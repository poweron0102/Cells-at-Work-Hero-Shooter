"""Combatentes: ciclo de vida, dano, construcao e respawn (kits em kits.py).

Cada jogador simula o proprio heroi (movimento, armas, habilidades). Acoes
sobre objetos compartilhados (colonias, hemacias, recursos) viram pedidos ao
servidor, que valida e replica pelo snapshot da Arena.
"""
import math
import time
from EasyCells3D.NetworkComponents import NetworkComponent, NetworkTransform, NetworkVariable, Rpc, SendTo
from EasyCells3D.Geometry import Vec3, Quaternion
from EasyCells3D.PhysicsComponents3D import PhysicsBody3D, CharacterController3D, CapsuleShape, BodyType
from .catalog import HEROES, CELLS, BALANCE
from .combat import Weapon, direction, EYE
from .kits import KitMixin
from .visuals import CombatantVisual

SHIELD_BASE = {"pneumococcus": 70}


class Combatant(NetworkComponent, KitMixin):
    def __init__(self, arena, slot, hero, team, owner):
        super().__init__(identifier=1000+slot, owner=owner)
        self.arena, self.slot, self.hero, self.team = arena, slot, hero, team
        self.health = NetworkVariable(HEROES[hero].health, 2000+slot*4, owner)
        self.shield = NetworkVariable(SHIELD_BASE.get(hero, 0), 2001+slot*4, owner)
        self.kills = NetworkVariable(0, 2002+slot*4, owner)
        self.deaths = NetworkVariable(0, 2003+slot*4, owner)
        self.respawn = 0
        self.waiting = False
        self.spawn_choice = None
        self.killer = None
        self.yaw = 0 if team == CELLS else math.pi
        self.pitch = 0
        self.reset_kit()
        self.since_hit = 10
        self.hit_marker = self.hurt = self.kill_marker = 0
        self.absorbed = 0
        self.hurt_from = []  # [(x, z, time)]
        self.shot = 0
        self.controls = {}
        self.previous = {}
        self.build = None  # dict(pos, progress) while holding the build action
        self.build_problem = ""
        self.deliver_hold = False
        self.action = 0.0
        self.third_person = 0.0  # 0..1, camera em 3a pessoa (player.py)
        self.fire_serial, self.fire_time, self.fire_kind = 0, -1.0, 'shot'
        self.vm_muzzle = None   # cano no espaço do viewmodel (jogador local em 1ª pessoa)
        self.tp_muzzle = None   # cano da arma na mão do personagem (mundo)

    def init(self):
        super().init()
        self.body = self.GetComponent(PhysicsBody3D)
        self.controller = self.GetComponent(CharacterController3D)
        self.weapon = self.GetComponent(Weapon)

    @property
    def local(self):
        return self.owner == self.game.session.manager.id

    @property
    def alive(self):
        return self.health.value > 0

    @property
    def feet(self):
        p = self.transform.position
        return (p.x, p.y-.95, p.z)

    # -- dano ---------------------------------------------------------------
    def damage(self, amount, source, effect=None):
        """Called by the attacker (any peer); routed to the owner of the target."""
        if amount > 0:
            amount = source.outgoing(amount, self)
        if source.local and source.team != self.team:
            source.gain(amount*BALANCE['charge_per_damage'])
            source.hit_marker = .15
        p = source.transform.position
        if self.local:
            self.take_hit(amount, source.slot, effect, (p.x, p.z))
        else:
            self.hit(amount, source.slot, effect, (p.x, p.z))

    @Rpc(send_to=SendTo.OWNER, require_owner=False)
    def hit(self, amount, source, effect=None, origin=None):
        if self.local:
            self.take_hit(amount, source, effect, origin)

    def take_hit(self, amount, source, effect=None, origin=None):
        source = self.arena.actors[source]
        if not self.alive or source.team == self.team or self.arena.state.winner:
            return
        if self.guard > 0:
            amount *= .5
        if self.marked > 0:
            amount *= 1+BALANCE['mark_bonus']
        if self.in_own_dome():
            amount *= .7
        absorbed = min(self.shield.value, amount)
        if absorbed:
            self.absorbed = .4
        self.shield.value -= absorbed
        self.health.value = max(0, self.health.value - amount + absorbed)
        if amount > 0:
            self.since_hit, self.hurt = 0, .25
        if origin:
            self.hurt_from = (self.hurt_from+[(origin[0], origin[1], self.arena.state.elapsed)])[-4:]
        if self.build and amount > 0:
            self.arena.building(self.slot, self.build['pos'], False)
            self.build = None
            self.build_problem = "Construcao interrompida por dano"
        effect = effect or {}
        if effect.get('slow'):
            self.slow, self.slow_factor = effect['slow'][1], effect['slow'][0]
        if effect.get('knock') and self.body.enable:
            kx, ky, kz = effect['knock']
            self.body.velocity = Vec3(kx, ky, kz)
            self.dash = 0
            self.grapple = 0
            self.stagger = .45
        if effect.get('mark'):
            self.marked = max(self.marked, effect['mark'])
            self.arena.mark_actor(self.slot, effect['mark'])
        for kind in ('root', 'antiheal'):
            if effect.get(kind):
                setattr(self, kind, max(getattr(self, kind), effect[kind]))
                self.status_fx(kind, effect[kind])
        if kind := effect.get('perforin'):
            self.perforin.append([kind[1], kind[0], source.slot])
            self.status_fx('perforin', kind[1])
        if not self.alive:
            self.die(source)

    @Rpc(send_to=SendTo.OWNER, require_owner=False)
    def absorb(self, amount, source=None):
        if self.local:
            self.take_absorb(amount, source)

    def absorb_hit(self, amount, source):
        if self.local:
            self.take_absorb(amount, source.slot)
        else:
            self.absorb(amount, source.slot)

    @Rpc(send_to=SendTo.ALL, require_owner=False)
    def grant_shield(self, amount, seconds, cap):
        if self.local and self.alive:
            base = SHIELD_BASE.get(self.hero, 0)
            self.shield.value = min(base+cap, self.shield.value+amount)
            self.shield_hold = max(self.shield_hold, seconds)

    @Rpc(send_to=SendTo.ALL, require_owner=False)
    def status_fx(self, kind, seconds):
        if seconds > 0:
            self.fx[kind] = max(self.fx.get(kind, 0), seconds)
        else:
            self.fx.pop(kind, None)

    @Rpc(send_to=SendTo.NOT_ME, require_owner=False)
    def sync_front(self, kind, radius):
        self.front, self.front_radius = kind, radius

    def die(self, source):
        self.respawn = BALANCE['respawn_seconds']
        self.waiting = False
        self.deaths.value += 1
        self.build = None
        self.placing = self.place = None
        if self.front:
            self.set_front_state(None)
        source.credit_kill(self.transform.position.to_tuple)
        self.body.enable = False
        self.arena.eliminated(self.slot, source.slot, self.deaths.value, self.transform.position.to_tuple)

    @Rpc(send_to=SendTo.ALL, require_owner=False)
    def credit_kill(self, position=None):
        if self.local:
            self.kills.value += 1
            self.kill_marker = .6
            self.gain(12)
            if self.hero == 'neutrophil' and self.dash_kill > 0:
                self.ability_cd = 0
            if self.hero == 'macrophage' and position is not None and \
                    math.dist(position, self.transform.position.to_tuple) < 6:
                self.heal(HEROES['macrophage'].health*.25)
                self.arena.effect('heal', self.feet, 1.5)

    def gain(self, amount):
        """Special charge from combat and objectives (never from time alone)."""
        if self.alive and not self.ult_on:
            self.charge = min(100.0, self.charge+amount)

    def apply_hit(self, hit, damage, effect=None):
        """Resolve one hit from this local actor onto whatever the ray found."""
        kind = hit['kind']
        if kind == 'actor':
            target = hit['target']
            if hit.get('head'):
                damage *= 1.5
            if self.hero == 'b_cell':
                effect = dict(effect or {}, mark=max(3, (effect or {}).get('mark', 0)))
            target.damage(damage, self, effect)
        elif kind == 'front':
            hit['target'].absorb_hit(damage, self)
            self.hit_marker = .1
        elif kind == 'minion':
            self.arena.damage_minion(hit['target'], damage, self.slot)
            self.hit_marker = .15
        elif kind == 'colony':
            self.arena.hit_colony(self.slot, hit['target'], damage*(2.0 if self.hero == 'b_cell' else 1))
            self.gain(damage*BALANCE['charge_per_damage']*.5)
            self.hit_marker = .15
        elif kind == 'rbc':
            self.arena.hit_rbc(self.slot, hit['target'], damage*(2 if self.hero == 'streptococcus' else 1))
            self.gain(damage*BALANCE['charge_per_damage']*.5)
            self.hit_marker = .15

    # -- respawn ------------------------------------------------------------
    def spawn_options(self):
        if self.team == CELLS:
            return [('base', None)]
        return self.arena.spawn_options()

    def try_spawn(self):
        options = self.spawn_options()
        if not options:
            self.waiting = True
            return False
        choice = next((o for o in options if o == self.spawn_choice), None) or options[0]
        position = self.arena.spawn_position(self.slot, choice)
        if position is None:
            self.waiting = True
            return False
        self.spawn(position)
        return True

    def spawn(self, position=None):
        if position is None:
            position = self.arena.spawn_position(self.slot, ('base', None) if self.team == CELLS else ('entrance', None))
        self.hero = self.game.session.roster.value[self.slot]["hero"]
        self.health.value = HEROES[self.hero].health
        self.shield.value = SHIELD_BASE.get(self.hero, 0)
        charge = self.charge
        self.reset_kit()
        self.charge = charge*.5
        self.previous = {}
        self.waiting = False
        self.killer = None
        self.weapon.ammo = HEROES[self.hero].magazine
        self.weapon.timer = self.weapon.reload_time = 0
        self.body.enable = True
        self.body.teleport(position)
        self.spawned(self.hero)

    @Rpc(send_to=SendTo.NOT_ME)
    def spawned(self, hero):
        self.hero = hero
        self.front, self.front_radius = None, 0.0
        self.fx = {}

    @Rpc(send_to=SendTo.ALL, require_owner=False)
    def reveal_enemies(self, seconds):
        self.reveal = max(self.reveal, seconds)

    @Rpc(send_to=SendTo.ALL, require_owner=False)
    def buff(self, kind, seconds):
        if self.local:
            setattr(self, kind, max(getattr(self, kind), seconds))
        self.fx[kind] = max(self.fx.get(kind, 0), seconds)

    @Rpc(send_to=SendTo.ALL, require_owner=False)
    def show_action(self, value):
        self.action = value

    def fired(self, kind='shot'):
        """Evento visual de disparo (local ou recebido): recuo em 3ª pessoa e clarão.
        Os chumbos de uma mesma escopetada contam como um disparo só."""
        now = time.perf_counter()
        if now - self.fire_time > .03:
            self.fire_serial += 1
            self.fire_kind = kind
        self.fire_time = now

    # -- loop ---------------------------------------------------------------
    def loop(self):
        owner = self.game.session.roster.value[self.slot]["owner"]
        if owner != self.owner:
            self.owner = owner
            self.GetComponent(NetworkTransform).owner = owner
            for variable in (self.health, self.shield, self.kills, self.deaths):
                variable.owner = owner
            self.body.body_type = BodyType.DYNAMIC if self.local else BodyType.KINEMATIC
        if self.body.enable and not self.alive:
            self.respawn = BALANCE['respawn_seconds']
        self.body.enable = self.alive
        if self.game.session.status != "playing":
            return
        dt = min(.05, self.game.delta_time)
        for key in self.TIMERS:
            setattr(self, key, max(0, getattr(self, key)-dt))
        self.tick_fx(dt)
        self.action = max(0.0, self.action-dt*2.5)
        if not self.alive:
            self.zoom = False
            self.placing = self.place = None
            if self.local:
                self.respawn -= dt
                if self.respawn <= 0 and not self.arena.state.winner:
                    self.try_spawn()
            return
        if not self.local:
            facing = self.transform.rotation.rotate_vector(Vec3(0, 0, 1))
            self.yaw = math.atan2(facing.x, facing.z)
            return
        self.since_hit += dt
        kit = HEROES[self.hero]
        base_shield = SHIELD_BASE.get(self.hero, 0)
        # vida/escudo sao variaveis de rede (cada escrita vira um SET TCP): regenera em pulsos de 0,25 s
        self.regen_clock = getattr(self, 'regen_clock', 0.0)+dt
        self.pulse = 0.0
        if self.regen_clock >= .25:
            self.pulse, self.regen_clock = self.regen_clock, 0.0
        if self.pulse:
            if self.since_hit > 5 and self.antiheal <= 0 and self.health.value < kit.health:
                self.health.value = min(kit.health, self.health.value+self.pulse*6)
            if base_shield and self.since_hit > 3 and self.antiheal <= 0 and self.shield.value < base_shield:
                self.shield.value = min(base_shield, self.shield.value+self.pulse*15)
            if self.shield_hold <= 0 and self.shield.value > base_shield:
                self.shield.value = max(base_shield, self.shield.value-self.pulse*25)
        player = self.game.session.roster.value[self.slot]
        cmd = self.arena.brain.command(self) if player["bot"] else self.controls
        self.yaw, self.pitch = cmd.get("yaw", self.yaw), cmd.get("pitch", self.pitch)
        self.transform.rotation = Quaternion.from_euler_angles(Vec3(0, self.yaw, 0))
        forward = direction(self.yaw)
        right = Vec3(math.cos(self.yaw), 0, math.sin(self.yaw))
        move = forward*cmd.get("z", 0)+right*cmd.get("x", 0)
        speed = kit.speed*(1.3 if cmd.get("sprint") and not self.zoom and not self.front else 1)
        if self.slow > 0:
            speed *= 1-self.slow_factor
        if self.haste > 0:
            speed *= 1.3
        if self.zoom:
            speed *= .6
        speed *= self.kit_speed()
        self.zone_effects(dt)
        for zone in self.arena.zones:
            if zone["kind"] in ("biofilm", "mature") and math.dist(self.feet, zone["pos"]) < zone["radius"]+.4:
                source = self.arena.actors.get(zone["owner"])
                friendly = source is not None and source.team == self.team
                speed *= 1.25 if friendly else .6
        if self.root > 0:
            self.dash = self.grapple = 0
        if self.dash > 0 and self.dash_dir is not None:
            self.body.velocity = self.dash_dir
            self.dash_hits()
        elif self.stagger > 0:
            pass  # knocked back: keep the impulse instead of steering
        else:
            self.controller.move_speed = speed
            self.controller.jump_height = kit.jump_height
            self.controller.move(move if speed > 0 else Vec3(0, 0, 0))
        if self.leap:
            self.leap += dt
        if self.leap > .3 and self.controller.is_grounded:
            self.leap = 0
            self.area_damage(4, 50, knock=6)
            self.arena.effect('slam', self.feet, 4)
        if cmd.get("jump") and not self.previous.get("jump") and self.root <= 0:
            self.controller.jump()
        if cmd.get("reload"):
            self.weapon.reload()
        self.handle_input(cmd, dt)
        if cmd.get("interact") and not self.previous.get("interact"):
            self.interact()
        self.update_build(cmd.get("build", False), dt)
        self.kit_update(dt)
        # Charge for escorting: cells near the platelets while the wound is open.
        if self.team == CELLS and not self.arena.state.wound_closed:
            head = self.arena.path.at(self.arena.state.escort)
            if math.dist(head, self.feet) < 7:
                self.gain(dt*BALANCE['charge_escort'])
        self.previous = cmd.copy()
        if self.transform.y < -10:
            self.body.teleport(self.arena.spawn_position(self.slot, self.spawn_options()[0] if self.spawn_options() else ('entrance', None)) or Vec3(0, 2, 60))

    def zone_effects(self, dt):
        """Dano/efeitos de zonas inimigas sobre este heroi (roda no dono), em pulsos de 0,25 s
        para nao regravar a vida (variavel de rede) a cada quadro."""
        self.zone_tick = getattr(self, 'zone_tick', 0.0)+dt
        if self.zone_tick < .25:
            return
        dt, self.zone_tick = self.zone_tick, 0.0
        for zone in self.arena.zones:
            if not self.touches_zone(zone):
                continue
            source = self.arena.actors.get(zone["owner"])
            if source is None or source.team == self.team:
                continue
            kind = zone["kind"]
            if kind == "mature":
                self.damage(dt*14, source)
            elif kind == "acid":
                self.damage(dt*10, source)
            elif kind == "cloud":
                self.damage(dt*12, source)
            elif kind == "rain":
                self.damage(dt*22, source)
                if self.marked < .5:
                    self.marked = 1.5
                    self.arena.mark_actor(self.slot, 1.5)

    def in_zone(self, kind, enemy=False):
        for zone in self.arena.zones:
            if zone["kind"] != kind:
                continue
            source = self.arena.actors.get(zone["owner"])
            if enemy and source is not None and source.team == self.team:
                continue
            if self.touches_zone(zone):
                return True
        return False

    BODY_RADIUS, BODY_HALF = .45, .5  # capsula do heroi: raio e meia-altura do segmento central

    def touches_zone(self, zone):
        """Zona no chao: pes dentro do raio. Zona colada numa superficie (``normal``): a capsula
        do heroi encosta no disco - vale para rampas, paredes e tetos."""
        normal = zone.get("normal")
        if normal is None:
            return math.dist(self.feet, zone["pos"]) < zone["radius"]
        p = self.transform.position
        cx, cy, cz = zone["pos"]
        nx, ny, nz = normal
        best = None
        for i in range(7):
            y = p.y-self.BODY_HALF+2*self.BODY_HALF*i/6
            dx, dy, dz = p.x-cx, y-cy, p.z-cz
            dn = dx*nx+dy*ny+dz*nz
            px, py, pz = dx-nx*dn, dy-ny*dn, dz-nz*dn
            out = max(0.0, math.sqrt(px*px+py*py+pz*pz)-zone["radius"])
            d = math.hypot(dn, out)
            best = d if best is None else min(best, d)
        return best <= self.BODY_RADIUS+.1

    # -- construcao e entrega (bacterias, tecla G) ----------------------------
    def build_target(self):
        """Ground point in front of the bacterium, with validity reason."""
        state = self.arena.state
        aim = direction(self.yaw, min(self.pitch, -.35))
        origin = self.transform.position+Vec3(0, EYE, 0)
        hit = self.game.physics_world.raycast(origin, aim, 6.5, 1)
        if hit is None:
            ahead = origin+direction(self.yaw)*2.5
            hit = self.game.physics_world.raycast(ahead, Vec3(0, -1, 0), 4, 1)
        if hit is None:
            return None, "Sem chao valido"
        point = hit.point
        problem = state.build_problem(self.slot, state.resources.get(self.slot, 0))
        if not problem:
            problem = self.arena.placement_problem((point.x, point.y, point.z), hit.normal, self.slot)
        return (point.x, point.y, point.z), problem

    def deliverable(self):
        """Colonia proxima que pode receber recursos agora (para o toque em G)."""
        if self.team == CELLS or self.arena.state.resources.get(self.slot, 0) <= 0:
            return None
        colony = self.arena.nearest_colony(self.feet, 3.5)
        if colony and colony['dev'] < BALANCE['colony_dev_cap']:
            return colony
        return None

    def update_build(self, held, dt):
        if held and not self.previous.get("build") and self.deliverable():
            # Toque em G perto de uma colonia: entrega em vez de construir.
            self.interact()
            self.deliver_hold = True
        if self.deliver_hold:
            if not held:
                self.deliver_hold = False
            held = False
        if self.team == CELLS or not held:
            if self.build and not held:
                self.build_problem = "Construcao cancelada"
            self.build = None
            self.preview = None
            return
        point, problem = self.build_target()
        self.preview, self.build_problem = point, problem
        if self.build is None:
            if point is None or problem:
                return
            self.build = dict(pos=point, progress=0.0)
            self.arena.building(self.slot, point, True)
        pos = self.build['pos']
        if math.dist(pos, self.feet) > BALANCE['colony_build_radius']+2.5:
            self.build = None
            self.build_problem = "Fique perto da construcao"
            self.arena.building(self.slot, pos, False)
            return
        self.build['progress'] += dt
        if self.build['progress'] >= BALANCE['colony_build_time']:
            self.arena.request_build(self.slot, pos)
            self.arena.building(self.slot, pos, False)
            self.gain(BALANCE['charge_build'])
            self.build = None
            self.build_problem = ""

    def interact(self):
        """Entregar recursos numa colonia (bacterias): toque em G ou comando dos bots."""
        if self.team == CELLS:
            return
        colony = self.arena.nearest_colony(self.feet, 3.5)
        if colony:
            self.arena.request_develop(self.slot, colony['id'])

    # -- area -------------------------------------------------------------------
    def area_damage(self, radius, amount, knock=0.0, effect=None, center=None, exclude=()):
        """``exclude``: atores/ids de lacaio que ja levaram o acerto direto."""
        origin = center is not None
        center = center or self.transform.position
        for other in list(self.arena.actors.values()):
            if other.team == self.team or not other.alive or any(other is e for e in exclude):
                continue
            d = other.transform.position-center
            visible = (self.arena.clear_line(center.to_tuple, (other.transform.position+Vec3(0, .3, 0)).to_tuple)
                       if origin else self.arena.visible(self, other))
            if d.magnitude() <= radius and visible:
                fx = dict(effect or {})
                if knock:
                    flat = Vec3(d.x, 0, d.z)
                    flat = flat.normalize() if flat.magnitude() > .01 else direction(self.yaw)
                    fx['knock'] = (flat.x*knock, 4.5, flat.z*knock)
                other.damage(amount, self, fx)
        for ident, m in list(self.arena.minions.items()):
            owner = self.arena.actors.get(m['slot'])
            if owner is not None and owner.team != self.team and ident not in exclude and \
                    math.dist(m['pos'], (center.x, center.y-.5, center.z)) <= radius+.5:
                self.arena.damage_minion(ident, amount, self.slot)
        if self.team == CELLS:
            for colony in list(self.arena.state.colonies):
                if math.dist(colony['pos'], (center.x, center.y-.95, center.z)) <= radius+1:
                    self.arena.hit_colony(self.slot, colony['id'], amount)

    def zone(self, kind, radius, life, position=None, follow=False, normal=None):
        position = position or self.feet
        self.arena.add_zone(kind, position, radius, life, self.slot, follow, normal)


def load_combatant(game, arena, slot, player):
    item = game.CreateItem()
    item.name = f"Combatant {slot} / {player['hero']}"
    actor = item.AddComponent(Combatant(arena, slot, player["hero"], player["team"], player["owner"]))
    item.transform.position = arena.spawn_position(slot, ('base', None) if player["team"] == CELLS else ('entrance', None))
    item.AddComponent(PhysicsBody3D(CapsuleShape(.45, 1), mass=80, lock_rotation=True,
                                   allow_sleep=False, friction=0,
                                   body_type=BodyType.DYNAMIC if actor.local else BodyType.KINEMATIC,
                                   collision_group=2 if player["team"] == CELLS else 4))
    item.AddComponent(CharacterController3D(jump_height=HEROES[player['hero']].jump_height))
    item.AddComponent(Weapon(actor))
    item.AddComponent(CombatantVisual(actor))
    item.AddComponent(NetworkTransform(
        identifier=100_000 + slot, owner=player["owner"], sync_frequency=1/30,
        sync_scale_x=False, sync_scale_y=False, sync_scale_z=False,
        interpolation_speed=22,
    ))
    return actor
