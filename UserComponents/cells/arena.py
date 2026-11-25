"""Objetivos compartilhados: o servidor simula e replica um snapshot (10 Hz).

Pedidos dos jogadores (construir, desenvolver, danificar colonia, ferir hemacia)
chegam por RPC ao servidor, que valida antes de alterar o estado. Assim nao ha
gastos, coletas ou recompensas duplicadas entre host e clientes.
"""
import math
from EasyCells3D.NetworkComponents import NetworkComponent, Rpc, SendTo, Protocol
from EasyCells3D.Geometry import Vec3
from EasyCells3D.Geometry import Quaternion
from EasyCells3D.PhysicsComponents3D import PhysicsBody3D, BodyType, SphereShape, BoxShape
from .rules import MatchState, EscortPath, escort_blockers
from .catalog import CELLS, BACTERIA, HEROES, BALANCE
from .bots import BotBrain
from .npcs import Hemacias, RemoteHemacias
from . import layout, heart


class Arena(NetworkComponent):
    def __init__(self):
        super().__init__(identifier=200, owner=0)
        self.mode = layout.MODE
        self.path = EscortPath(layout.ESCORT_PATH)
        total = BALANCE['training_goal'] if self.mode == 'training' else self.path.total
        self.state = MatchState(mode=self.mode, escort_total=total, notice=layout.label('start'))
        # Coracao: valvas (portoes) e onde o comboio cruza cada uma.
        self.valves = [dict(v) for v in layout.VALVES] if self.mode == 'convoy' else []
        self.valve_progress = {v['id']: heart.valve_progress(v, self.path) for v in self.valves}
        self.valve_bodies = {}
        self.valve_open = {v['id']: True for v in self.valves}
        self.actors = {}
        self.zones, self.tracers, self.effects = [], [], []
        self.minions = {}      # id -> dict(kind, slot, pos, yaw, hp, max, life): torretas e clones
        self.walls = {}        # id -> dict(pos, yaw, life, item): Coagulase
        self.projectiles = []  # granadas (simuladas em todos; so o dono aplica o efeito)
        self.spits = []        # disparos da Pseudomonas (idem: todos simulam, so o dono aplica o dano)
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
        for v in self.valves:
            item = self.game.CreateItem()
            item.name = f"Valva {v['id']}"
            x, y, z = v['pos']
            h = v.get('height', 6.0)
            item.transform.position = Vec3(x, y+h/2, z)
            half = Vec3(v['width']/2, h/2, .35) if v['axis'] == 'x' else Vec3(.35, h/2, v['width']/2)
            body = item.AddComponent(PhysicsBody3D(BoxShape(half), body_type=BodyType.STATIC))
            body.nav_ignore = True  # a navegacao passa pelo vao (os bots esperam a valva abrir)
            self.valve_bodies[v['id']] = body

    # -- coracao: valvas ------------------------------------------------------
    def valve_is_open(self, valve):
        s = self.state
        return heart.is_open(valve, s.elapsed, s.jammed, s.escort, self.valve_progress[valve['id']], s.wound_closed)

    def update_valves(self):
        """Abre/fecha as valvas deste par pelo relogio replicado; quem esta no vao quando ela
        fecha e empurrado para o lado mais perto (so os atores simulados aqui)."""
        for v in self.valves:
            body = self.valve_bodies.get(v['id'])
            if body is None:
                continue
            opened = self.valve_is_open(v)
            if opened == self.valve_open.get(v['id']) and body.enable == (not opened):
                continue
            if not opened and self.valve_open.get(v['id'], True):
                self.clear_doorway(v)
            self.valve_open[v['id']] = opened
            body.enable = not opened

    def clear_doorway(self, v):
        x, y, z = v['pos']
        half_w, half_t = v['width']/2+.5, .35+.55
        for actor in self.actors.values():
            if not actor.local or not actor.alive:
                continue
            p = actor.transform.position
            along, across = (p.x-x, p.z-z) if v['axis'] == 'x' else (p.z-z, p.x-x)
            if abs(along) > half_w or abs(across) > half_t or not (y-.5 <= p.y-.95 <= y+v.get('height', 6.0)):
                continue
            side = 1.0 if across >= 0 else -1.0
            push = side*(half_t+.15)
            target = Vec3(p.x, p.y+.05, z+push) if v['axis'] == 'x' else Vec3(x+push, p.y+.05, p.z)
            actor.body.teleport(target)

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
            x, y, z = layout.CELL_SPAWNS[slot % 3]
        elif kind == 'entrance':
            x, y, z = layout.BACTERIA_ENTRANCE[slot % 3]
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

    @staticmethod
    def _surface(hit):
        if hit is None:
            return None
        n = hit.normal.normalize() if hit.normal is not None and hit.normal.magnitude() > 1e-6 else Vec3(0, 1, 0)
        return hit.point.to_tuple, n.to_tuple

    def floor_at(self, point, drop=4.0):
        """Chao logo abaixo de ``point`` (ate ``drop`` metros): (ponto, normal), seguindo rampas;
        None se nao houver (abismo, alto demais)."""
        x, y, z = point
        return self._surface(self.game.physics_world.raycast(Vec3(x, y+.3, z), Vec3(0, -1, 0), drop+.3, 1))

    def surface_at(self, point, aim):
        """Superficie do mapa que um projetil vindo na direcao ``aim`` atingiu em ``point``:
        (ponto, normal) ou None."""
        p = Vec3(*point)
        return self._surface(self.game.physics_world.raycast(p-aim*.3, aim, .6, 1 | 8))

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
        if layout.in_cells_base(x, z):
            return "Proibido na base das celulas"
        if any(math.dist(c['pos'], point) < 4.5 for c in self.state.colonies):
            return "Muito perto de outra colonia"
        if any(math.dist(p, point) < 4.5 for s, p in self.builds.items() if s != slot):
            return "Outra construcao em andamento"
        if self.mode != 'training' and math.dist(point, self.path.at(self.state.escort)) < 3:
            return "Sobre a escolta"
        for v in self.valves:
            if math.hypot(point[0]-v['pos'][0], point[2]-v['pos'][2]) < v['width']/2+1.2:
                return "No vao da valva"
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
        if layout.in_cells_base(position[0], position[2]) or any(math.dist(c['pos'], position) < 4.5 for c in self.state.colonies):
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
            amount = BALANCE['kid_resource'] if self.hemacias.kids else BALANCE['rbc_resource']
            self.add_drop('resource', position, amount)

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
    def add_zone(self, kind, position, radius, life, owner, follow=False, normal=None):
        """``normal``: zona colada numa superficie (rampa, parede, teto) - disco orientado por ela."""
        normal = tuple(normal) if normal is not None else None
        self.push_zone(kind, position, radius, life, owner, follow, normal)
        self.remote_zone(kind, tuple(position), radius, life, owner, follow, normal)

    @Rpc(send_to=SendTo.NOT_ME, require_owner=False)
    def remote_zone(self, kind, position, radius, life, owner, follow=False, normal=None):
        self.push_zone(kind, position, radius, life, owner, follow, normal)

    def push_zone(self, kind, position, radius, life, owner, follow, normal):
        zone = dict(kind=kind, pos=tuple(position), radius=radius, life=life, owner=owner, follow=follow,
                    age=0.0, max=life)
        if normal is not None:
            zone['normal'] = tuple(normal)
        self.zones.append(zone)
        actor = self.actors.get(owner)
        if follow == 'focus' and actor is not None and not actor.local:
            actor.ult_focus = tuple(position)  # nada de centro velho de uma Chuva anterior

    # -- objetos de habilidade --------------------------------------------------
    @Rpc(send_to=SendTo.ALL, require_owner=False)
    def spawn_minion(self, ident, kind, slot, position, yaw, health, life):
        self.minions[ident] = dict(kind=kind, slot=slot, pos=tuple(position), yaw=yaw, hp=health, max=health,
                                   life=life, recoil=0.0, age=0.0)
        self.effects.append(dict(kind='spawn', pos=tuple(position), radius=1.2, life=.6, extra=kind))

    @Rpc(send_to=SendTo.ALL, require_owner=False)
    def damage_minion(self, ident, amount, source):
        m = self.minions.get(ident)
        if m is None:
            return
        m['hp'] -= amount
        m['hurt'] = .2
        attacker = self.actors.get(source)
        if attacker is not None and attacker.local:
            attacker.hit_marker = .15
        if m['hp'] <= 0:
            self.minions.pop(ident, None)
            x, y, z = m['pos']
            self.effects.append(dict(kind='pop', pos=(x, y+.8, z), radius=1.4, life=.6, extra=m['kind']))

    @Rpc(send_to=SendTo.ALL, require_owner=False)
    def remove_minion(self, ident):
        self.minions.pop(ident, None)

    @Rpc(send_to=SendTo.NOT_ME, require_owner=False, protocol=Protocol.UDP)
    def sync_minion(self, ident, position, yaw, recoil=0.0):
        m = self.minions.get(ident)
        if m is not None:
            m['pos'], m['yaw'] = tuple(position), yaw
            m['recoil'] = max(m.get('recoil', 0), recoil)

    @Rpc(send_to=SendTo.ALL, require_owner=False)
    def add_wall(self, ident, position, yaw, life):
        x, y, z = position
        width = BALANCE['wall_width']
        item = self.game.CreateItem()
        item.name = f"Coagulase {ident}"
        item.transform.position = Vec3(x, y+1.3, z)
        item.transform.rotation = Quaternion.from_euler_angles(Vec3(0, yaw, 0))
        body = item.AddComponent(PhysicsBody3D(BoxShape(Vec3(width/2, 1.3, .3)), body_type=BodyType.STATIC))
        self.walls[ident] = dict(pos=tuple(position), yaw=yaw, life=life, max=life, item=item, body=body)

    def remove_wall(self, ident):
        wall = self.walls.pop(ident, None)
        if wall:
            wall['item'].Destroy()
            self.effects.append(dict(kind='crumble', pos=wall['pos'], radius=3, life=.6, extra=wall['yaw']))

    def throw(self, kind, start, velocity, slot):
        self.add_projectile(kind, start, velocity, slot)
        self.remote_throw(kind, tuple(start), tuple(velocity), slot)

    @Rpc(send_to=SendTo.NOT_ME, require_owner=False)
    def remote_throw(self, kind, start, velocity, slot):
        self.add_projectile(kind, start, velocity, slot)

    def add_projectile(self, kind, start, velocity, slot):
        self.projectiles.append(dict(kind=kind, pos=tuple(start), vel=list(velocity), slot=slot, life=2.5,
                                     trail=[tuple(start)]))

    def step_projectiles(self, dt):
        from .kits import GRAVITY
        world = self.game.physics_world
        for p in list(self.projectiles):
            owner = self.actors.get(p['slot'])
            x, y, z = p['pos']
            vx, vy, vz = p['vel']
            nvy = vy-GRAVITY*dt
            nx, ny, nz = x+vx*dt, y+(vy+nvy)*.5*dt, z+vz*dt
            p['vel'][1] = nvy
            p['life'] -= dt
            delta = Vec3(nx-x, ny-y, nz-z)
            dist = delta.magnitude()
            point = None
            if dist > 1e-6:
                hit = world.raycast(Vec3(x, y, z), delta, dist, 1 | 8)
                if hit is not None:
                    point = hit.point.to_tuple
            shield = None
            for other in self.actors.values():
                if owner is None or other.team == owner.team or not other.alive:
                    continue
                center = other.front_center()
                if other.front and math.dist(center, (nx, ny, nz)) < other.front_radius <= math.dist(center, (x, y, z)):
                    shield = other
                    break
                if point is None and any(math.dist(c, (nx, ny, nz)) < r+.25 for c, r, _ in other.hitboxes()):
                    point = (nx, ny, nz)
            p['pos'] = (nx, ny, nz)
            p['trail'] = (p['trail']+[p['pos']])[-10:]
            if shield is not None:
                self.projectiles.remove(p)
                if owner is not None and owner.local:
                    shield.absorb_hit(40, owner)
                continue
            if point is None and p['life'] <= 0:
                point = p['pos']
            if point is not None:
                self.projectiles.remove(p)
                if owner is not None and owner.local:
                    owner.detonate(p['kind'], point)

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
        if actor is not None and kind not in ('turret', 'clone'):
            actor.fired(kind)

    # -- disparos da Pseudomonas (projetil com gravidade) -------------------
    def spit(self, start, velocity, slot):
        self.add_spit(start, velocity, slot)
        self.remote_spit(tuple(start), tuple(velocity), slot)

    @Rpc(send_to=SendTo.NOT_ME, require_owner=False, protocol=Protocol.UDP)
    def remote_spit(self, start, velocity, slot):
        self.add_spit(start, velocity, slot)

    def add_spit(self, start, velocity, slot):
        start = tuple(start)
        self.spits.append(dict(origin=start, pos=start, vel=tuple(velocity), slot=slot, age=0.0,
                               trail=[(start, 0.0)], end=None, end_age=0.0, impact=None))
        actor = self.actors.get(slot)
        if actor is not None:
            actor.fired('shot')

    def step_spits(self, dt):
        """Avanca cada glob em linha reta por quadro (com gravidade) e testa o trecho percorrido
        contra o mesmo ``cast`` do hitscan. O dono aplica dano/respingo/poca no impacto, mesmo
        que ja tenha morrido; os demais pares so mostram o efeito."""
        from .combat import SPIT, cast, impact_kind
        for s in list(self.spits):
            s['age'] += dt
            if s['end'] is not None:
                if s['age']-s['end_age'] > SPIT['linger']:
                    self.spits.remove(s)
                continue
            owner = self.actors.get(s['slot'])
            if owner is None:
                self.spits.remove(s)
                continue
            x, y, z = s['pos']
            vx, vy, vz = s['vel']
            nvy = vy-SPIT['gravity']*dt
            nxt = (x+vx*dt, y+(vy+nvy)*.5*dt, z+vz*dt)
            s['vel'] = (vx, nvy, vz)
            delta = Vec3(nxt[0]-x, nxt[1]-y, nxt[2]-z)
            dist = delta.magnitude()
            if dist > 1e-6:
                aim = delta*(1/dist)
                hits = cast(owner, aim, dist, origin=Vec3(x, y, z))
                if hits:
                    point = hits[0]['point'].to_tuple
                    self.finish_spit(s, point, impact_kind(hits))
                    if owner.local:
                        owner.spit_impact(hits[0], point, aim)
                    continue
            s['pos'] = nxt
            s['trail'].append((nxt, s['age']))
            if s['age'] >= SPIT['life']:
                self.finish_spit(s, nxt, None)  # perdeu forca no ar: some sem poca

    @staticmethod
    def finish_spit(s, point, impact):
        s['end'], s['end_age'], s['impact'] = point, s['age'], impact
        s['pos'] = point
        s['trail'].append((point, s['age']))

    def effect(self, kind, position, radius, extra=None, normal=None):
        normal = tuple(normal) if normal is not None else None
        self.effects.append(dict(kind=kind, pos=tuple(position), radius=radius, life=.6, extra=extra, normal=normal))
        self.remote_effect(kind, tuple(position), radius, extra, normal)

    @Rpc(send_to=SendTo.NOT_ME, require_owner=False)
    def remote_effect(self, kind, position, radius, extra=None, normal=None):
        self.effects.append(dict(kind=kind, pos=tuple(position), radius=radius, life=.6, extra=extra, normal=normal))

    # -- servidor -----------------------------------------------------------
    def server_tick(self, dt):
        state = self.state
        living = [a for a in self.actors.values() if a.alive and a.body.enable]
        bacteria = [a for a in living if a.team != CELLS]
        cells = [a for a in living if a.team == CELLS]
        blockers = []
        if self.mode != 'training':
            head = self.path.at(state.escort)
            eye = (head[0], head[1]+1.2, head[2])
            candidates = [(a.slot, a.transform.position.to_tuple,
                           self.clear_line(eye, a.transform.position.to_tuple)) for a in bacteria]
            blockers = escort_blockers(self.path, state.escort, candidates)
            for zone in self.zones:
                # Pneumonia: a nuvem sobre as plaquetas (ou o comboio) tambem os para.
                if zone['kind'] == 'cloud' and zone['owner'] in self.actors and zone['owner'] not in blockers \
                        and math.dist(zone['pos'], head) < zone['radius']+1:
                    blockers.append(zone['owner'])
        limit, valve = math.inf, -1
        if self.valves and not state.wound_closed:
            state.jammed = heart.jammed_valves(self.valves, state.colonies)
            limit = heart.max_advance(self.valves, self.valve_progress, state.elapsed, state.jammed, state.escort)
            valve = heart.convoy_block(self.valves, self.valve_progress, state.elapsed, state.jammed, state.escort)
        elif self.valves:
            state.jammed = []
        state.tick(dt, blockers, len(bacteria), limit, valve)
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
        near = lambda a: math.dist(a.feet, layout.RECON) <= BALANCE['recon_radius']
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
        for zone in self.zones:
            zone['age'] = zone.get('age', 0.0)+dt
            if zone.get('follow'):
                owner = self.actors.get(zone['owner'])
                if owner is not None and owner.alive:
                    if zone['follow'] != 'focus':
                        zone['pos'] = owner.feet
                    elif owner.ult_focus is not None:
                        # Chuva de anticorpos: segue o centro que o B-Cell move (suave nos outros pares).
                        k = 1.0 if owner.local else min(1.0, dt*12)
                        zone['pos'] = tuple(a+(b-a)*k for a, b in zip(zone['pos'], owner.ult_focus))
        for ident, wall in list(self.walls.items()):
            wall['life'] -= dt
            if wall['life'] <= 0:
                self.remove_wall(ident)
        for m in self.minions.values():
            m['age'] = m.get('age', 0.0)+dt
            m['recoil'] = max(0.0, m.get('recoil', 0)-dt*5)
            m['hurt'] = max(0.0, m.get('hurt', 0)-dt)
        self.step_projectiles(dt)
        self.step_spits(dt)
        self.rbc_view.update(dt)
        self.sync_bodies()
        if self.valves:
            self.update_valves()
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
        self.walls.clear()  # os itens das paredes sao destruidos junto com a cena
        if getattr(self.game, "session", None):
            self.game.session.arena = None
        super().on_destroy()
