"""The player fires and resolves hits using local engine physics queries."""
import math
import random
from EasyCells3D.Components import Component
from EasyCells3D.Geometry import Vec3
from .catalog import HEROES, CELLS


def direction(yaw, pitch=0):
    return Vec3(math.sin(yaw)*math.cos(pitch), math.sin(pitch), -math.cos(yaw)*math.cos(pitch))


class Weapon(Component):
    def __init__(self, actor):
        self.actor = actor
        self.timer = 0
        self.reload_time = 0
        self.ammo = HEROES[actor.hero].magazine
        self.rng = random.Random(actor.slot + 12)
        self.last_target = None
        self.lock_hits = 0
        self.burst = 0

    def loop(self):
        a = self.actor
        if not a.local or not a.alive:
            return
        dt = min(.05, self.game.delta_time)
        self.timer = max(0, self.timer - dt)
        if self.reload_time > 0:
            self.reload_time = max(0, self.reload_time-dt)
            if not self.reload_time:
                self.ammo = HEROES[a.hero].magazine

    def reload(self):
        if not self.reload_time and self.ammo < HEROES[self.actor.hero].magazine:
            self.reload_time = 1.6

    def fire(self):
        a = self.actor
        if self.timer > 0 or self.reload_time > 0 or not a.alive:
            return
        if self.ammo <= 0:
            self.reload()
            return
        kit = HEROES[a.hero]
        self.timer = kit.interval
        if a.hero == "killer_t":
            self.burst = (self.burst+1) % 3
            self.timer = .09 if self.burst else .4
        self.ammo -= 1
        a.shot += 1
        pellets = 7 if a.hero == "macrophage" else 1
        for _ in range(pellets):
            spread = .09 if pellets > 1 else .008
            aim = direction(a.yaw + self.rng.uniform(-spread, spread), a.pitch + self.rng.uniform(-spread, spread))
            origin = a.transform.position + Vec3(0, .56, 0)
            mask = 1 | (4 | 8 if a.team == CELLS else 2)
            hit = self.game.physics_world.raycast(origin, aim, 55 if pellets == 1 else 18, mask)
            endpoint = hit.point if hit else origin + aim*45
            if hit and a.hero == "pseudomonas":
                a.arena.zones.append(dict(kind="acid", pos=endpoint.to_tuple, radius=1.4, life=2, owner=a.slot))
                a.arena.add_zone("acid", endpoint.to_tuple, 1.4, 2, a.slot)
            a.arena.tracers.append(dict(a=origin.to_tuple, b=endpoint.to_tuple, life=.1))
            a.arena.trace(origin.to_tuple, endpoint.to_tuple)
            if not hit or not hit.body:
                continue
            target = a.arena.actor_for_body(hit.body)
            damage = kit.damage * (1.4 if a.boost > 0 else 1)
            if target:
                if hit.point.y > target.transform.y + .4:
                    damage *= 1.5
                if a.hero == "b_cell":
                    self.lock_hits = self.lock_hits + 1 if self.last_target == target.slot else 1
                    self.last_target = target.slot
                    damage *= min(1.5, 1 + self.lock_hits*.08)
                if a.hero == "pseudomonas" and target.health.value < HEROES[target.hero].health*.5:
                    damage *= 1.3
                target.damage(damage, a)
                a.hit_marker = .15
            elif a.team == CELLS:
                for i, body in enumerate(a.arena.core_bodies):
                    if hit.body is body:
                        a.arena.damage_core(i, damage*(2.2 if a.hero == "b_cell" else 1))
                        a.hit_marker = .15

    def melee(self):
        a = self.actor
        if self.timer > 0:
            return
        self.timer = .8
        aim = direction(a.yaw)
        for body in self.game.physics_world.overlap_sphere(a.transform.position+aim, 1.7, 4 if a.team == CELLS else 2):
            target = a.arena.actor_for_body(body)
            if target and a.arena.visible(a, target):
                damage = 90 if a.hero == "macrophage" else 65
                if a.hero == "killer_t" and target.health.value < 80:
                    damage = 120
                target.damage(damage, a)
                a.hit_marker = .15
