"""Combatentes: ciclo de vida, kits dos herois, construcao e respawn.

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
from .combat import Weapon, direction, cast, melee_targets, impact_kind, EYE
from .visuals import CombatantVisual
from .layout import in_cells_base

SHIELD_BASE = {"pneumococcus": 70}


class Combatant(NetworkComponent):
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
        self.action = 0.0
        self.fire_serial, self.fire_time, self.fire_kind = 0, -1.0, 'shot'
        self.vm_muzzle = None   # cano no espaço do viewmodel (jogador local em 1ª pessoa)
        self.tp_muzzle = None   # cano da arma na mão do personagem (mundo)

    def reset_kit(self):
        self.ability_cd = self.secondary_cd = 0
        self.charge = 0.0
        self.boost = self.capsule = self.dash = self.reveal = self.marked = 0
        self.slow = self.slow_factor = self.haste = self.guard = self.leap = self.stagger = 0
        self.zoom = False
        self.dash_dir = None
        self.preview = None

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
            amount *= 1.2
        absorbed = min(self.shield.value, amount)
        if absorbed:
            self.absorbed = .4
        self.shield.value -= absorbed
        self.health.value = max(0, self.health.value - amount + absorbed)
        self.since_hit, self.hurt = 0, .25
        if origin:
            self.hurt_from = (self.hurt_from+[(origin[0], origin[1], self.arena.state.elapsed)])[-4:]
        if self.build:
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
            self.stagger = .45
        if effect.get('mark'):
            self.marked = effect['mark']
            self.arena.mark_actor(self.slot, effect['mark'])
        if not self.alive:
            self.die(source)

    def die(self, source):
        self.respawn = BALANCE['respawn_seconds']
        self.waiting = False
        self.deaths.value += 1
        self.build = None
        source.credit_kill()
        self.body.enable = False
        self.arena.eliminated(self.slot, source.slot, self.deaths.value, self.transform.position.to_tuple)

    @Rpc(send_to=SendTo.ALL, require_owner=False)
    def credit_kill(self):
        if self.local:
            self.kills.value += 1
            self.kill_marker = .6
            self.gain(12)

    def gain(self, amount):
        """Special charge from combat and objectives (never from time alone)."""
        if self.alive and self.boost <= 0:
            self.charge = min(100.0, self.charge+amount)

    def apply_hit(self, hit, damage, effect=None):
        """Resolve one hit from this local actor onto whatever the ray found."""
        kind = hit['kind']
        if kind == 'actor':
            target = hit['target']
            if hit.get('head'):
                damage *= 1.5
            target.damage(damage, self, effect)
        elif kind == 'colony':
            self.arena.hit_colony(self.slot, hit['target'], damage*(2.0 if self.hero == 'b_cell' else 1))
            self.gain(damage*BALANCE['charge_per_damage']*.5)
            self.hit_marker = .15
        elif kind == 'rbc':
            self.arena.hit_rbc(self.slot, hit['target'], damage)
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

    @Rpc(send_to=SendTo.ALL, require_owner=False)
    def reveal_enemies(self, seconds):
        self.reveal = max(self.reveal, seconds)

    @Rpc(send_to=SendTo.ALL, require_owner=False)
    def buff(self, kind, seconds):
        if self.local:
            setattr(self, kind, max(getattr(self, kind), seconds))

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
        for key in ("ability_cd", "secondary_cd", "boost", "capsule", "dash", "reveal", "marked", "slow", "haste", "stagger",
                    "guard", "hit_marker", "hurt", "kill_marker", "absorbed"):
            setattr(self, key, max(0, getattr(self, key)-dt))
        self.action = max(0.0, self.action-dt*2.5)
        if not self.alive:
            self.zoom = False
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
        in_cloud = self.in_zone('cloud', enemy=True)
        if self.since_hit > 5:
            if self.health.value < kit.health:
                self.health.value = min(kit.health, self.health.value+dt*6)
            base_shield = SHIELD_BASE.get(self.hero, 0)
            if base_shield and self.marked <= 0 and self.shield.value < base_shield:
                self.shield.value = min(base_shield, self.shield.value+dt*12)
        if self.capsule <= 0 and self.shield.value > SHIELD_BASE.get(self.hero, 0) and self.hero != 'staphylococcus':
            self.shield.value = max(SHIELD_BASE.get(self.hero, 0), self.shield.value-dt*40)
        player = self.game.session.roster.value[self.slot]
        cmd = self.arena.brain.command(self) if player["bot"] else self.controls
        self.yaw, self.pitch = cmd.get("yaw", self.yaw), cmd.get("pitch", self.pitch)
        self.transform.rotation = Quaternion.from_euler_angles(Vec3(0, self.yaw, 0))
        forward = direction(self.yaw)
        right = Vec3(math.cos(self.yaw), 0, math.sin(self.yaw))
        move = forward*cmd.get("z", 0)+right*cmd.get("x", 0)
        speed = kit.speed*(1.3 if cmd.get("sprint") and not self.zoom else 1)
        if self.slow > 0:
            speed *= 1-self.slow_factor
        if self.haste > 0:
            speed *= 1.3
        if self.boost > 0 and self.hero in ('streptococcus', 'killer_t'):
            speed *= 1.3 if self.hero == 'streptococcus' else 1.15
        if self.zoom:
            speed *= .6
        for zone in self.arena.zones:
            if (self.transform.position-Vec3(*zone["pos"])).magnitude() >= zone["radius"]:
                continue
            source = self.arena.actors.get(zone["owner"])
            friendly = source is not None and source.team == self.team
            if zone["kind"] in ("biofilm", "mature"):
                speed *= 1.25 if friendly else .65
                if zone["kind"] == "mature" and not friendly:
                    self.damage(dt*14, source)
            elif zone["kind"] == "acid" and not friendly:
                self.damage(dt*10, source)
            elif zone["kind"] == "cloud" and not friendly:
                self.damage(dt*12, source)
        if self.dash > 0 and self.dash_dir is not None:
            self.body.velocity = self.dash_dir
            self.dash_hits()
        elif self.stagger > 0:
            pass  # knocked back: keep the impulse instead of steering
        else:
            self.controller.move_speed = speed
            self.controller.jump_height = kit.jump_height
            self.controller.move(move)
        if self.leap:
            self.leap += dt
        if self.leap > .3 and self.controller.is_grounded:
            self.leap = 0
            self.area_damage(4, 50, knock=6)
            self.arena.effect('slam', self.feet, 4)
        if cmd.get("jump") and not self.previous.get("jump"):
            self.controller.jump()
        if cmd.get("reload"):
            self.weapon.reload()
        self.zoom = bool(cmd.get("secondary")) and self.hero == 'b_cell'
        if cmd.get("fire") and (self.hero != "b_cell" or not self.previous.get("fire")):
            self.weapon.fire()
        if cmd.get("secondary") and self.hero != 'b_cell':
            self.secondary()
        if cmd.get("ability") and not self.previous.get("ability"):
            self.ability()
        if cmd.get("ultimate") and not self.previous.get("ultimate"):
            self.ultimate()
        if cmd.get("interact") and not self.previous.get("interact"):
            self.interact()
        self.update_build(cmd.get("build", False), dt)
        # Charge for escorting: cells near the platelets while the wound is open.
        if self.team == CELLS and not self.arena.state.wound_closed:
            head = self.arena.path.at(self.arena.state.escort)
            if math.dist(head, self.feet) < 7:
                self.gain(dt*BALANCE['charge_escort'])
        self.previous = cmd.copy()
        if self.transform.y < -10:
            self.body.teleport(self.arena.spawn_position(self.slot, self.spawn_options()[0] if self.spawn_options() else ('entrance', None)) or Vec3(0, 2, 60))

    def in_zone(self, kind, enemy=False):
        for zone in self.arena.zones:
            if zone["kind"] != kind:
                continue
            source = self.arena.actors.get(zone["owner"])
            if enemy and source is not None and source.team == self.team:
                continue
            if (self.transform.position-Vec3(*zone["pos"])).magnitude() < zone["radius"]:
                return True
        return False

    # -- construcao (todas as bacterias) ------------------------------------
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

    def update_build(self, held, dt):
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
        """E: entregar recursos numa colonia (bacterias)."""
        if self.team == CELLS:
            return
        colony = self.arena.nearest_colony(self.feet, 3.5)
        if colony:
            self.arena.request_develop(self.slot, colony['id'])

    # -- kits ---------------------------------------------------------------
    def area_damage(self, radius, amount, knock=0.0, effect=None, center=None):
        center = center or self.transform.position
        for other in list(self.arena.actors.values()):
            if other.team == self.team or not other.alive:
                continue
            d = other.transform.position-center
            if d.magnitude() <= radius and self.arena.visible(self, other):
                fx = dict(effect or {})
                if knock:
                    flat = Vec3(d.x, 0, d.z)
                    flat = flat.normalize() if flat.magnitude() > .01 else direction(self.yaw)
                    fx['knock'] = (flat.x*knock, 4.5, flat.z*knock)
                other.damage(amount, self, fx)
        if self.team == CELLS:
            for colony in list(self.arena.state.colonies):
                if math.dist(colony['pos'], (center.x, center.y-.95, center.z)) <= radius+1:
                    self.arena.hit_colony(self.slot, colony['id'], amount)

    def melee(self, reach, amount, arc=.3, rbc_factor=1.0, execute=None, cooldown=.8, knock=0.0):
        if self.secondary_cd > 0:
            return
        self.secondary_cd = cooldown
        self.action = 1.0
        self.show_action(1.0)
        for kind, target in melee_targets(self, reach, arc, include_rbc=rbc_factor > 1):
            dmg = amount
            if kind == 'actor':
                if execute and target.health.value < HEROES[target.hero].health*execute[0]:
                    dmg = execute[1]
                fx = None
                if knock:
                    d = target.transform.position-self.transform.position
                    flat = Vec3(d.x, 0, d.z).normalize()
                    fx = dict(knock=(flat.x*knock, 3, flat.z*knock))
                target.damage(dmg, self, fx)
            elif kind == 'colony':
                self.arena.hit_colony(self.slot, target, dmg)
                self.hit_marker = .15
            else:
                self.arena.hit_rbc(self.slot, target, dmg*rbc_factor)
                self.hit_marker = .15

    def dash_hits(self):
        if self.hero not in ('neutrophil', 'pneumococcus'):
            return
        hit = getattr(self, 'dash_hit', set())
        for other in self.arena.actors.values():
            if other.team != self.team and other.alive and other.slot not in hit \
                    and (other.transform.position-self.transform.position).magnitude() < 1.8:
                hit.add(other.slot)
                if self.hero == 'neutrophil':
                    other.damage(35, self)
                else:
                    flat = Vec3(self.dash_dir.x, 0, self.dash_dir.z).normalize()
                    other.damage(30, self, dict(knock=(flat.x*10, 4, flat.z*10)))
        self.dash_hit = hit

    def start_dash(self, seconds, speed, vertical=False):
        aim = direction(self.yaw, self.pitch if vertical else 0)
        self.dash_dir = aim*speed
        self.dash = seconds
        self.dash_hit = set()

    def secondary(self):
        h = self.hero
        cd = HEROES[h].secondary_cd
        boosted = self.boost > 0 and h == 'killer_t'
        if h == 'neutrophil':
            self.melee(1.8, 55, cooldown=cd)
        elif h == 'macrophage':
            self.melee(3.0, 80, arc=-.1, cooldown=cd)
        elif h == 'killer_t':
            self.melee(2.2, 95*(1.5 if boosted else 1), execute=(.4, 140*(1.5 if boosted else 1)),
                       cooldown=.35 if boosted else cd, knock=4 if boosted else 0)
        elif h == 'streptococcus':
            self.melee(2.0, 30, arc=.4, rbc_factor=4.0, cooldown=cd*(.6 if self.boost > 0 else 1))
        elif self.secondary_cd <= 0:
            self.secondary_cd = cd
            self.action = 1.0
            self.show_action(1.0)
            if h == 'pneumococcus':
                self.start_dash(.35, 18)
            elif h == 'staphylococcus':
                hits = cast(self, direction(self.yaw, self.pitch), 40)
                if hits:
                    self.arena.tracer((self.transform.position+Vec3(0, EYE, 0)).to_tuple, hits[0]['point'].to_tuple, 'sticky',
                                      self.slot, impact_kind(hits))
                    self.apply_hit(hits[0], 35, dict(slow=(.4, 2.5)))
            elif h == 'pseudomonas':
                hits = cast(self, direction(self.yaw, self.pitch), 35)
                end = hits[0]['point'] if hits else self.transform.position+direction(self.yaw, self.pitch)*35
                self.arena.tracer((self.transform.position+Vec3(0, EYE, 0)).to_tuple, end.to_tuple, 'acid', self.slot,
                                  impact_kind(hits) or 'world')
                self.arena.effect('burst', end.to_tuple, 3.5)
                self.area_damage(3.5, 45, center=end)
                for ident, cell in self.arena.rbc_view.cells.items():
                    if cell['state'] not in ('dead', 'inside') and math.dist(cell['pos'], end.to_tuple) < 3.5:
                        self.arena.hit_rbc(self.slot, ident, 45)

    def ability(self):
        h = self.hero
        if self.ability_cd > 0:
            return
        kit = HEROES[h]
        cd = kit.ability_cd*(.5 if h == 'streptococcus' and self.boost > 0 else 1)
        if h == 'neutrophil':
            self.start_dash(.26, 22)
        elif h == 'macrophage':
            self.area_damage(5, 40, knock=9)
            self.arena.effect('slam', self.feet, 5)
        elif h == 'b_cell':
            hits = cast(self, direction(self.yaw, self.pitch), 60)
            if hits:
                self.arena.tracer((self.transform.position+Vec3(0, EYE, 0)).to_tuple, hits[0]['point'].to_tuple, 'mark',
                                  self.slot, impact_kind(hits))
                if hits[0]['kind'] == 'colony':
                    self.arena.mark_colony(hits[0]['target'], 8)
                self.apply_hit(hits[0], 20, dict(mark=6))
        elif h == 'killer_t':
            aim = direction(self.yaw)
            self.body.velocity = Vec3(aim.x*12, 8.5, aim.z*12)
            self.leap = .01
        elif h == 'pneumococcus':
            self.capsule = 5
            self.shield.value = min(SHIELD_BASE['pneumococcus']+120, self.shield.value+120)
        elif h == 'staphylococcus':
            colony = self.arena.nearest_colony(self.feet, 6)
            if not colony:
                return
            self.arena.repair_colony(self.slot, colony['id'], 120)
        elif h == 'pseudomonas':
            self.zone("biofilm", 5, 12)
        elif h == 'streptococcus':
            self.start_dash(.22, 24, vertical=True)
        self.ability_cd = cd
        self.action = .6

    def ultimate(self):
        if self.charge < 100 or self.arena.state.winner:
            return
        self.charge = 0
        h = self.hero
        self.arena.effect('ult', self.feet, 3, h)
        if h == 'neutrophil':
            for other in self.arena.actors.values():
                if other.team != self.team and other.alive and (other.transform.position-self.transform.position).magnitude() < 22:
                    other.damage(0, self, dict(mark=8))
                elif other.team == self.team and (other.transform.position-self.transform.position).magnitude() < 15:
                    other.buff('haste', 6)
            for other in self.arena.actors.values():
                if other.team == self.team:
                    other.reveal_enemies(8)
        elif h == 'macrophage':
            for other in self.arena.actors.values():
                if other.team == self.team and other.alive and (other.transform.position-self.transform.position).magnitude() < 10:
                    other.buff('guard', 6)
        elif h == 'b_cell':
            hits = cast(self, direction(self.yaw, self.pitch), 70, through=True)
            origin = self.transform.position+Vec3(0, EYE, 0)
            end = hits[-1]['point'] if hits else origin+direction(self.yaw, self.pitch)*70
            self.arena.tracer(origin.to_tuple, end.to_tuple, 'beam', self.slot, 'world' if hits else None)
            for hit in hits:
                if hit['kind'] == 'colony':
                    self.arena.hit_colony(self.slot, hit['target'], 260)
                elif hit['kind'] == 'actor':
                    hit['target'].damage(110, self)
        elif h in ('killer_t', 'streptococcus'):
            self.boost = 8
            if h == 'streptococcus':
                self.ability_cd = 0
        elif h == 'pneumococcus':
            self.zone("cloud", 7, 10)
        elif h == 'pseudomonas':
            self.zone("mature", 9, 14)
        elif h == 'staphylococcus':
            self.arena.fortify(self.slot, self.feet, 15, 10)
            self.shield.value = min(160, self.shield.value+80)
            self.boost = 6

    def zone(self, kind, radius, life, position=None):
        position = position or self.transform.position.to_tuple
        self.arena.add_zone(kind, position, radius, life, self.slot)


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
