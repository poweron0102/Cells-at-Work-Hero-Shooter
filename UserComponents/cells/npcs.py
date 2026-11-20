"""Hemacias que entregam oxigenio (simuladas pelo servidor).

Ciclo (PLANO_MAPA.md, secao 5): entrega -> percepcao (so com linha de visao)
-> fuga -> desvio por outra rota -> abrigo quando nao ha saida segura ->
retomada apos um periodo sem ver perigo. Uma escolha de rota vale por um
intervalo minimo, mas ameaca nova e proxima permite reagir antes.

Todo movimento, inclusive a fuga, segue as arestas de ``rbc_edges`` (que
``scripts/check_rbc_routes.py`` garante livres de parede e com chao continuo):
a busca parte dos dois nos da rua onde a hemacia esta, nunca de um no
"mais proximo" do outro lado de um predio.
"""
import heapq
import math
import random
from .catalog import BALANCE, CELLS
from .layout import RBC_NODES, RBC_EDGES, DESTINATIONS, RBC_DEPOT

GRAPH = {name: [] for name in RBC_NODES}
for a, b in RBC_EDGES:
    GRAPH[a].append(b)
    GRAPH[b].append(a)


def _d2(a, b):
    return (a[0]-b[0])**2+(a[2]-b[2])**2


def seg_dist(p, a, b):
    ax, az, bx, bz = a[0], a[2], b[0], b[2]
    vx, vz = bx-ax, bz-az
    L = vx*vx+vz*vz or 1
    t = max(0, min(1, ((p[0]-ax)*vx+(p[2]-az)*vz)/L))
    return math.hypot(ax+vx*t-p[0], az+vz*t-p[2])


DANGER_COST = 400  # por trecho que aproxima a hemacia de uma ameaca lembrada
ARRIVE = .4
FLEE_RANGE = 30.0  # metros de rua que a hemacia aceita correr ate um abrigo


def leg_cost(p, q, threats, danger):
    """Comprimento de p->q, mais DANGER_COST por ameaca da qual o trecho se aproxima.

    Afastar-se de uma bacteria proxima e permitido; passar perto dela vindo de longe nao.
    """
    c = math.dist(p, q)
    for t in threats:
        near = seg_dist(t, p, q)
        if near < danger and near < math.hypot(p[0]-t[0], p[2]-t[2])-.5:
            c += DANGER_COST
    return c


def anchors(origin, threats=(), danger=9.0):
    """Os dois nos da rua onde ``origin`` esta: os unicos alcancaveis em linha reta."""
    a, b = min(RBC_EDGES, key=lambda e: seg_dist(origin, RBC_NODES[e[0]], RBC_NODES[e[1]]))
    return {n: leg_cost(origin, RBC_NODES[n], threats, danger) for n in (a, b)}


def search(origin, threats=(), danger=9.0):
    """Dijkstra pelo grafo de ruas a partir de um ponto sobre ele.

    Devolve ``best`` {no: (custo, metros)} e ``parent`` {no: anterior | None}.
    """
    best, parent, queue = {}, {}, []
    for node, c in anchors(origin, threats, danger).items():
        best[node], parent[node] = (c, math.dist(origin, RBC_NODES[node])), None
        heapq.heappush(queue, (c, node))
    while queue:
        g, node = heapq.heappop(queue)
        if g > best[node][0]:
            continue
        length = best[node][1]
        for other in GRAPH[node]:
            a, b = RBC_NODES[node], RBC_NODES[other]
            ng = g+leg_cost(a, b, threats, danger)
            if ng < best.get(other, (math.inf,))[0]:
                best[other], parent[other] = (ng, length+math.dist(a, b)), node
                heapq.heappush(queue, (ng, other))
    return best, parent


def route(parent, node, origin):
    path = [node]
    while parent[path[-1]] is not None:
        path.append(parent[path[-1]])
    path.reverse()
    if len(path) > 1 and _d2(RBC_NODES[path[0]], origin) < ARRIVE**2:
        path.pop(0)  # ja esta em cima do primeiro no
    return path


def plan(origin, goals, threats=(), danger=9.0):
    """Melhor rota de ``origin`` ate um dos ``goals``, sempre pelas ruas."""
    best, parent = search(origin, threats, danger)
    goal = min(goals, key=lambda n: best.get(n, (math.inf,))[0])
    if goal not in best:
        return [], math.inf
    return route(parent, goal, origin), best[goal][0]


class RedBloodCell:
    def __init__(self, ident, destination, rng):
        self.id = ident
        self.rng = rng
        self.reset(destination)

    def reset(self, destination):
        self.destination = destination
        # Spread out along the depot's exit street (never sideways into the station's props).
        x, y, z = RBC_DEPOT
        ex, _, ez = RBC_NODES['depot_out']
        length = math.hypot(ex-x, ez-z) or 1
        ux, uz = (ex-x)/length, (ez-z)/length
        along, side = self.rng.uniform(0, min(1.5, length)), self.rng.uniform(-.3, .3)
        self.pos = [x+ux*along-uz*side, y, z+uz*along+ux*side]
        self.hp = BALANCE['rbc_health']
        self.state = 'deliver'
        self.path = []
        self.node = 'depot'
        self.threats = {}  # slot -> (pos, time seen)
        self.commit_until = 0.0
        self.calm_since = 0.0
        self.timer = 0.0
        self.yaw = 0.0
        self.moving = False
        self.carrying = True

    @property
    def alive(self):
        return self.state not in ('dead', 'inside')

    def snapshot(self):
        return (self.id, round(self.pos[0], 2), round(self.pos[1], 2), round(self.pos[2], 2), round(self.yaw, 2),
                self.state, int(self.hp), self.moving)


class Hemacias:
    """Server-side simulation. ``world`` is the physics world (raycasts)."""

    def __init__(self, arena, seed=11):
        self.arena = arena
        self.rng = random.Random(seed)
        order = ['A', 'B', 'C']
        self.cells = [RedBloodCell(i, order[i % 3], self.rng) for i in range(BALANCE['rbc_count'])]
        for i, cell in enumerate(self.cells):
            # Stagger departures so the district fills up gradually.
            cell.state, cell.timer = 'inside', 1.0+i*2.2
        self.next_destination = 0
        self.deliveries = {'A': 0, 'B': 0, 'C': 0}
        self.clock = 0.0
        self.perceive_timer = 0.0

    # -- helpers ---------------------------------------------------------
    def ground(self, x, z, expected):
        """Altura do chao perto de ``expected`` (a altura da rua naquele ponto).

        So aceita degraus pequenos: nada de subir em parede ou ficar no ar sem chao.
        """
        from EasyCells3D.Geometry import Vec3
        hit = self.arena.game.physics_world.raycast(Vec3(x, expected+.8, z), Vec3(0, -1, 0), 1.6, 1)
        return hit.point.y if hit else expected

    def line_of_sight(self, a, b):
        from EasyCells3D.Geometry import Vec3
        start = Vec3(a[0], a[1]+1.4, a[2])
        delta = Vec3(b[0], b[1]+.3, b[2])-start
        dist = delta.magnitude()
        return dist < .01 or self.arena.game.physics_world.raycast(start, delta, dist, 1) is None

    def replan(self, cell, now):
        threats = [t[0] for t in cell.threats.values()]
        best, parent = search(cell.pos, threats)
        cell.commit_until = now+BALANCE['rbc_commit']
        goals = [n for n in DESTINATIONS[cell.destination] if n in best]
        if goals:
            goal = min(goals, key=lambda n: best[n][0])
            if best[goal][0] < DANGER_COST:
                cell.state = 'deliver'
                cell.path = route(parent, goal, cell.pos)
                return
        # No safe route: run, along the streets, to a nearby corner the threats cannot see.
        cell.state = 'flee'
        cell.path = route(parent, self.shelter(best, threats), cell.pos)

    def shelter(self, best, threats):
        def key(node):
            cost, length = best[node]
            p = RBC_NODES[node]
            clear = min((math.dist(p, t) for t in threats), default=99)
            hidden = clear > 4 and not any(self.line_of_sight(t, p) for t in threats)
            # First never cross a threat, then prefer cover and distance, then short runs.
            return (int(cost//DANGER_COST), -(min(clear, 20)+(12 if hidden else 0)-.1*length))
        options = [n for n, (_, length) in best.items() if length <= FLEE_RANGE] or list(best)
        return min(options, key=key)

    # -- loop ------------------------------------------------------------
    def tick(self, dt, bacteria):
        """``bacteria``: list of living bacterial actors (server view)."""
        self.clock += dt
        now = self.clock
        self.perceive_timer -= dt
        perceive = self.perceive_timer <= 0
        if perceive:
            self.perceive_timer = .25
        for cell in self.cells:
            if cell.state in ('dead', 'inside'):
                cell.timer -= dt
                if cell.timer <= 0:
                    order = 'ABC'
                    dest = order[self.next_destination % 3]
                    self.next_destination += 1
                    cell.reset(dest)
                    self.replan(cell, now)
                continue
            if perceive:
                self.perceive(cell, bacteria, now)
            self.move(cell, dt, now)

    def perceive(self, cell, bacteria, now):
        sight = BALANCE['rbc_sight']
        new_threat = False
        facing = (math.sin(cell.yaw), -math.cos(cell.yaw))
        for actor in bacteria:
            p = actor.transform.position
            pos = (p.x, p.y-.95, p.z)
            d = math.dist(pos, cell.pos)
            if d > sight:
                continue
            # Field of view: about 210 degrees (only the back ~150 is blind), plus close-range awareness.
            vx, vz = (pos[0]-cell.pos[0])/max(d, .01), (pos[2]-cell.pos[2])/max(d, .01)
            if d > 5 and vx*facing[0]+vz*facing[1] < -.26:
                continue
            if not self.line_of_sight(cell.pos, pos):
                continue
            known = cell.threats.get(actor.slot)
            # New: never seen, moved a lot, or just closed in (not every tick while it stays close).
            if known is None or math.dist(known[0], pos) > 6 or (d < 5 and math.dist(known[0], cell.pos) >= 5):
                new_threat = True
            cell.threats[actor.slot] = (pos, now)
        memory = BALANCE['rbc_memory']
        for slot in [s for s, (_, t) in cell.threats.items() if now-t > memory]:
            del cell.threats[slot]
        if cell.threats:
            cell.calm_since = now
            closest = min(math.dist(t[0], cell.pos) for t in cell.threats.values())
            if (new_threat and closest < 6) or now >= cell.commit_until:
                if new_threat or cell.state == 'deliver':
                    self.replan(cell, now)
        elif cell.state in ('flee', 'hide') and now-cell.calm_since > memory*.5:
            self.replan(cell, now)  # resume the delivery

    def move(self, cell, dt, now):
        cell.moving = False
        if not cell.path:
            if cell.state == 'flee':
                cell.state = 'hide'
            return
        target = RBC_NODES[cell.path[0]]
        dx, dz = target[0]-cell.pos[0], target[2]-cell.pos[2]
        dist = math.hypot(dx, dz)
        speed = BALANCE['rbc_speed']*(1.3 if cell.state == 'flee' else 1)
        if dist < ARRIVE:
            cell.node = cell.path.pop(0)
            if not cell.path and cell.state == 'deliver' and cell.node in DESTINATIONS[cell.destination]:
                self.deliveries[cell.destination] += 1
                cell.state, cell.timer = 'inside', BALANCE['rbc_respawn']
            return
        step = min(dist, speed*dt)
        cell.pos[0] += dx/dist*step
        cell.pos[2] += dz/dist*step
        # Street height ramps linearly towards the next node; the raycast only refines it.
        street = cell.pos[1]+(target[1]-cell.pos[1])*step/dist
        cell.pos[1] = self.ground(cell.pos[0], cell.pos[2], street)
        cell.yaw = math.atan2(dx, -dz)
        cell.moving = True

    def damage(self, ident, amount):
        """Returns the drop position if the cell died."""
        cell = self.cells[ident]
        if not cell.alive:
            return None
        cell.hp -= amount
        if cell.hp <= 0:
            cell.state, cell.timer = 'dead', BALANCE['rbc_respawn']
            return tuple(cell.pos)
        return None

    def snapshot(self):
        return [c.snapshot() for c in self.cells if c.alive]


class RemoteHemacias:
    """Client mirror of the server snapshot with simple interpolation."""

    def __init__(self):
        self.cells = {}

    def apply(self, data):
        seen = set()
        for ident, x, y, z, yaw, state, hp, moving in data:
            seen.add(ident)
            cell = self.cells.get(ident)
            if cell is None or cell['state'] in ('dead', 'inside'):
                self.cells[ident] = dict(pos=[x, y, z], target=[x, y, z], yaw=yaw, state=state, hp=hp, moving=moving, phase=0.0)
            else:
                cell.update(target=[x, y, z], yaw=yaw, state=state, hp=hp, moving=moving)
        for ident in list(self.cells):
            if ident not in seen:
                del self.cells[ident]

    def update(self, dt):
        for cell in self.cells.values():
            p, t = cell['pos'], cell['target']
            k = min(1.0, dt*10)
            moved = math.dist(p, t)*k
            for i in range(3):
                p[i] += (t[i]-p[i])*k
            cell['phase'] += moved*4
