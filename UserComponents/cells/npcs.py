"""Hemacias que entregam oxigenio (simuladas pelo servidor).

Ciclo (PLANO_MAPA.md, secao 5): entrega -> percepcao (so com linha de visao)
-> fuga -> desvio por outra rota -> abrigo quando nao ha saida segura ->
retomada apos um periodo sem ver perigo. Uma escolha de rota vale por um
intervalo minimo, mas ameaca nova e proxima permite reagir antes.
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


def plan(start, goals, threats=(), danger=9.0):
    """A* no grafo de ruas. Arestas perto de ameacas lembradas ficam caras."""
    def cost(a, b):
        c = math.dist(RBC_NODES[a], RBC_NODES[b])
        for t in threats:
            if seg_dist(t, RBC_NODES[a], RBC_NODES[b]) < danger:
                c += 400
        return c
    goals = set(goals)
    best = {start: 0.0}
    parent = {}
    queue = [(0.0, 0.0, start)]
    while queue:
        _, g, node = heapq.heappop(queue)
        if node in goals:
            path = [node]
            while path[-1] != start:
                path.append(parent[path[-1]])
            return list(reversed(path)), g
        if g > best.get(node, math.inf):
            continue
        for other in GRAPH[node]:
            ng = g+cost(node, other)
            if ng < best.get(other, math.inf):
                best[other], parent[other] = ng, node
                h = min(math.dist(RBC_NODES[other], RBC_NODES[x]) for x in goals)
                heapq.heappush(queue, (ng+h, ng, other))
    return [], math.inf


class RedBloodCell:
    def __init__(self, ident, destination, rng):
        self.id = ident
        self.rng = rng
        self.reset(destination)

    def reset(self, destination):
        self.destination = destination
        x, y, z = RBC_DEPOT
        self.pos = [x+self.rng.uniform(-1.5, 1.5), y, z+self.rng.uniform(-1.5, 1.5)]
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

    def nearest_node(self):
        return min(RBC_NODES, key=lambda n: _d2(RBC_NODES[n], self.pos))

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
    def ground(self, x, y, z):
        from EasyCells3D.Geometry import Vec3
        hit = self.arena.game.physics_world.raycast(Vec3(x, y+1.6, z), Vec3(0, -1, 0), 4.5, 1)
        return hit.point.y if hit else y

    def line_of_sight(self, a, b):
        from EasyCells3D.Geometry import Vec3
        start = Vec3(a[0], a[1]+1.4, a[2])
        delta = Vec3(b[0], b[1]+.3, b[2])-start
        dist = delta.magnitude()
        return dist < .01 or self.arena.game.physics_world.raycast(start, delta, dist, 1) is None

    def replan(self, cell, now):
        threats = [t[0] for t in cell.threats.values()]
        start = cell.nearest_node()
        path, cost = plan(start, DESTINATIONS[cell.destination], threats)
        cell.commit_until = now+BALANCE['rbc_commit']
        if path and cost < 400:
            cell.state = 'deliver'
            cell.path = path
            return
        # No safe route: back off to the reachable node farthest from the threats.
        best, score = start, -1
        frontier = {start}
        seen = {start}
        for _ in range(2):
            frontier = {o for n in frontier for o in GRAPH[n]} - seen
            seen |= frontier
        for node in seen:
            p = RBC_NODES[node]
            s = min((math.dist(p, t) for t in threats), default=99)
            if s > score:
                best, score = node, s
        cell.state = 'flee'
        cell.path = [best]

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
            # Field of view: 150 degrees forward, plus close-range awareness.
            vx, vz = (pos[0]-cell.pos[0])/max(d, .01), (pos[2]-cell.pos[2])/max(d, .01)
            if d > 5 and vx*facing[0]+vz*facing[1] < -.26:
                continue
            if not self.line_of_sight(cell.pos, pos):
                continue
            known = cell.threats.get(actor.slot)
            if known is None or math.dist(known[0], pos) > 6 or d < 5:
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
        if dist < .4:
            cell.node = cell.path.pop(0)
            if not cell.path and cell.state == 'deliver' and cell.node in DESTINATIONS[cell.destination]:
                self.deliveries[cell.destination] += 1
                cell.state, cell.timer = 'inside', BALANCE['rbc_respawn']
            return
        step = min(dist, speed*dt)
        cell.pos[0] += dx/dist*step
        cell.pos[2] += dz/dist*step
        cell.pos[1] = self.ground(cell.pos[0], cell.pos[1], cell.pos[2])
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
