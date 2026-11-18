"""Kits dos herois: passivas, RMB, Q, E, especial F e objetos de habilidade.

Mixin do ``Combatant`` (actors.py). Tudo aqui roda no dono do heroi (jogador local, ou o
servidor para os bots). Efeitos sobre outros jogadores viajam por ``damage()``/RPCs e
objetos compartilhados (torretas, clones, paredes, granadas, zonas) pela ``Arena``.

Mecanicas compartilhadas:
* marca (B-Cell): alvo marcado recebe +15% de dano; Killer T ganha +20% contra marcados;
* "frente" (``front``): membrana do Engolir (Macrofago) ou barreira (Pneumococcus) — os
  tiros inimigos que a cruzam param nela (combat.cast) e viram ``absorb``;
* ``ult``: janela do especial ativo; ``ult_cam``: camera em 3a pessoa (player.py).
"""
import math
from EasyCells3D.Geometry import Vec3
from .catalog import HEROES, CELLS, BALANCE
from .combat import direction, cast, melee_targets, impact_kind, EYE

GRAVITY = 18.0
PLACE_RANGE = {'turret': 12.0, 'wall': 10.0}
STATUS_KINDS = ('root', 'antiheal', 'perforin', 'ult', 'absorb')


def predict_arc(world, start, velocity, steps=60, dt=1/30):
    """Trajetoria balistica (granadas): pontos ate tocar o mundo. Devolve (pontos, impacto)."""
    x, y, z = start
    vx, vy, vz = velocity
    points = [(x, y, z)]
    for _ in range(steps):
        nvy = vy-GRAVITY*dt
        nx, ny, nz = x+vx*dt, y+(vy+nvy)*.5*dt, z+vz*dt
        delta = Vec3(nx-x, ny-y, nz-z)
        dist = delta.magnitude()
        if dist > 1e-6:
            hit = world.raycast(Vec3(x, y, z), delta, dist, 1 | 8)
            if hit is not None:
                points.append(hit.point.to_tuple)
                return points, hit.point.to_tuple
        x, y, z, vy = nx, ny, nz, nvy
        points.append((x, y, z))
    return points, None


class KitMixin:
    # ------------------------------------------------------------------ estado
    def reset_kit(self):
        self.ability_cd = self.secondary_cd = self.ability2_cd = self.melee_cd = 0
        self.charge = 0.0
        self.boost = self.capsule = self.dash = self.reveal = self.marked = 0
        self.slow = self.slow_factor = self.haste = self.guard = self.leap = self.stagger = 0
        self.root = self.antiheal = self.frenzy = self.shield_hold = 0
        self.ult = self.ult_cam = 0
        self.ult_on = False
        self.ult_focus = None
        self.zoom = False
        self.dash_dir = None
        self.preview = None
        self.front = None
        self.front_radius = 0.0
        self.engulf_energy = BALANCE['engulf_time']
        self.engulf_idle = self.engulf_lock = 0
        self.barrier_hp = BALANCE['barrier_health']
        self.barrier_idle = self.barrier_lock = 0
        self.feast = 0.0          # dano engolido durante o Banquete
        self.dash_charges = 0     # Quimiotaxia
        self.dash_kill = 0        # janela para recarregar o Avanco ao eliminar
        self.q_charges, self.q_recharge = 2, 0.0
        self.placing = None
        self.place = None         # (ponto, valido, yaw) da previa
        self.fire_block = False
        self.punch = 0.0
        self.aiming = False
        self.arc = None           # previa da granada acida
        self.perforin = []
        self.grapple = 0
        self.grapple_point = None
        self.slide = self.slide_tick = 0
        self.rain_tick = 0
        self.swing = getattr(self, 'swing', 0)
        self.fx = {}
        self.absorbed_fx = 0
        self.minion_serial = getattr(self, 'minion_serial', 0)

    TIMERS = ("ability_cd", "secondary_cd", "ability2_cd", "melee_cd", "boost", "capsule", "dash", "reveal",
              "marked", "slow", "haste", "stagger", "guard", "hit_marker", "hurt", "kill_marker", "absorbed",
              "root", "antiheal", "frenzy", "shield_hold", "ult", "ult_cam", "engulf_lock", "barrier_lock",
              "dash_kill", "grapple", "slide", "absorbed_fx")

    @property
    def eye(self):
        return self.transform.position+Vec3(0, EYE, 0)

    def aim(self):
        return direction(self.yaw, self.pitch)

    @property
    def is_bot(self):
        player = self.game.session.roster.value.get(self.slot)
        return bool(player and player["bot"])

    def pressed(self, cmd, key):
        return bool(cmd.get(key)) and not self.previous.get(key)

    def tick_fx(self, dt):
        for kind in list(self.fx):
            self.fx[kind] -= dt
            if self.fx[kind] <= 0:
                del self.fx[kind]

    # ------------------------------------------------------------------ dano
    def outgoing(self, amount, target):
        """Multiplicadores do atacante (passivas e especiais)."""
        k = 1.0
        if self.hero == 'killer_t':
            if target.marked > 0:
                k *= 1.2
            if self.ult > 0:
                k *= 1.4
        if self.hero == 'pseudomonas' and target.health.value < HEROES[target.hero].health*.5:
            k *= 1.3
        if self.frenzy > 0:
            k *= 1.2
        amount *= k
        if self.hero == 'killer_t' and self.ult > 0 and self.local:
            self.heal(amount*.25)
        return amount

    def heal(self, amount):
        cap = HEROES[self.hero].health
        if self.antiheal > 0 or not self.alive or self.health.value >= cap:
            return  # nao regrava a variavel de rede sem mudanca
        self.health.value = min(cap, self.health.value+amount)

    def in_own_dome(self):
        for zone in self.arena.zones:
            if zone['kind'] != 'dome':
                continue
            owner = self.arena.actors.get(zone['owner'])
            if owner is not None and owner.team == self.team and \
                    math.dist(zone['pos'], self.feet) < zone['radius']:
                return True
        return False

    def front_center(self):
        f = direction(self.yaw)
        p = self.transform.position
        return (p.x+f.x*.75, p.y+.25, p.z+f.z*.75)

    # ------------------------------------------------------------------ frente
    def set_front_state(self, kind):
        radius = 0.0
        if kind == 'engulf':
            radius = BALANCE['engulf_radius']*(2 if self.ult > 0 else 1)
        elif kind == 'barrier':
            radius = BALANCE['barrier_radius']
        if kind != self.front or abs(radius-self.front_radius) > .01:
            self.front, self.front_radius = kind, radius
            self.sync_front(kind, radius)

    def take_absorb(self, amount, source=None):
        """Dono da frente: tiro inimigo parou na membrana/barreira."""
        if self.front == 'engulf':
            self.absorbed_fx = .25
            self.gain(amount*BALANCE['charge_absorb'])
            if self.ult > 0:
                self.feast += amount
                share = amount*.6
                for ally in self.arena.actors.values():
                    if ally.team == self.team and ally.alive and \
                            (ally.transform.position-self.transform.position).magnitude() < 12:
                        ally.grant_shield(share, 6.0, 150)
        elif self.front == 'barrier':
            self.barrier_hp -= amount
            self.barrier_idle = 0
            if self.barrier_hp <= 0:
                self.barrier_hp = 0
                self.barrier_lock = 4.0
                self.set_front_state(None)
                self.arena.effect('shatter', self.front_center(), 2)

    def update_front(self, dt):
        if self.front == 'engulf':
            self.engulf_idle = 0
            if self.ult <= 0:
                self.engulf_energy -= dt
                if self.engulf_energy <= 0:
                    self.engulf_energy = 0
                    self.engulf_lock = 1.5
                    self.set_front_state(None)
        else:
            self.engulf_idle += dt
            if self.engulf_idle > 1:
                self.engulf_energy = min(BALANCE['engulf_time'], self.engulf_energy+dt*.6)
        if self.front != 'barrier':
            self.barrier_idle += dt
            if self.barrier_idle > 2 and self.barrier_hp < BALANCE['barrier_health']:
                self.barrier_hp = min(BALANCE['barrier_health'], self.barrier_hp+dt*90)

    # ------------------------------------------------------------------ entrada
    def can_fire(self):
        return (self.front is None and not self.placing and not self.fire_block and self.punch <= 0
                and not self.aiming and not (self.hero == 'b_cell' and self.ult > 0))

    def kit_speed(self):
        if self.root > 0 or (self.hero == 'b_cell' and self.ult > 0):
            return 0.0
        k = 1.0
        if self.front == 'engulf':
            k *= .85
        elif self.front == 'barrier':
            k *= .65
        if self.punch > 0:
            k *= .7
        if self.frenzy > 0:
            k *= 1.2
        if self.ult > 0 and self.hero == 'killer_t':
            k *= 1.25
        if self.ult > 0 and self.hero == 'streptococcus':
            k *= 1.2
        return k

    def handle_input(self, cmd, dt):
        if not cmd.get('fire'):
            self.fire_block = False
        if self.placing:
            self.update_placement(cmd)
            return
        self.secondary_input(cmd, dt)
        if cmd.get("fire") and self.can_fire() and (self.hero != "b_cell" or self.pressed(cmd, "fire")):
            self.weapon.fire()
        if self.pressed(cmd, "ability"):
            self.ability()
        if self.pressed(cmd, "ability2"):
            self.ability2()
        if self.pressed(cmd, "melee"):
            self.quick_melee()
        if self.pressed(cmd, "ultimate"):
            self.ultimate()

    def secondary_input(self, cmd, dt):
        h = self.hero
        held = bool(cmd.get('secondary'))
        if h == 'b_cell':
            self.zoom = held and self.ult <= 0
        elif h == 'macrophage':
            want = held and self.engulf_lock <= 0 and (self.engulf_energy > 0 or self.ult > 0)
            self.set_front_state('engulf' if want else None)
        elif h == 'pneumococcus':
            want = held and self.barrier_lock <= 0 and self.barrier_hp > 0
            self.set_front_state('barrier' if want else None)
        elif h == 'killer_t':
            if self.ult > 0:
                if held and self.secondary_cd <= 0:
                    self.charged_punch(1.0, .45)
            elif held and self.secondary_cd <= 0:
                self.punch = min(1.0, self.punch+dt)
            elif self.punch > 0:
                self.charged_punch(self.punch, HEROES[h].secondary_cd)
                self.punch = 0.0
        elif h == 'pseudomonas':
            if held and self.secondary_cd <= 0:
                self.aiming = True
                start, vel = self.throw_vector(16, 5)
                self.arc = predict_arc(self.game.physics_world, start, vel)
            elif self.aiming:
                self.aiming = False
                self.arc = None
                if self.secondary_cd <= 0:
                    self.secondary_cd = HEROES[h].secondary_cd
                    self.throw('acid', 16, 5)
                    self.mark_action()
        elif held:
            self.secondary()

    def mark_action(self, value=1.0):
        self.action = value
        self.show_action(value)

    # ------------------------------------------------------------------ corpo a corpo
    def melee(self, reach, amount, arc=.3, rbc_factor=1.0, execute=None, cooldown=.8, knock=0.0,
              cd_attr='secondary_cd', backstab=False):
        if getattr(self, cd_attr) > 0:
            return
        setattr(self, cd_attr, cooldown)
        self.swing += 1
        self.mark_action()
        for kind, target in melee_targets(self, reach, arc, include_rbc=rbc_factor > 1):
            dmg = amount
            if kind == 'actor':
                if execute and target.health.value < HEROES[target.hero].health*execute[0]:
                    dmg = execute[1]
                d = target.transform.position-self.transform.position
                flat = Vec3(d.x, 0, d.z)
                flat = flat.normalize() if flat.magnitude() > .01 else direction(self.yaw)
                if backstab and flat.dot(direction(target.yaw)) > .35:
                    dmg *= 2
                    self.arena.effect('backstab', target.transform.position.to_tuple, 1)
                fx = dict(knock=(flat.x*knock, 3+knock*.15, flat.z*knock)) if knock else None
                target.damage(dmg, self, fx)
            elif kind == 'colony':
                self.arena.hit_colony(self.slot, target, dmg)
                self.hit_marker = .15
            else:
                self.arena.hit_rbc(self.slot, target, dmg*rbc_factor)
                self.hit_marker = .15

    def quick_melee(self):
        self.melee(1.9, 30, arc=.3, cooldown=.9, cd_attr='melee_cd')

    def charged_punch(self, k, cooldown):
        self.melee(2.5, 40+80*k, arc=.15, knock=3+8*k, cooldown=cooldown)
        f = direction(self.yaw)
        v = self.body.velocity
        self.body.velocity = Vec3(v.x+f.x*5*k, v.y, v.z+f.z*5*k)
        if k > .6:
            self.arena.effect('punch', (self.eye+f*1.4).to_tuple, 1.5*k)

    # ------------------------------------------------------------------ RMB simples
    def secondary(self):
        h = self.hero
        cd = HEROES[h].secondary_cd
        if h == 'neutrophil':
            self.melee(1.8, 55, cooldown=cd, backstab=True)
        elif h == 'streptococcus':
            self.melee(2.0, 30, arc=.4, rbc_factor=4.0, cooldown=cd*(.6 if self.ult > 0 else 1))
        elif h == 'staphylococcus' and self.secondary_cd <= 0:
            self.secondary_cd = cd
            self.mark_action()
            hits = cast(self, self.aim(), 40)
            if hits:
                self.arena.tracer(self.eye.to_tuple, hits[0]['point'].to_tuple, 'sticky', self.slot, impact_kind(hits))
                self.apply_hit(hits[0], 35, dict(slow=(.4, 2.5)))

    # ------------------------------------------------------------------ Q
    def ability(self):
        h = self.hero
        kit = HEROES[h]
        if h == 'streptococcus':
            if self.q_charges <= 0:
                return
        elif h == 'neutrophil' and self.dash_charges > 0:
            pass
        elif self.ability_cd > 0:
            return
        cd = kit.ability_cd
        if h in ('b_cell', 'staphylococcus'):
            self.placing = 'turret' if h == 'b_cell' else 'wall'
            if self.is_bot:
                point, ok, yaw = self.placement_target(bot=True)
                if point is None or not ok:
                    self.placing = None
                    return
                self.confirm_place(point, yaw)
            return
        if h == 'neutrophil':
            self.start_dash(.26, 22)
            if self.dash_charges > 0:
                self.dash_charges -= 1
                cd = .35
        elif h == 'macrophage':
            self.hook()
        elif h == 'killer_t':
            aim = direction(self.yaw)
            self.body.velocity = Vec3(aim.x*12, 8.5, aim.z*12)
            self.leap = .01
        elif h == 'pneumococcus':
            self.start_dash(.4, 19)
        elif h == 'pseudomonas':
            self.start_dash(.6, 13)
            self.slide, self.slide_tick = .6, 0
        elif h == 'streptococcus':
            self.start_dash(.22, 24, vertical=True)
            self.q_charges -= 1
            if self.q_recharge <= 0:
                self.q_recharge = cd
            cd = 0
        self.ability_cd = cd
        self.mark_action(.6)

    def hook(self):
        hits = cast(self, self.aim(), 20)
        end = hits[0]['point'] if hits else self.eye+self.aim()*20
        self.arena.tracer(self.eye.to_tuple, end.to_tuple, 'hook', self.slot, impact_kind(hits))
        if hits and hits[0]['kind'] == 'actor':
            target = hits[0]['target']
            d = self.transform.position-target.transform.position
            flat = Vec3(d.x, 0, d.z)
            dist = flat.magnitude()
            if dist > .1:
                flat = flat.normalize()*min(17, max(4, dist*2.0))
                target.damage(30, self, dict(knock=(flat.x, 4.5, flat.z)))
        elif hits:
            self.apply_hit(hits[0], 30)

    def dash_hits(self):
        if self.hero not in ('neutrophil', 'pneumococcus'):
            return
        hit = getattr(self, 'dash_hit', set())
        for other in self.arena.actors.values():
            if other.team != self.team and other.alive and other.slot not in hit \
                    and (other.transform.position-self.transform.position).magnitude() < 1.8:
                hit.add(other.slot)
                if self.hero == 'neutrophil':
                    self.dash_kill = 1.0
                    other.damage(35, self)
                else:
                    flat = Vec3(self.dash_dir.x, 0, self.dash_dir.z).normalize()
                    other.damage(40, self, dict(knock=(flat.x*12, 3.5, flat.z*12), root=.9))
                    self.dash = min(self.dash, .06)
                    self.arena.effect('slam', other.feet, 2)
        self.dash_hit = hit

    def start_dash(self, seconds, speed, vertical=False):
        aim = direction(self.yaw, self.pitch if vertical else 0)
        self.dash_dir = aim*speed
        self.dash = seconds
        self.dash_hit = set()

    # ------------------------------------------------------------------ posicionamento
    def placement_target(self, bot=False):
        kind = self.placing
        reach = PLACE_RANGE[kind]
        world = self.game.physics_world
        if bot:
            target = min((a for a in self.arena.actors.values() if a.team != self.team and a.alive),
                         key=lambda a: (a.transform.position-self.transform.position).magnitude(), default=None)
            yaw = self.yaw
            dist = 2.5 if kind == 'turret' else 4.0
            ahead = self.transform.position+direction(yaw)*dist
            if target is not None and kind == 'wall':
                d = target.transform.position-self.transform.position
                yaw = math.atan2(d.x, -d.z)
                ahead = self.transform.position+direction(yaw)*min(4.0, d.magnitude()*.5)
            hit = world.raycast(ahead+Vec3(0, 1, 0), Vec3(0, -1, 0), 4, 1)
        else:
            yaw = self.yaw
            hit = world.raycast(self.eye, self.aim(), reach, 1)
            if hit is None or (hit.normal is not None and hit.normal.y < .7):
                flat = direction(self.yaw)
                far = (hit.point-flat*.6) if hit is not None else self.eye+self.aim()*reach
                hit = world.raycast(Vec3(far.x, self.eye.y+.2, far.z), Vec3(0, -1, 0), 8, 1)
        if hit is None:
            return None, False, yaw
        ok = hit.normal is None or hit.normal.y > .7
        point = hit.point
        if kind == 'turret' and ok:
            ok = not world.overlap_sphere(Vec3(point.x, point.y+.75, point.z), .35, 1)
        return (point.x, point.y, point.z), ok, yaw

    def update_placement(self, cmd):
        point, ok, yaw = self.placement_target()
        self.place = (point, ok, yaw) if point is not None else None
        if self.pressed(cmd, 'secondary') or self.pressed(cmd, 'ability'):
            self.placing, self.place = None, None
            return
        if self.pressed(cmd, 'fire') and point is not None and ok:
            self.fire_block = True
            self.confirm_place(point, yaw)

    def confirm_place(self, point, yaw):
        kind, self.placing, self.place = self.placing, None, None
        self.minion_serial = (self.minion_serial+1) % 900
        ident = self.slot*1000+self.minion_serial
        if kind == 'turret':
            for old, m in list(self.arena.minions.items()):
                if m['slot'] == self.slot and m['kind'] == 'turret':
                    self.arena.remove_minion(old)
            self.arena.spawn_minion(ident, 'turret', self.slot, point, yaw, BALANCE['turret_health'], 0)
        else:
            self.arena.add_wall(ident, point, yaw, BALANCE['wall_life'])
        self.ability_cd = HEROES[self.hero].ability_cd
        self.mark_action(.6)

    # ------------------------------------------------------------------ E
    def ability2(self):
        if self.ability2_cd > 0:
            return
        h = self.hero
        cd = HEROES[h].ability2_cd
        aim = self.aim()
        if h == 'macrophage':
            self.melee(3.2, 85, arc=-.1, knock=7, cooldown=cd, cd_attr='ability2_cd')
            self.arena.effect('slam', (self.transform.position+direction(self.yaw)*1.6).to_tuple, 2.5)
            return
        if h == 'neutrophil':
            self.skill_shot('net', 25, 15, dict(root=1.5))
        elif h == 'b_cell':
            self.throw('antibody', 20, 4)
        elif h == 'killer_t':
            self.skill_shot('perforin', 12, 10, dict(perforin=(55, 3.0)))
        elif h == 'pneumococcus':
            self.grant_shield(100, 5.0, 170)
            allies = [a for a in self.arena.actors.values() if a.team == self.team and a.alive and a.slot != self.slot
                      and (a.transform.position-self.transform.position).magnitude() < 15]
            if allies:
                best = max(allies, key=lambda a: (a.transform.position-self.transform.position).normalize().dot(aim))
                best.grant_shield(100, 5.0, 170)
                self.arena.tracer(self.eye.to_tuple, best.transform.position.to_tuple, 'capsule', self.slot, None)
        elif h == 'staphylococcus':
            self.skill_shot('toxin', 30, 20, dict(antiheal=5))
        elif h == 'pseudomonas':
            hit = self.game.physics_world.raycast(self.eye, aim, 25, 1)
            if hit is None:
                return
            self.arena.tracer(self.eye.to_tuple, hit.point.to_tuple, 'flagellum', self.slot, 'world')
            self.grapple, self.grapple_point = .9, hit.point
        elif h == 'streptococcus':
            hits = cast(self, aim, 22)
            if not hits:
                return
            self.arena.tracer(self.eye.to_tuple, hits[0]['point'].to_tuple, 'chain', self.slot, impact_kind(hits))
            if hits[0]['kind'] == 'actor':
                self.apply_hit(hits[0], 15, dict(slow=(.4, 1.5)))
            self.grapple, self.grapple_point = .7, hits[0]['point']
        self.ability2_cd = cd
        self.mark_action(.6)

    def skill_shot(self, kind, reach, damage, effect):
        hits = cast(self, self.aim(), reach)
        end = hits[0]['point'] if hits else self.eye+self.aim()*reach
        self.arena.tracer(self.eye.to_tuple, end.to_tuple, kind, self.slot, impact_kind(hits))
        if hits:
            self.apply_hit(hits[0], damage, effect)

    # ------------------------------------------------------------------ granadas
    def throw_vector(self, speed, up):
        aim = self.aim()
        start = self.eye+aim*.6
        vel = aim*speed+Vec3(0, up, 0)
        return start.to_tuple, vel.to_tuple

    def throw(self, kind, speed, up):
        start, vel = self.throw_vector(speed, up)
        self.arena.throw(kind, start, vel, self.slot)

    def detonate(self, kind, point):
        center = Vec3(*point)
        if kind == 'antibody':
            self.arena.effect('antibody', point, 4)
            self.area_damage(4.0, 35, effect=dict(mark=4), center=center+Vec3(0, .5, 0))
        elif kind == 'acid':
            # Onda e poca no chao abaixo da explosao (que pode ser no tronco de alguem ou no ar).
            floor = self.arena.floor_at(point)
            if floor is not None:
                self.arena.effect('burst', floor[0], 3.5, normal=floor[1])
            else:
                self.arena.effect('burst', point, 3.5)
            self.area_damage(3.5, 45, center=center+Vec3(0, .5, 0))
            if floor is not None:
                self.zone('acid', 2.6, 4, floor[0], normal=floor[1])
            for ident, cell in self.arena.rbc_view.cells.items():
                if cell['state'] not in ('dead', 'inside') and math.dist(cell['pos'], point) < 3.5:
                    self.arena.hit_rbc(self.slot, ident, 45)

    def spit_impact(self, hit, point, aim):
        """Glob da Pseudomonas acertou (roda no dono, mesmo morto): dano direto, respingo e poca
        de acido. No mapa, a poca gruda na superficie atingida (chao, rampa, parede, teto); num
        alvo, cai no chao abaixo dele. Membranas/barreiras engolem o glob inteiro."""
        from .combat import SPIT
        self.apply_hit(hit, HEROES['pseudomonas'].damage)
        if hit['kind'] == 'front':
            return
        # Recua um pouco do ponto atingido para o respingo/chao nao partirem de dentro da parede.
        back = Vec3(*point)-aim*.2
        direct = (hit['target'],) if hit['kind'] in ('actor', 'minion') else ()
        self.area_damage(SPIT['splash_radius'], SPIT['splash_damage'], center=back, exclude=direct)
        surface = self.arena.surface_at(point, aim) if hit['kind'] in ('world', 'colony') else None
        surface = surface or self.arena.floor_at(back.to_tuple)
        if surface is not None:
            self.zone('acid', SPIT['zone_radius'], SPIT['zone_life'], surface[0], normal=surface[1])

    # ------------------------------------------------------------------ F
    def ultimate(self):
        h = self.hero
        if h == 'macrophage' and self.ult_on:
            self.spit()
            return
        if self.charge < 100 or self.arena.state.winner or self.ult_on:
            return
        kit = HEROES[h]
        self.charge = 0
        self.ult_on = True
        self.ult_cam = kit.ult_time
        self.arena.effect('ult', self.feet, 3, h)
        seconds = kit.ult_time
        if h == 'neutrophil':
            seconds = 8
            for other in self.arena.actors.values():
                if other.team == self.team:
                    other.reveal_enemies(8)
                    other.buff('haste', 6)
            self.dash_charges, self.ability_cd = 3, 0
        elif h == 'macrophage':
            self.feast = 0.0
            self.engulf_energy = BALANCE['engulf_time']
        elif h == 'b_cell':
            hit = self.game.physics_world.raycast(self.eye, self.aim(), 70, 1)
            point = hit.point if hit is not None else self.eye+self.aim()*40
            down = self.game.physics_world.raycast(Vec3(point.x, point.y+1, point.z), Vec3(0, -1, 0), 30, 1)
            if down is not None:
                point = down.point
            self.ult_focus = (point.x, point.y, point.z)
            self.zone('rain', 7, 4.5, self.ult_focus)
            self.zoom = False
        elif h == 'killer_t':
            pass
        elif h == 'pneumococcus':
            self.zone('cloud', 7, 7, follow=True)
        elif h == 'staphylococcus':
            seconds = 8
            self.zone('dome', BALANCE['dome_radius'], 8, self.feet)
            self.arena.fortify(self.slot, self.feet, 15, 10)
        elif h == 'pseudomonas':
            seconds = 8
            self.zone('mature', 9, 12)
            for other in self.arena.actors.values():
                if other.team == self.team:
                    other.buff('frenzy', 8)
        elif h == 'streptococcus':
            seconds = 8
            self.q_charges = 2
            for side in (-1, 1):
                self.minion_serial = (self.minion_serial+1) % 900
                yaw = self.yaw+side*.45
                start = self.transform.position+direction(yaw)*1.2
                self.arena.spawn_minion(self.slot*1000+self.minion_serial, 'clone', self.slot,
                                        (start.x, start.y-.95, start.z), yaw, BALANCE['clone_health'], 10)
        self.ult = seconds
        self.status_fx('ult', seconds)

    def spit(self):
        """Macrofago: cospe o que engoliu numa onda frontal e encerra o Banquete."""
        amount = min(250, 50+self.feast*.5)
        forward = direction(self.yaw)
        p = self.transform.position
        for other in list(self.arena.actors.values()):
            if other.team == self.team or not other.alive:
                continue
            d = other.transform.position-p
            flat = Vec3(d.x, 0, d.z)
            dist = flat.magnitude()
            if dist < 11 and (dist < .8 or flat.normalize().dot(forward) > .5) and self.arena.visible(self, other):
                other.damage(amount, self, dict(knock=(forward.x*9, 4, forward.z*9)))
        for colony in list(self.arena.state.colonies):
            c = colony['pos']
            d = Vec3(c[0]-p.x, 0, c[2]-p.z)
            if d.magnitude() < 12 and d.normalize().dot(forward) > .5:
                self.arena.hit_colony(self.slot, colony['id'], amount)
        self.arena.effect('spit', self.feet, 11, self.yaw)
        self.end_ult()

    def end_ult(self):
        self.ult_on = False
        self.ult = 0
        self.ult_cam = min(self.ult_cam, .7)
        self.dash_charges = 0
        self.ult_focus = None
        self.status_fx('ult', 0)
        if self.front == 'engulf':
            self.set_front_state('engulf')

    # ------------------------------------------------------------------ quadro a quadro
    def kit_update(self, dt):
        h = self.hero
        if self.ult_on and self.ult <= 0:
            if h == 'macrophage':
                self.spit()
            else:
                self.end_ult()
        pulse = getattr(self, 'pulse', 0.0)  # curas passivas no mesmo pulso da regeneracao
        if pulse and h == 'staphylococcus' and self.arena.nearest_colony(self.feet, 8):
            self.heal(10*pulse)
        if pulse and self.in_own_dome():
            self.heal(15*pulse)
        self.update_front(dt)
        if h == 'streptococcus' and self.q_charges < 2:
            self.q_recharge -= dt
            if self.q_recharge <= 0:
                self.q_charges += 1
                self.q_recharge = HEROES[h].ability_cd if self.q_charges < 2 else 0
        for item in list(self.perforin):
            item[0] -= dt
            if item[0] <= 0:
                self.perforin.remove(item)
                amount = item[1]*(1.2 if self.marked > 0 else 1)
                self.arena.effect('perforin', self.transform.position.to_tuple, 1.4)
                self.take_hit(amount, item[2])
        if self.grapple > 0 and self.grapple_point is not None:
            d = self.grapple_point-self.transform.position
            if d.magnitude() < 1.8:
                self.grapple = 0
            else:
                self.dash_dir = d.normalize()*22+Vec3(0, 1.0, 0)
                self.dash = max(self.dash, .05)
        if self.slide > 0:
            self.slide_tick -= dt
            if self.slide_tick <= 0:
                self.slide_tick = .12
                self.zone('biofilm', 1.9, 6, self.feet)
        if self.ult > 0 and h == 'b_cell' and self.ult_focus:
            self.rain_tick -= dt
            if self.rain_tick <= 0:
                self.rain_tick = .5
                for colony in list(self.arena.state.colonies):
                    if math.dist(colony['pos'], self.ult_focus) < 8:
                        self.arena.hit_colony(self.slot, colony['id'], 30)
        self.update_minions(dt)

    # ------------------------------------------------------------------ torretas e clones
    def update_minions(self, dt):
        arena = self.arena
        world = self.game.physics_world
        for ident, m in list(arena.minions.items()):
            if m['slot'] != self.slot:
                continue
            m['cool'] = m.get('cool', 0)-dt
            m['sync'] = m.get('sync', 0)-dt
            x, y, z = m['pos']
            if m['kind'] == 'clone':
                m['life'] -= dt
                if m['life'] <= 0:
                    arena.effect('pop', (x, y+.8, z), 1.2)
                    arena.remove_minion(ident)
                    continue
                f = direction(m['yaw'])
                origin = Vec3(x, y+.8, z)
                if world.raycast(origin, f, 1.2, 1) is not None:
                    m['yaw'] += 1.3
                else:
                    nx, nz = x+f.x*6*dt, z+f.z*6*dt
                    ground = world.raycast(Vec3(nx, y+1.2, nz), Vec3(0, -1, 0), 3, 1)
                    if ground is not None:
                        m['pos'] = (nx, ground.point.y, nz)
                    else:
                        m['yaw'] += 1.3
                reach, damage, rate = 20, 4, .3
            else:
                reach, damage, rate = BALANCE['turret_range'], BALANCE['turret_damage'], .5
            x, y, z = m['pos']
            muzzle = (x, y+.85, z)
            target = None
            best = reach
            for other in arena.actors.values():
                if other.team == self.team or not other.alive:
                    continue
                dist = math.dist(muzzle, other.transform.position.to_tuple)
                if dist < best and arena.clear_line(muzzle, other.transform.position.to_tuple):
                    target, best = other, dist
            if target is not None:
                d = target.transform.position-Vec3(*muzzle)
                if m['kind'] == 'turret':
                    m['yaw'] = math.atan2(d.x, -d.z)
                if m['cool'] <= 0:
                    m['cool'] = rate
                    m['recoil'] = 1.0
                    arena.tracer(muzzle, target.transform.position.to_tuple, m['kind'], self.slot, 'actor')
                    target.damage(damage, self, dict(mark=2.5) if m['kind'] == 'turret' else None)
            if m['sync'] <= 0:
                m['sync'] = .1
                arena.sync_minion(ident, m['pos'], m['yaw'], m.get('recoil', 0))
