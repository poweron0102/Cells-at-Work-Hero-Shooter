"""Arma principal e resolucao de acertos (jogadores, colonias e hemacias)."""
import math
import random
from EasyCells3D.Components import Component
from EasyCells3D.Geometry import Vec3
from .catalog import HEROES, CELLS

EYE = .56


def direction(yaw, pitch=0):
    return Vec3(math.sin(yaw)*math.cos(pitch), math.sin(pitch), -math.cos(yaw)*math.cos(pitch))


def ray_sphere(origin, aim, center, radius, max_dist):
    oc = Vec3(origin.x-center[0], origin.y-center[1], origin.z-center[2])
    b = oc.dot(aim)
    c = oc.dot(oc)-radius*radius
    disc = b*b-c
    if disc < 0:
        return None
    t = -b-math.sqrt(disc)
    return t if 0 <= t <= max_dist else None


def cast(actor, aim, max_dist, through=False):
    """Resolve a hitscan ray for ``actor``. Returns list of hits sorted by distance.

    Each hit: dict(kind='actor'|'colony'|'rbc'|'world', target, point, dist).
    With ``through`` the ray passes enemies (antibody beam) and stops at walls.
    """
    arena = actor.arena
    world = actor.game.physics_world
    origin = actor.transform.position+Vec3(0, EYE, 0)
    hits = []
    wall = world.raycast(origin, aim, max_dist, 1 | 8)
    limit = max_dist
    if wall:
        limit = (wall.point-origin).magnitude()
        colony = arena.colony_for_body(wall.body)
        if colony is not None and actor.team == CELLS:
            hits.append(dict(kind='colony', target=colony, point=wall.point, dist=limit))
        elif colony is None:
            hits.append(dict(kind='world', target=None, point=wall.point, dist=limit))
        else:
            hits.append(dict(kind='world', target=None, point=wall.point, dist=limit))
    enemy_group = 4 if actor.team == CELLS else 2
    for other in arena.actors.values():
        if other.team == actor.team or not other.alive or not other.body.enable:
            continue
        p = other.transform.position
        # Capsule approximated by two spheres (body + head) to allow headshots.
        for center, radius, head in (((p.x, p.y-.15, p.z), .5, False), ((p.x, p.y+.62, p.z), .32, True)):
            t = ray_sphere(origin, aim, center, radius, limit)
            if t is not None:
                hits.append(dict(kind='actor', target=other, point=origin+aim*t, dist=t, head=head))
                break
    if actor.team != CELLS:
        for ident, cell in arena.rbc_view.cells.items():
            if cell['state'] in ('dead', 'inside'):
                continue
            x, y, z = cell['pos']
            t = ray_sphere(origin, aim, (x, y+.9, z), .55, limit)
            if t is not None:
                hits.append(dict(kind='rbc', target=ident, point=origin+aim*t, dist=t))
    hits.sort(key=lambda h: h['dist'])
    if not through:
        return hits[:1]
    out = []
    for h in hits:
        out.append(h)
        if h['kind'] in ('world', 'colony'):
            break
    return out


def impact_kind(hits):
    """Tipo de impacto visual do primeiro acerto: 'actor' (corpo), 'world' (superfície) ou None."""
    if not hits:
        return None
    return 'actor' if hits[0]['kind'] in ('actor', 'rbc') else 'world'


class Weapon(Component):
    def __init__(self, actor):
        self.actor = actor
        self.timer = 0
        self.reload_time = 0
        self.ammo = HEROES[actor.hero].magazine
        self.rng = random.Random(actor.slot + 12)
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
        self.timer = kit.interval*(.6 if a.hero == 'streptococcus' and a.boost > 0 else 1)
        if a.hero == "killer_t":
            self.burst = (self.burst+1) % 3
            self.timer = .09 if self.burst else .4
        self.ammo -= 1
        a.shot += 1
        pellets = 7 if a.hero == "macrophage" else 1
        zoomed = a.hero == 'b_cell' and a.zoom
        for _ in range(pellets):
            spread = .09 if pellets > 1 else (0 if zoomed else .008)
            aim = direction(a.yaw + self.rng.uniform(-spread, spread), a.pitch + self.rng.uniform(-spread, spread))
            hits = cast(a, aim, 55 if pellets == 1 else 18)
            origin = a.transform.position+Vec3(0, EYE, 0)
            endpoint = hits[0]['point'] if hits else origin+aim*45
            a.arena.tracer(origin.to_tuple, endpoint.to_tuple, 'shot', a.slot, impact_kind(hits))
            if hits and a.hero == "pseudomonas":
                a.zone("acid", 1.4, 2, endpoint.to_tuple)
            if not hits:
                continue
            damage = kit.damage*(1.4 if a.boost > 0 and a.team == CELLS else 1)*(1.15 if zoomed else 1)
            if a.hero == "pseudomonas" and hits[0]['kind'] == 'actor':
                target = hits[0]['target']
                if target.health.value < HEROES[target.hero].health*.5:
                    damage *= 1.3
            a.apply_hit(hits[0], damage)


def melee_targets(actor, reach, arc_cos=.3, include_rbc=False):
    """Enemies in front of the actor within ``reach`` (visible), for melee kits."""
    arena = actor.arena
    forward = direction(actor.yaw)
    p = actor.transform.position
    out = []
    for other in arena.actors.values():
        if other.team == actor.team or not other.alive:
            continue
        d = other.transform.position-p
        flat = Vec3(d.x, 0, d.z)
        dist = flat.magnitude()
        if dist <= reach+.45 and abs(d.y) < 2.2 and (dist < .6 or flat.normalize().dot(forward) >= arc_cos) and arena.visible(actor, other):
            out.append(('actor', other))
    if actor.team == CELLS:
        for colony in arena.state.colonies:
            c = colony['pos']
            if math.dist((c[0], c[1], c[2]), (p.x, p.y-.95, p.z)) <= reach+1.3:
                out.append(('colony', colony['id']))
    elif include_rbc:
        for ident, cell in arena.rbc_view.cells.items():
            if cell['state'] in ('dead', 'inside'):
                continue
            x, y, z = cell['pos']
            if math.dist((x, y+.9, z), (p.x, p.y, p.z)) <= reach+.6:
                out.append(('rbc', ident))
    return out
