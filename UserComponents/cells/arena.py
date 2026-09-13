"""Match coordination, replication and living objectives; no rendering loop."""
from EasyCells3D.Components import Component
from EasyCells3D.Geometry import Vec3
from EasyCells3D.PhysicsComponents3D import PhysicsBody3D, BodyType, SphereShape
from .rules import MatchState
from .catalog import POINTS, CORE_POSITIONS, CELLS
from .bots import BotBrain
from .layout import SPAWN_Z

ACTOR_FIELDS = ("hero", "health", "shield", "alive", "respawn", "yaw", "pitch", "ability_cd", "secondary_cd",
                "special_cd", "boost", "harden", "reveal", "neutralized", "hit_marker", "hurt", "kills", "deaths", "shot")


class Arena(Component):
    def __init__(self, authority):
        self.authority = authority
        self.state = MatchState()
        self.actors = {}
        self.samples, self.zones, self.tracers = [], [], []
        self.core_bodies = []
        self.brain = BotBrain(self)
        self.applied_snapshot = None
        self.finish_timer = 0

    def init(self):
        self.game.session.arena = self
        for x, z in CORE_POSITIONS:
            item = self.game.CreateItem()
            item.name = "Colony core"
            item.transform.position = Vec3(x, 1.1, z)
            body = item.AddComponent(PhysicsBody3D(SphereShape(1.1), body_type=BodyType.STATIC, collision_group=8))
            body.enable = False
            self.core_bodies.append(body)

    def spawn_position(self, slot):
        return Vec3((slot % 3-1)*20, 1.05, SPAWN_Z if slot < 3 else -SPAWN_Z)

    def actor_for_body(self, body):
        return next((a for a in self.actors.values() if getattr(a, "body", None) is body and a.alive), None)

    def visible(self, actor, target):
        start = actor.transform.position + Vec3(0, .5, 0)
        delta = target.transform.position+Vec3(0, .3, 0)-start
        return self.game.physics_world.raycast(start, delta, delta.magnitude(), 1) is None

    def bot_command(self, actor):
        return self.brain.command(actor)

    def collect(self, actor, radius=2.8):
        if actor.team != CELLS or self.state.phase == 0:
            return
        for sample in list(self.samples):
            delta = Vec3(*sample["pos"])-actor.transform.position
            if delta.magnitude() <= radius and self.game.physics_world.raycast(actor.transform.position, delta, delta.magnitude(), 1) is None:
                self.samples.remove(sample)
                self.state.antigen(25 if actor.hero == "macrophage" else 8)
                self.state.stress = max(0, self.state.stress-2)

    def plant(self, actor):
        if self.state.phase < 1:
            return
        for i, (x, z) in enumerate(CORE_POSITIONS):
            if (actor.transform.position-Vec3(x, 1, z)).magnitude() < 6:
                if self.state.cores[i] > 0:
                    self.state.cores[i] = min(360, self.state.cores[i]+90)
                actor.zone("biofilm", 4, 12)
                break

    def damage_core(self, index, amount):
        if self.state.phase < 1 or self.state.cores[index] <= 0:
            return
        self.state.cores[index] = max(0, self.state.cores[index]-amount)
        if self.state.cores[index] == 0:
            self.state.antigen(20)
            self.state.stress = max(0, self.state.stress-8)
            self.state.announce("NUCLEO DESTRUIDO - foco de infeccao eliminado")

    def loop(self):
        net = self.game.session
        if not self.authority:
            if net.latest and self.applied_snapshot is not net.latest:
                self.apply(net.latest)
                self.applied_snapshot = net.latest
            return
        dt = min(.05, self.game.delta_time)
        presence = []
        for x, z in POINTS:
            nearby = [a for a in self.actors.values() if a.alive and (a.transform.position-Vec3(x, 1, z)).magnitude() < 3.2]
            presence.append((sum(a.team == CELLS for a in nearby), sum(a.team != CELLS for a in nearby)))
        self.state.tick(dt, presence)
        for i, body in enumerate(self.core_bodies):
            body.enable = self.state.phase >= 1 and self.state.cores[i] > 0
        for collection in (self.samples, self.zones, self.tracers):
            for value in list(collection):
                value["life"] -= dt
                if value["life"] <= 0:
                    collection.remove(value)
        if self.state.winner:
            self.finish_timer += dt
            if self.finish_timer > 2:
                net.latest = self.serialize_state()
                net.status = "results"

    def serialize_state(self):
        actors = {}
        for slot, a in self.actors.items():
            data = {key: getattr(a, key) for key in ACTOR_FIELDS}
            data.update(ammo=getattr(a, "weapon", None).ammo if hasattr(a, "weapon") else 0,
                        reload=a.weapon.reload_time if hasattr(a, "weapon") else 0)
            actors[slot] = data
        return dict(state=self.state.serialize(), actors=actors, samples=self.samples.copy(),
                    zones=self.zones.copy(), tracers=self.tracers.copy())

    def apply(self, snapshot):
        self.state = MatchState(**snapshot["state"])
        self.samples, self.zones, self.tracers = snapshot["samples"], snapshot["zones"], snapshot["tracers"]
        for slot, data in snapshot["actors"].items():
            a = self.actors.get(slot)
            if a is None:
                continue
            for key in ACTOR_FIELDS:
                setattr(a, key, data[key])
            a.body.enable = a.alive
            a.weapon.ammo, a.weapon.reload_time = data["ammo"], data["reload"]
        self.gate.enable = self.state.event == "coagulation" and self.state.event_time > 0
        for i, body in enumerate(self.core_bodies):
            body.enable = self.state.phase >= 1 and self.state.cores[i] > 0

    def on_destroy(self):
        if getattr(self.game, "session", None):
            self.game.session.arena = None
