"""Combatant lifecycle and hero abilities, attached to each Item."""
import math
from EasyCells3D.Components import Component
from EasyCells3D.NetworkComponents import NetworkTransform
from EasyCells3D.Geometry import Vec3
from EasyCells3D.PhysicsComponents3D import PhysicsBody3D, CharacterController3D, CapsuleShape, BodyType
from .catalog import HEROES, CELLS, CORE_POSITIONS
from .combat import Weapon, direction
from .visuals import CombatantVisual
from .network import TRANSFORM_ID_BASE


class Combatant(Component):
    def __init__(self, arena, slot, hero, team):
        self.arena, self.slot, self.hero, self.team = arena, slot, hero, team
        self.health = HEROES[hero].health
        self.shield = 70 if hero == "pneumococcus" else 0
        self.alive = True
        self.respawn = 0
        self.yaw = 0 if team == CELLS else math.pi
        self.pitch = 0
        self.ability_cd = self.secondary_cd = self.special_cd = 0
        self.boost = self.harden = self.dash = self.reveal = self.neutralized = 0
        self.since_hit = 10
        self.hit_marker = self.hurt = 0
        self.kills = self.deaths = self.shot = 0
        self.previous = {}

    def init(self):
        self.body = self.GetComponent(PhysicsBody3D)
        self.controller = self.GetComponent(CharacterController3D)
        self.weapon = self.GetComponent(Weapon)

    def damage(self, amount, source):
        if not self.alive or source.team == self.team:
            return
        if self.harden > 0 and self.neutralized <= 0:
            amount *= .5
        absorbed = min(self.shield, amount)
        self.shield -= absorbed
        self.health = max(0, self.health - amount + absorbed)
        self.since_hit, self.hurt = 0, .25
        if self.health <= 0:
            self.alive = False
            self.respawn = 6
            self.deaths += 1
            source.kills += 1
            self.body.enable = False
            if self.team != CELLS:
                self.arena.samples.append(dict(pos=self.transform.position.to_tuple, life=24))
            self.arena.state.announce(f"{HEROES[source.hero].name} eliminou {HEROES[self.hero].name}")
            if source.hero == "streptococcus" and source.boost > 0:
                source.ability_cd = 0

    def spawn(self):
        self.hero = self.game.session.roster[self.slot]["hero"]
        self.health, self.alive = HEROES[self.hero].health, True
        self.shield = 70 if self.hero == "pneumococcus" else 0
        self.ability_cd = self.secondary_cd = self.special_cd = 0
        self.boost = self.harden = self.dash = self.reveal = self.neutralized = 0
        self.previous = {}
        self.weapon.ammo = HEROES[self.hero].magazine
        self.weapon.timer = self.weapon.reload_time = 0
        self.body.enable = True
        self.body.teleport(self.arena.spawn_position(self.slot))

    def loop(self):
        if not self.arena.authority:
            return
        dt = min(.05, self.game.delta_time)
        for key in ("ability_cd", "secondary_cd", "special_cd", "boost", "harden", "dash", "reveal", "neutralized", "hit_marker", "hurt"):
            setattr(self, key, max(0, getattr(self, key)-dt))
        if not self.alive:
            self.respawn -= dt
            if self.respawn <= 0:
                self.spawn()
            return
        self.since_hit += dt
        if self.since_hit > 5 and self.arena.state.event != "fever":
            self.health = min(HEROES[self.hero].health, self.health+dt*5)
            if self.hero == "pneumococcus" and self.neutralized <= 0:
                self.shield = min(70, self.shield+dt*12)
        player = self.game.session.roster[self.slot]
        cmd = self.arena.bot_command(self) if player["bot"] else self.game.session.command(self.slot)
        self.yaw, self.pitch = cmd.get("yaw", self.yaw), cmd.get("pitch", self.pitch)
        forward = direction(self.yaw)
        right = Vec3(math.cos(self.yaw), 0, math.sin(self.yaw))
        move = forward*cmd.get("z", 0)+right*cmd.get("x", 0)
        speed = HEROES[self.hero].speed*(1.35 if cmd.get("sprint") else 1)
        for zone in self.arena.zones:
            if (self.transform.position-Vec3(*zone["pos"])).magnitude() < zone["radius"]:
                if zone["kind"] == "biofilm":
                    speed *= .65 if self.team == CELLS else 1.2
                elif zone["kind"] == "acid":
                    source = self.arena.actors[zone["owner"]]
                    if source.team != self.team:
                        self.damage(dt*10, source)
        if self.arena.state.event == "inflammation" and self.arena.state.event_time > 0 and abs(self.transform.x) < 10:
            speed *= .72
        if self.dash > 0:
            speed, move = 22, forward
        self.controller.move_speed = speed
        self.controller.jump_height = HEROES[self.hero].jump_height
        self.controller.move(move)
        if self.arena.state.event == "blood_flow" and self.arena.state.event_time > 0 and abs(self.transform.x) > 15:
            self.body.velocity = self.body.velocity + Vec3(0, 0, 3.2)
        if cmd.get("jump") and not self.previous.get("jump"):
            self.controller.jump()
        if cmd.get("reload"):
            self.weapon.reload()
        if cmd.get("fire") and (self.hero != "b_cell" or not self.previous.get("fire")):
            self.weapon.fire()
        if cmd.get("secondary"):
            self.secondary()
        if cmd.get("ability"):
            self.ability()
        if cmd.get("ultimate"):
            self.ultimate()
        if cmd.get("interact"):
            self.arena.collect(self)
        self.previous = cmd.copy()
        if self.transform.y < -8:
            self.body.teleport(self.arena.spawn_position(self.slot))

    def secondary(self):
        if self.team == CELLS:
            self.weapon.melee()
            return
        if self.secondary_cd > 0:
            return
        self.secondary_cd = 8
        if self.hero == "pneumococcus":
            self.dash = .3
        elif self.hero == "staphylococcus":
            nearby = any((self.transform.position-Vec3(x, 1, z)).magnitude() < 8 and self.arena.state.cores[i] > 0 for i, (x, z) in enumerate(CORE_POSITIONS))
            self.shield = min(120, self.shield + (100 if nearby else 30))
        else:
            self.area_damage(4, 45)
            if self.hero == "streptococcus":
                self.health = min(HEROES[self.hero].health, self.health+35)

    def ability(self):
        if self.ability_cd > 0 or self.neutralized > 0:
            return
        self.ability_cd = 9
        if self.hero in ("neutrophil", "killer_t", "streptococcus"):
            self.dash = .26
            self.area_damage(3, 35)
            if self.hero == "neutrophil":
                self.reveal = 5
            if self.hero == "streptococcus":
                self.ability_cd = 5
        elif self.hero == "macrophage":
            self.reveal = 7
            self.arena.collect(self, 6)
        elif self.hero == "b_cell":
            self.area_damage(7, 30, neutralize=True)
        elif self.hero == "pneumococcus":
            self.harden = 4
        elif self.hero == "staphylococcus":
            self.arena.plant(self)
        elif self.hero == "pseudomonas":
            self.zone("biofilm", 5, 12)

    def zone(self, kind, radius, life):
        self.arena.zones.append(dict(kind=kind, pos=self.transform.position.to_tuple, radius=radius, life=life))

    def area_damage(self, radius, amount, neutralize=False):
        for body in self.game.physics_world.overlap_sphere(self.transform.position, radius, 4 if self.team == CELLS else 2):
            target = self.arena.actor_for_body(body)
            if target and self.arena.visible(self, target):
                target.damage(amount, self)
                if neutralize:
                    target.neutralized = 6

    def ultimate(self):
        if self.team == CELLS:
            if not self.arena.state.response():
                return
            if self.hero == "neutrophil":
                for actor in self.arena.actors.values():
                    if actor.team == CELLS:
                        actor.reveal = 9
            elif self.hero == "macrophage":
                self.harden = 10
                self.arena.collect(self, 9)
            elif self.hero == "b_cell":
                self.area_damage(13, 85, True)
                for i, (x, z) in enumerate(CORE_POSITIONS):
                    if (self.transform.position-Vec3(x, 1, z)).magnitude() < 13:
                        self.arena.damage_core(i, 170)
            else:
                self.boost = 10
        elif self.special_cd <= 0:
            self.special_cd = 40
            if self.hero == "pneumococcus":
                self.zone("cloud", 6, 10)
            elif self.hero == "pseudomonas":
                self.zone("biofilm", 9, 18)
            elif self.hero == "staphylococcus":
                self.shield, self.boost = 160, 10
            else:
                self.boost, self.ability_cd = 10, 0


def load_combatant(game, arena, slot, player):
    item = game.CreateItem()
    item.name = f"Combatant {slot} / {player['hero']}"
    item.transform.position = arena.spawn_position(slot)
    actor = item.AddComponent(Combatant(arena, slot, player["hero"], player["team"]))
    item.AddComponent(PhysicsBody3D(CapsuleShape(.45, 1), mass=80, lock_rotation=True,
                                   allow_sleep=False, friction=0,
                                   body_type=BodyType.DYNAMIC if arena.authority else BodyType.KINEMATIC,
                                   collision_group=2 if player["team"] == CELLS else 4))
    item.AddComponent(CharacterController3D(jump_height=HEROES[player['hero']].jump_height))
    item.AddComponent(Weapon(actor))
    item.AddComponent(CombatantVisual(actor))
    item.AddComponent(NetworkTransform(
        identifier=TRANSFORM_ID_BASE + slot, owner=0, sync_frequency=1/30,
        sync_rot_x=False, sync_rot_y=False, sync_rot_z=False,
        sync_scale_x=False, sync_scale_y=False, sync_scale_z=False,
        interpolation_speed=22,
    ))
    return actor
