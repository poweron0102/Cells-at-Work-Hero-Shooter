"""Shared objectives and combat effects, expressed as gameplay RPCs."""
from EasyCells3D.NetworkComponents import NetworkComponent, Rpc, SendTo, Protocol
from EasyCells3D.Geometry import Vec3
from EasyCells3D.PhysicsComponents3D import PhysicsBody3D, BodyType, SphereShape
from .rules import MatchState
from .catalog import POINTS, CORE_POSITIONS, CELLS, HEROES
from .bots import BotBrain
from .director import StressDirector
from .layout import SPAWN_Z


class Arena(NetworkComponent):
    def __init__(self):
        super().__init__(identifier=200, owner=0)
        self.state = MatchState()
        self.actors = {}
        self.samples, self.zones, self.tracers = [], [], []
        self.core_bodies = []
        self.brain = BotBrain(self)
        self.director = StressDirector(self)
        self.clock = self.finish_timer = 0
        self.ready = False

    def init(self):
        super().init()
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
        return next((a for a in self.actors.values() if a.body is body and a.alive), None)

    def visible(self, actor, target):
        start = actor.transform.position + Vec3(0, .5, 0)
        delta = target.transform.position+Vec3(0, .3, 0)-start
        return self.game.physics_world.raycast(start, delta, delta.magnitude(), 1) is None

    def collect(self, actor, radius=2.8):
        if actor.team != CELLS or self.state.phase == 0:
            return
        samples = []
        for sample in self.samples:
            delta = Vec3(*sample["pos"])-actor.transform.position
            if delta.magnitude() <= radius and self.game.physics_world.raycast(actor.transform.position, delta, delta.magnitude(), 1) is None:
                samples.append(sample["id"])
        if samples:
            self.take_samples(samples, 25 if actor.hero == "macrophage" else 8)

    @Rpc(send_to=SendTo.ALL, require_owner=False)
    def take_samples(self, ids, antigen):
        for sample in list(self.samples):
            if sample["id"] in ids:
                self.samples.remove(sample)
                self.state.antigen(antigen)
                self.state.stress = max(0, self.state.stress-2)

    def plant(self, actor):
        if self.state.phase < 1:
            return
        for i, (x, z) in enumerate(CORE_POSITIONS):
            if (actor.transform.position-Vec3(x, 1, z)).magnitude() < 6:
                self.reinforce_core(i)
                actor.zone("biofilm", 4, 12)
                break

    @Rpc(send_to=SendTo.ALL, require_owner=False)
    def reinforce_core(self, index):
        if self.state.cores[index] > 0:
            self.state.cores[index] = min(360, self.state.cores[index]+90)

    @Rpc(send_to=SendTo.ALL, require_owner=False)
    def damage_core(self, index, amount):
        if self.state.phase < 1 or self.state.cores[index] <= 0:
            return
        self.state.cores[index] = max(0, self.state.cores[index]-amount)
        if self.state.cores[index] == 0:
            self.state.antigen(20)
            self.state.stress = max(0, self.state.stress-8)
            self.state.announce("NUCLEO DESTRUIDO - foco de infeccao eliminado")

    @Rpc(send_to=SendTo.ALL, require_owner=False)
    def eliminated(self, victim, source, death, position):
        target, attacker = self.actors[victim], self.actors[source]
        if target.team != CELLS:
            self.samples.append(dict(id=(victim, death), pos=position, life=24))
        self.state.announce(f"{HEROES[attacker.hero].name} eliminou {HEROES[target.hero].name}")

    @Rpc(send_to=SendTo.ALL, require_owner=False)
    def response_started(self):
        self.state.response()

    @Rpc(send_to=SendTo.NOT_ME, require_owner=False)
    def add_zone(self, kind, position, radius, life, owner):
        self.zones.append(dict(kind=kind, pos=position, radius=radius, life=life, owner=owner))

    @Rpc(send_to=SendTo.NOT_ME, require_owner=False, protocol=Protocol.UDP)
    def trace(self, start, end):
        self.tracers.append(dict(a=start, b=end, life=.1))

    @Rpc(send_to=SendTo.ALL)
    def advance_objectives(self, dt, presence):
        # Clock increments, not snapshots: every tick contributes to the objectives.
        self.state.tick(dt, presence)
        self.director.tick(dt)
        for i, body in enumerate(self.core_bodies):
            body.enable = self.state.phase >= 1 and self.state.cores[i] > 0
        for collection in (self.samples, self.zones):
            for value in list(collection):
                value["life"] -= dt
                if value["life"] <= 0:
                    collection.remove(value)

    def loop(self):
        session = self.game.session
        if not self.ready:
            self.ready = True
            session.ready(session.manager.id)
        dt = min(.05, self.game.delta_time)
        for shot in list(self.tracers):
            shot["life"] -= dt
            if shot["life"] <= 0:
                self.tracers.remove(shot)
        if session.status != "playing" or not session.manager.is_server:
            return
        self.clock += dt
        if self.clock >= .1:
            presence = []
            for x, z in POINTS:
                nearby = [a for a in self.actors.values() if a.alive and (a.transform.position-Vec3(x, 1, z)).magnitude() < 3.2]
                presence.append((sum(a.team == CELLS for a in nearby), sum(a.team != CELLS for a in nearby)))
            self.advance_objectives(self.clock, presence)
            self.clock = 0
        if self.state.winner:
            self.finish_timer += dt
            if self.finish_timer > 2:
                session.finish(dict(state=self.state.serialize(), actors={
                    slot: dict(kills=a.kills.value, deaths=a.deaths.value) for slot, a in self.actors.items()}))

    def on_destroy(self):
        if getattr(self.game, "session", None):
            self.game.session.arena = None
        super().on_destroy()
