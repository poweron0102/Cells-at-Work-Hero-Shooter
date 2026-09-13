"""Layered surface A*: streets, ramp slopes and rooftops can share an X/Z cell."""
import heapq
import math
from EasyCells3D.Geometry import Vec3
from .layout import WIDTH, LENGTH


class Navigator:
    def __init__(self, solids, ramps):
        self.solids, self.ramps, self.gate = solids, ramps, None
        self.columns = {}
        self.free = set()
        self.obstacles = [(s.position[0], s.position[2], s.size[0], s.size[2])
                          for s in solids if s.position[1]-s.size[1]/2 < 1.9]
        for x in range(-WIDTH//2+2, WIDTH//2, 2):
            for z in range(-LENGTH//2+2, LENGTH//2, 2):
                heights = {0.0}
                heights.update(s.top for s in solids if s.top < 10 and s.contains(x, z, -.5))
                heights.update(h for r in ramps if (h := r.surface(x, z)) is not None)
                nodes = []
                for y in sorted(heights):
                    if any(s.contains(x, z, .48) and s.top > y+.12
                           and s.position[1]-s.size[1]/2 < y+1.95 for s in solids):
                        continue
                    if any((h := r.surface(x, z)) is not None and h > y+.12 for r in ramps):
                        continue
                    node = (x, round(y, 3), z)
                    nodes.append(node)
                    self.free.add(node)
                self.columns[x, z] = nodes

    def _crosses_gate(self, a, b):
        if not self.gate or not self.gate.enable:
            return False
        return (min(a[2], b[2]) <= 7.85 and max(a[2], b[2]) >= 6.15
                and min(abs(a[0]), abs(b[0])) < 3.5 and min(a[1], b[1]) < 3.6)

    def path(self, start, target, jump_height=1.2):
        def nearest(p):
            return min(self.free, key=lambda n: (n[0]-p.x)**2+(n[2]-p.z)**2+4*(n[1]+.95-p.y)**2)
        first, last = nearest(start), nearest(target)
        queue, costs, parent = [(0, first)], {first: 0}, {}
        while queue:
            _, current = heapq.heappop(queue)
            if current == last:
                nodes = [current]
                while nodes[-1] != first:
                    nodes.append(parent[nodes[-1]])
                return [Vec3(x, y+.95, z) for x, y, z in reversed(nodes)]
            for dx, dz in ((2, 0), (-2, 0), (0, 2), (0, -2)):
                for other in self.columns.get((current[0]+dx, current[2]+dz), ()):
                    rise = other[1]-current[1]
                    if rise > jump_height-.15 or rise < -4.1 or self._crosses_gate(current, other):
                        continue
                    # Never route through the side of a building/under a low lintel.
                    mx, mz = (current[0]+other[0])/2, (current[2]+other[2])/2
                    high = max(current[1], other[1])
                    if any(s.contains(mx, mz, .45) and s.top > high+.12
                           and s.position[1]-s.size[1]/2 < high+1.95 for s in self.solids):
                        continue
                    cost = costs[current]+2+abs(rise)*.5+(2 if rise > .7 else 0)
                    if cost < costs.get(other, math.inf):
                        costs[other], parent[other] = cost, current
                        heapq.heappush(queue, (cost+abs(other[0]-last[0])+abs(other[2]-last[2]), other))
        return []
