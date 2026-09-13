"""Abrasion factories: architecture, physical cover, and navigation data."""
import heapq
from EasyCells3D.Geometry import Vec3
from EasyCells3D.PhysicsComponents3D import PhysicsBody3D, BodyType, BoxShape
from .visuals import Block


def block(game, name, position, size, tint, solid=True):
    item = game.CreateItem()
    item.name = name
    item.transform.position = Vec3(*position)
    item.AddComponent(Block(Vec3(*size), tint))
    if solid:
        item.AddComponent(PhysicsBody3D(BoxShape(Vec3(*size) * .5), body_type=BodyType.STATIC))
    return item


def build_abrasion(game):
    block(game, "Epithelium floor", (0, -.5, 0), (52, 1, 62), (201, 172, 153))
    obstacles = []
    def wall(name, pos, size, tint):
        obstacles.append((pos[0], pos[2], size[0], size[2]))
        return block(game, name, pos, size, tint)
    for x in (-26, 26):
        wall("Tissue perimeter", (x, 4, 0), (2, 8, 62), (155, 96, 97))
    for z in (-31, 31):
        wall("Tissue perimeter", (0, 4, z), (54, 8, 2), (155, 96, 97))
    for x in (-7, 7):
        for z in (-10, 12):
            wall("Epithelial service building", (x, 2.5, z), (4, 5, 8), (194, 137, 124))
            block(game, "Cornice", (x, 5.1, z), (4.4, .25, 8.4), (239, 210, 176), False)
            for zz in (z-2, z+2):
                block(game, "Teal service window", (x + (-2.02 if x < 0 else 2.02), 2.8, zz), (.06, 1.7, 1.4), (50, 99, 99), False)
    for x, z in [(-17, 8), (17, 8), (-17, -8), (17, -8), (-2, -21), (3, 20)]:
        wall("Oxygen freight / cover", (x, .8, z), (3.4, 1.6, 2.5), (91, 135, 129))
        block(game, "Freight band", (x, .82, z), (3.5, .22, 2.6), (215, 213, 173), False)
    for x in (-20, 0, 20):
        block(game, "Vascular route", (x, .012, 0), (.18, .02, 56), (224, 207, 163), False)
    for z in range(-26, 28, 6):
        block(game, "Route markings", (0, .018, z), (2, .02, .3), (246, 231, 199), False)
    block(game, "Cell entry", (0, .02, 25), (12, .03, 5), (74, 158, 153), False)
    block(game, "Bacterial breach", (0, .02, -26), (12, .03, 5), (170, 105, 140), False)
    gate = game.CreateItem()
    gate.name = "Coagulation passage"
    gate.transform.position = Vec3(0, 1.8, 7)
    body = gate.AddComponent(PhysicsBody3D(BoxShape(Vec3(3, 1.8, .4)), body_type=BodyType.STATIC))
    body.enable = False
    return Navigator(obstacles), body


class Navigator:
    """Small static-grid A* for training combatants; collision remains in Bullet."""
    def __init__(self, obstacles):
        self.obstacles = obstacles
        self.free = {(x, z) for x in range(-12, 13) for z in range(-14, 15)
                     if not any(abs(x*2 - ox) < sx/2 + .65 and abs(z*2 - oz) < sz/2 + .65
                                for ox, oz, sx, sz in obstacles)}

    def path(self, start, target):
        def node(p):
            return min(self.free, key=lambda n: (n[0]*2-p.x)**2 + (n[1]*2-p.z)**2)
        first, last = node(start), node(target)
        queue, costs, parent = [(0, first)], {first: 0}, {}
        while queue:
            _, current = heapq.heappop(queue)
            if current == last:
                path = [target]
                while current != first:
                    path.append(Vec3(current[0]*2, 1, current[1]*2))
                    current = parent[current]
                return list(reversed(path))
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                other = current[0]+dx, current[1]+dz
                cost = costs[current] + 1
                if other in self.free and cost < costs.get(other, 10000):
                    costs[other], parent[other] = cost, current
                    heapq.heappush(queue, (cost + abs(other[0]-last[0])+abs(other[1]-last[1]), other))
        return []
