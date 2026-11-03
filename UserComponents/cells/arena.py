"""Objetivos compartilhados: o servidor simula e replica um snapshot (10 Hz).

Pedidos dos jogadores (construir, desenvolver, danificar colonia, ferir hemacia)
chegam por RPC ao servidor, que valida antes de alterar o estado. Assim nao ha
gastos, coletas ou recompensas duplicadas entre host e clientes.
"""
import math
from EasyCells3D.NetworkComponents import NetworkComponent, Rpc, SendTo, Protocol
from EasyCells3D.Geometry import Vec3
from EasyCells3D.PhysicsComponents3D import PhysicsBody3D, BodyType, SphereShape
from .rules import MatchState, EscortPath, escort_blockers
from .catalog import CELLS, BACTERIA, HEROES, BALANCE
from .bots import BotBrain
from .npcs import Hemacias, RemoteHemacias
from .layout import (CELL_SPAWNS, BACTERIA_ENTRANCE, ESCORT_PATH, RECON, COLONY_HINTS, in_cells_base)


class Arena(NetworkComponent):
    def __init__(self):
        super().__init__(identifier=200, owner=0)
        self.path = EscortPath(ESCORT_PATH)
        self.state = MatchState(escort_total=self.path.total)
        self.actors = {}
        self.zones, self.tracers, self.effects = [], [], []
        self.drops = []
        self.next_drop = 1
        self.builds = {}  # slot -> position of a construction in progress (visual)
        self.colony_bodies = {}
        self.brain = BotBrain(self)
        self.rbc_view = RemoteHemacias()
        self.hemacias = None
        self.clock = self.finish_timer = 0
        self.sync_clock = 0
        self.ready = False
        self.navigator = None

    @property
    def server(self):
        return self.game.session.manager.is_server

    def init(self):
        super().init()
        self.game.session.arena = self
        if self.server:
            self.hemacias = Hemacias(self)

    # -- consultas --------------------------------------------------------
    def spawn_options(self):
        options = []
        if not self.state.wound_closed:
            options.append(('entrance', None))
        for colony in self.state.colonies:
            options.append(('colony', colony['id']))
        return options

    def spawn_position(self, slot, choice):
        kind, ident = choice
        if kind == 'base':
            x, y, z = CELL_SPAWNS[slot % 3]
        elif kind == 'entrance':
            x, y, z = BACTERIA_ENTRANCE[slot % 3]
        else:
            colony = self.state.colony(ident)
            if colony is None:
                return None
            a = (slot % 3)*2.1+.6
            x, y, z = colony['pos'][0]+math.cos(a)*1.8, colony['pos'][1]+.2, colony['pos'][2]+math.sin(a)*1.8
        return Vec3(x, y+1.05, z)

    def actor_for_body(self, body):
        return next((a for a in self.actors.values() if a.body is body and a.alive), None)

    def colony_for_body(self, body):
        if body is None:
            return None
        return next((cid for cid, b in self.colony_bodies.items() if b is body), None)

    def visible(self, actor, target):
        start = actor.transform.position + Vec3(0, .5, 0)
        delta = target.transform.position+Vec3(0, .3, 0)-start
        return self.game.physics_world.raycast(start, delta, delta.magnitude(), 1) is None

    def clear_line(self, a, b):
        start = Vec3(*a)
        delta = Vec3(*b)-start
        dist = delta.magnitude()
        return dist < .01 or self.game.physics_world.raycast(start, delta, dist, 1) is None

    def nearest_colony(self, feet, radius):
        best = None
        for colony in self.state.colonies:
            d = math.dist(colony['pos'], feet)
            if d <= radius and (best is None or d < best[0]):
                best = (d, colony)
        return best[1] if best else None

    def placement_problem(self, point, normal, slot=None):
        x, y, z = point
        if normal.y < .8:
            return "Chao inclinado demais"
        if in_cells_base(x, z):
            return "Proibido na base das celulas"
        if any(math.dist(c['pos'], point) < 4.5 for c in self.state.colonies):
            return "Muito perto de outra colonia"
        if any(math.dist(p, point) < 4.5 for s, p in self.builds.items() if s != slot):
            return "Outra construcao em andamento"
        if math.dist(point, self.path.at(self.state.escort)) < 3:
            return "Sobre a escolta"
        world = self.game.physics_world
        if world.overlap_sphere(Vec3(x, y+1.2, z), .95, 1):
            return "Sem espaco livre"
        return ""

    # -- snapshot -----------------------------------------------------------
    def snapshot(self):
        return dict(state=self.state.snapshot(), rbc=self.hemacias.snapshot() if self.hemacias else [],
                    drops=[dict(d) for d in self.drops], builds={s: list(p) for s, p in self.builds.items()})

    @Rpc(send_to=SendTo.CLIENTS)
    def sync(self, data):
        self.apply_snapshot(data)

    def apply_snapshot(self, data):
        self.state.apply(data['state'])
        self.rbc_view.apply(data['rbc'])
        self.drops = [dict(d) for d in data['drops']]
        self.builds = {int(s): tuple(p) for s, p in data.get('builds', {}).items()}

    # -- pedidos (servidor) ---------------------------------------------------
    @Rpc(send_to=SendTo.SERVER, require_owner=False)
    def request_build(self, slot, position):
        actor = self.actors.get(slot)
        if actor is None or actor.team == CELLS or not actor.alive:
            return
        if math.dist(actor.feet, position) > BALANCE['colony_build_radius']+3:
            return
        position = tuple(position)
        from .layout import in_cells_base as forbidden
        if forbidden(position[0], position[2]) or any(math.dist(c['pos'], position) < 4.5 for c in self.state.colonies):
            return
        self.builds.pop(slot, None)
        if self.state.add_colony(slot, position):
            self.reward(slot, 0)

    @Rpc(send_to=SendTo.SERVER, require_owner=False)
    def request_develop(self, slot, colony_id):
        actor = self.actors.get(slot)
        colony = self.state.colony(colony_id)
        if actor is None or colony is None or actor.team == CELLS or math.dist(actor.feet, colony['pos']) > 4.5:
            return
        if self.state.develop(slot, colony_id):
            self.reward(slot, BALANCE['charge_collect'])

    @Rpc(send_to=SendTo.SERVER, require_owner=False)
    def building(self, slot, position, active):
        if active:
            self.builds[slot] = tuple(position)
        else:
            self.builds.pop(slot, None)

    @Rpc(send_to=SendTo.SERVER, require_owner=False)
    def hit_colony(self, slot, colony_id, amount):
        actor = self.actors.get(slot)
        if actor is None or actor.team != CELLS:
            return
        self.state.damage_colony(colony_id, amount)

    @Rpc(send_to=SendTo.SERVER, require_owner=False)
    def repair_colony(self, slot, colony_id, amount):
        actor = self.actors.get(slot)
        if actor and actor.team == BACTERIA:
            self.state.repair(colony_id, amount)
            self.effect('repair', self.state.colony(colony_id)['pos'] if self.state.colony(colony_id) else actor.feet, 2)

    @Rpc(send_to=SendTo.SERVER, require_owner=False)
    def mark_colony(self, colony_id, seconds):
        colony = self.state.colony(colony_id)
        if colony:
            colony['marked'] = seconds

    @Rpc(send_to=SendTo.SERVER, require_owner=False)
    def fortify(self, slot, position, radius, seconds):
        for colony in self.state.colonies:
            if math.dist(colony['pos'], position) <= radius:
                colony['fortified'] = seconds
                self.state.repair(colony['id'], 60)

    @Rpc(send_to=SendTo.SERVER, require_owner=False)
    def hit_rbc(self, slot, ident, amount):
        actor = self.actors.get(slot)
        if actor is None or actor.team == CELLS or self.hemacias is None:
            return
        position = self.hemacias.damage(ident, amount)
        if position is not None:
            self.add_drop('resource', position, BALANCE['rbc_resource'])

    @Rpc(send_to=SendTo.ALL, require_owner=False)
    def reward(self, slot, amount):
        actor = self.actors.get(slot)
        if actor and actor.local:
            actor.gain(amount)

    @Rpc(send_to=SendTo.ALL, require_owner=False)
    def mark_actor(self, slot, seconds):
        actor = self.actors.get(slot)
        if actor:
            actor.marked = max(actor.marked, seconds)

    def add_drop(self, kind, position, amount):
        x, y, z = position
        self.drops.append(dict(id=self.next_drop, kind=kind, pos=(x, y, z), amount=amount,
                               life=BALANCE['drop_life'] if kind == 'resource' else BALANCE['antigen_life']))
        self.next_drop += 1

    @Rpc(send_to=SendTo.ALL, require_owner=False)
    def eliminated(self, victim, source, death, position):
        target, attacker = self.actors[victim], self.actors[source]
        target.killer = source
        self.state.announce(f"{HEROES[attacker.hero].name} eliminou {HEROES[target.hero].name}", 4)
        if not self.server:
            return
        feet = (position[0], position[1]-.95, position[2])
        if target.team != CELLS:
            self.add_drop('antigen', feet, 1)
            carried = self.state.resources.get(victim, 0)
            if carried:
                self.state.resources[victim] = 0
                self.add_drop('resource', (feet[0]+.6, feet[1], feet[2]), carried)

    # -- efeitos visuais ------------------------------------------------------
    def add_zone(self, kind, position, radius, life, owner):
        self.zones.append(dict(kind=kind, pos=tuple(position), radius=radius, life=life, owner=owner))
        self.remote_zone(kind, tuple(position), radius, life, owner)

    @Rpc(send_to=SendTo.NOT_ME, require_owner=False)
    def remote_zone(self, kind, position, radius, life, owner):
        self.zones.append(dict(kind=kind, pos=tuple(position), radius=radius, life=life, owner=owner))

    def tracer(self, start, end, kind='shot', slot=None, impact=None):
        """Disparo visual de ``slot`` (hitscan já resolvido): ``start`` é o olho, ``end`` o ponto
        atingido; ``impact`` = 'world' | 'actor' | None (nada atingido)."""
        self.add_tracer(start, end, kind, slot, impact)
        self.remote_trace(start, end, kind, slot, impact)

    @Rpc(send_to=SendTo.NOT_ME, require_owner=False, protocol=Protocol.UDP)
    def remote_trace(self, start, end, kind='shot', slot=None, impact=None):
        self.add_tracer(start, end, kind, slot, impact)

    def add_tracer(self, start, end, kind, slot, impact):
        from .shots import tracer_life
        start, end = tuple(start), tuple(end)
        actor = self.actors.get(slot)
        hero = actor.hero if actor is not None else None
        self.tracers.append(dict(a=start, b=end, life=tracer_life(kind, hero, start, end), kind=kind, slot=slot,
                                 impact=impact))
        if actor is not None:
            actor.fired(kind)

    def effect(self, kind, position, radius, extra=None):
        self.effects.append(dict(kind=kind, pos=tuple(position), radius=radius, life=.6, extra=extra))
        self.remote_effect(kind, tuple(position), radius, extra)

    @Rpc(send_to=SendTo.NOT_ME, require_owner=False)
    def remote_effect(self, kind, position, radius, extra=None):
        self.effects.append(dict(kind=kind, pos=tuple(position), radius=radius, life=.6, extra=extra))

    # -- servidor -----------------------------------------------------------
    def server_tick(self, dt):
        state = self.state
        living = [a for a in self.actors.values() if a.alive and a.body.enable]
        bacteria = [a for a in living if a.team != CELLS]
        cells = [a for a in living if a.team == CELLS]
        head = self.path.at(state.escort)
        eye = (head[0], head[1]+1.2, head[2])
        candidates = [(a.slot, a.transform.position.to_tuple,
                       self.clear_line(eye, a.transform.position.to_tuple)) for a in bacteria]
        blockers = escort_blockers(self.path, state.escort, candidates)
        state.tick(dt, blockers, len(bacteria))
        if self.hemacias:
            self.hemacias.tick(dt, bacteria)
        # Physical pickups: bacteria gather resources; cells destroy them and collect antigens.
        radius = BALANCE['pickup_radius']
        for drop in list(self.drops):
            drop['life'] -= dt
            if drop['life'] <= 0:
                self.drops.remove(drop)
                continue
            for actor in living:
                if math.dist(actor.feet, drop['pos']) > radius+(.8 if actor.hero == 'macrophage' else 0):
                    continue
                if drop['kind'] == 'resource':
                    if actor.team == CELLS:
                        state.announce("Recurso bacteriano destruido", 2)
                    else:
                        state.resources[actor.slot] = state.resources.get(actor.slot, 0)+drop['amount']
                        self.reward(actor.slot, BALANCE['charge_collect'])
                    self.drops.remove(drop)
                    break
                if drop['kind'] == 'antigen' and actor.team == CELLS:
                    gain = BALANCE['antigen_macrophage'] if actor.hero == 'macrophage' else BALANCE['antigen_per_sample']
                    state.antigen(gain)
                    self.reward(actor.slot, BALANCE['charge_collect'])
                    self.drops.remove(drop)
                    break
        # Reconnaissance: contested presence at the plaza post, only after the wound closes.
        near = lambda a: math.dist(a.feet, RECON) <= BALANCE['recon_radius']
        channel = [a for a in cells if near(a)]
        if channel:
            state.channel_recon(channel[0].slot, dt, any(near(a) for a in bacteria))
        else:
            state.recon = max(0.0, state.recon-dt)

    def sync_bodies(self):
        alive = {c['id']: c for c in self.state.colonies}
        for cid in list(self.colony_bodies):
            if cid not in alive:
                body = self.colony_bodies.pop(cid)
                body.item.Destroy()
        for cid, colony in alive.items():
            if cid not in self.colony_bodies:
                item = self.game.CreateItem()
                item.name = f"Colonia {cid}"
                x, y, z = colony['pos']
                item.transform.position = Vec3(x, y+1.1, z)
                self.colony_bodies[cid] = item.AddComponent(
                    PhysicsBody3D(SphereShape(1.25), body_type=BodyType.STATIC, collision_group=8))

    def loop(self):
        session = self.game.session
        if not self.ready:
            self.ready = True
            session.ready(session.manager.id)
        dt = min(.05, self.game.delta_time)
        for collection in (self.tracers, self.effects, self.zones):
            for value in list(collection):
                value["life"] -= dt
                if value["life"] <= 0:
                    collection.remove(value)
        self.rbc_view.update(dt)
        self.sync_bodies()
        if session.status != "playing" or not self.server:
            if not self.server:
                self.state.elapsed += dt
            return
        self.server_tick(dt)
        self.sync_clock += dt
        if self.sync_clock >= .1:
            self.sync_clock = 0
            data = self.snapshot()
            self.rbc_view.apply(data['rbc'])
            self.sync(data)
        if self.state.winner:
            self.finish_timer += dt
            if self.finish_timer > 3:
                session.finish(dict(state=self.state.serialize(), actors={
                    slot: dict(kills=a.kills.value, deaths=a.deaths.value) for slot, a in self.actors.items()}))

    def on_destroy(self):
        if getattr(self.game, "session", None):
            self.game.session.arena = None
        super().on_destroy()
