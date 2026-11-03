"""Navegacao em camadas (rua, canal, passarelas, pontes) para os bots.

A grade e amostrada com raycasts na colisao exportada do Blender e salva em
``nav.json`` ao lado do mapa (gerada por ``scripts/build_navmesh.py`` ou na
primeira execucao). Varias alturas podem dividir a mesma coluna X/Z, o que
preserva passagens sob pontes e passarelas.
"""
import hashlib
import heapq
import json
import math
from EasyCells3D.Geometry import Vec3
from .layout import X0, X1, Z0, Z1, NAV_CEILINGS, MAP_FOLDER

STEP = 2
NAV_FILE = MAP_FOLDER/'nav.json'


def map_hash():
    return hashlib.sha1((MAP_FOLDER/'runtime.json').read_bytes()).hexdigest()[:16]


class Navigator:
    _cached = None

    def __init__(self, world):
        self.world = world
        self.columns, self.edges = {}, {}

    # -- construcao -------------------------------------------------------
    def build(self):
        import pybullet as bullet
        world = self.world
        columns, edges = {}, {}
        shape = bullet.createCollisionShape(bullet.GEOM_CAPSULE, radius=.42, height=1.0,
                                            collisionFrameOrientation=[-.70710678, 0, 0, .70710678],
                                            physicsClientId=world.client)
        probe = bullet.createMultiBody(baseMass=0, baseCollisionShapeIndex=shape, basePosition=[0, -100, 0],
                                       physicsClientId=world.client)
        bullet.setCollisionFilterGroupMask(probe, -1, 0, 0, physicsClientId=world.client)
        bodies = [b.uid for b in world.bodies if b.enable and b.collision_group & 1]

        def clear(x, y, z):
            bullet.resetBasePositionAndOrientation(probe, [x, y+1.2, z], [0, 0, 0, 1], physicsClientId=world.client)
            return not any(bullet.getClosestPoints(probe, uid, .01, physicsClientId=world.client) for uid in bodies)
        surfaces = walkable_heights()
        try:
            for (x, z), heights in surfaces.items():
                nodes = [y for y in heights if clear(x, y, z)]
                if nodes:
                    columns[(x, z)] = nodes
            for (x, z), ys in columns.items():
                for y in ys:
                    out = []
                    for dx, dz in ((STEP, 0), (-STEP, 0), (0, STEP), (0, -STEP)):
                        for oy in columns.get((x+dx, z+dz), ()):
                            if abs(oy-y) > 3.0:
                                continue
                            if all(clear(x+dx*t, max(y, oy) if abs(oy-y) > .35 else y+(oy-y)*t, z+dz*t) for t in (.33, .66)):
                                slope = 1
                                if abs(oy-y) > .35:
                                    # A ramp/stair has intermediate ground at the midpoint; a ledge does not.
                                    mid = world.raycast(Vec3(x+dx/2, max(y, oy)+1.2, z+dz/2), Vec3(0, -1, 0), 4, 1)
                                    lo, hi = min(y, oy), max(y, oy)
                                    slope = int(bool(mid) and lo+.15 < mid.point.y < hi-.15)
                                out.append((x+dx, oy, z+dz, slope))
                    edges[(x, y, z)] = out
        finally:
            bullet.removeBody(probe, physicsClientId=world.client)
        self.columns, self.edges = columns, edges

    def save(self, path=NAV_FILE):
        data = dict(hash=map_hash(), step=STEP,
                    nodes=[[x, y, z, [list(e) for e in self.edges.get((x, y, z), ())]]
                           for (x, z), ys in self.columns.items() for y in ys])
        path.write_text(json.dumps(data, separators=(',', ':')), encoding='utf-8')

    def load(self, path=NAV_FILE):
        if not path.exists():
            return False
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('hash') != map_hash():
            return False
        columns, edges = {}, {}
        for x, y, z, out in data['nodes']:
            columns.setdefault((x, z), []).append(y)
            edges[(x, y, z)] = [tuple(e) for e in out]
        self.columns, self.edges = columns, edges
        return True

    def ensure(self):
        if self.edges:
            return
        if Navigator._cached is not None:
            self.columns, self.edges = Navigator._cached
            return
        if not self.load():
            self.build()
            try:
                self.save()
            except OSError:
                pass
        Navigator._cached = self.columns, self.edges

    # -- consulta ---------------------------------------------------------
    def nearest(self, p):
        cx = int(round((p.x-X0-1)/STEP))*STEP+int(X0)+1
        cz = int(round((p.z-Z0-1)/STEP))*STEP+int(Z0)+1
        best, score = None, math.inf
        for r in range(0, 6):
            for dx in range(-r, r+1):
                for dz in range(-r, r+1):
                    if max(abs(dx), abs(dz)) != r:
                        continue
                    key = (cx+dx*STEP, cz+dz*STEP)
                    for y in self.columns.get(key, ()):
                        s = (key[0]-p.x)**2+(key[1]-p.z)**2+6*(y+.95-p.y)**2
                        if s < score:
                            best, score = (key[0], y, key[1]), s
            if best is not None and r >= 1:
                return best
        return best

    def path(self, start, target, jump_height=1.2, limit=6000):
        self.ensure()
        first, last = self.nearest(start), self.nearest(target)
        if first is None or last is None:
            return []
        queue, costs, parent = [(0, first)], {first: 0}, {}
        expanded = 0
        while queue and expanded < limit:
            _, current = heapq.heappop(queue)
            expanded += 1
            if current == last:
                nodes = [current]
                while nodes[-1] != first:
                    nodes.append(parent[nodes[-1]])
                return [Vec3(x, y+.95, z) for x, y, z in reversed(nodes)]
            for edge in self.edges.get(current, ()):
                other, slope = edge[:3], edge[3]
                rise = other[1]-current[1]
                if not slope and rise > jump_height-.15:
                    continue
                cost = costs[current]+STEP+abs(rise)*.5+(2 if rise > .7 else 0)
                if cost < costs.get(other, math.inf):
                    costs[other], parent[other] = cost, current
                    heapq.heappush(queue, (cost+abs(other[0]-last[0])+abs(other[2]-last[2]), other))
        return []

def walkable_heights():
    """Heights of upward-facing collision triangles at every grid column.

    Reads the exported triangles directly (their winding is outward), so solid
    slabs never produce phantom floors under the street.
    """
    from .layout import MAP_DATA
    verts, idx = MAP_DATA['vertices'], MAP_DATA['indices']
    xs = range(int(X0)+1, int(X1), STEP)
    zs = range(int(Z0)+1, int(Z1), STEP)
    out = {}
    for t in range(0, len(idx), 3):
        a, b, c = verts[idx[t]], verts[idx[t+1]], verts[idx[t+2]]
        ux, uy, uz = b[0]-a[0], b[1]-a[1], b[2]-a[2]
        vx, vy, vz = c[0]-a[0], c[1]-a[1], c[2]-a[2]
        nx, ny, nz = uy*vz-uz*vy, uz*vx-ux*vz, ux*vy-uy*vx
        length = math.sqrt(nx*nx+ny*ny+nz*nz) or 1
        if ny/length < .6:
            continue
        x0, x1 = min(a[0], b[0], c[0]), max(a[0], b[0], c[0])
        z0, z1 = min(a[2], b[2], c[2]), max(a[2], b[2], c[2])
        det = (b[2]-c[2])*(a[0]-c[0])+(c[0]-b[0])*(a[2]-c[2])
        if abs(det) < 1e-9:
            continue
        for x in xs:
            if x < x0-1e-6 or x > x1+1e-6:
                continue
            for z in zs:
                if z < z0-1e-6 or z > z1+1e-6:
                    continue
                l1 = ((b[2]-c[2])*(x-c[0])+(c[0]-b[0])*(z-c[2]))/det
                l2 = ((c[2]-a[2])*(x-c[0])+(a[0]-c[0])*(z-c[2]))/det
                l3 = 1-l1-l2
                if min(l1, l2, l3) < -1e-6:
                    continue
                y = round(l1*a[1]+l2*b[1]+l3*c[1], 2)
                ys = out.setdefault((x, z), [])
                if all(abs(y-o) > .3 for o in ys):
                    ys.append(y)
    for ys in out.values():
        ys.sort()
    return out
