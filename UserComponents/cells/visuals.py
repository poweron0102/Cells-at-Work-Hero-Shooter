"""Renderizadores de combate e objetivos registrados no Camera3D do motor."""
import math
import random
import time
import pyray as rl
from EasyCells3D.Components.Camera3D import Renderable3D
from EasyCells3D.Geometry import Vec3
from .catalog import CELLS, BALANCE

TEAM_RING = {True: (80, 224, 189), False: (236, 155, 99)}


def color(rgb, alpha=255):
    return rl.Color(int(rgb[0]), int(rgb[1]), int(rgb[2]), int(alpha))


def model(key):
    from .models import CharacterModel
    cache = model.__dict__.setdefault('cache', {})
    if key not in cache:
        cache[key] = CharacterModel(key)
    return cache[key]


class Block(Renderable3D):
    def __init__(self, size, tint):
        self.size, self.tint = size, tint

    def render(self):
        p = self.global_transform.position.to_raylib()
        rl.draw_cube_v(p, self.size.to_raylib(), color(self.tint))
        rl.draw_cube_wires_v(p, self.size.to_raylib(), color(tuple(int(v * .77) for v in self.tint)))


class CombatantVisual(Renderable3D):
    def __init__(self, actor):
        self.actor = actor
        self.last_position = None
        self.phase = 0

    def on_destroy(self):
        from .model_lighting import release
        super().on_destroy()
        release()

    def render(self):
        a = self.actor
        session = self.game.session
        local = a.slot == session.local_slot
        if not a.alive or local:
            return
        p = a.transform.position
        distance = (p-self.last_position).magnitude() if self.last_position else 0
        self.last_position = Vec3(p.x, p.y, p.z)
        self.phase += min(distance, .5)*5
        me = a.arena.actors.get(session.local_slot)
        revealed = a.reveal > 0 or a.marked > 0
        tint = None
        if a.hurt > 0:
            tint = rl.Color(255, 170, 170, 255)
        since = time.perf_counter() - a.fire_time
        kick = max(0.0, 1 - since / .14) ** 2 if since >= 0 else 0.0
        a.tp_muzzle = model(a.hero).draw(p-Vec3(0, .95, 0), a.yaw, self.phase, distance > .002, 1 if revealed else 0,
                                         a.shield.value, a.action, tint, kick)
        friendly = me is not None and me.team == a.team
        rl.draw_cylinder_wires((p-Vec3(0, .92, 0)).to_raylib(), .57, .57, .02, 20, color(TEAM_RING[friendly]))
        if a.guard > 0:
            rl.draw_sphere_wires(p.to_raylib(), 1.05, 8, 10, color((250, 210, 120)))
        if a.capsule > 0:
            rl.draw_sphere_wires(p.to_raylib(), 1.1, 8, 10, color((202, 152, 218)))
        if a.boost > 0:
            rl.draw_cylinder_wires((p-Vec3(0, .9, 0)).to_raylib(), .8, .2, 2.2, 8, color((255, 120, 90), 160))


class ArenaEffects(Renderable3D):
    """Escolta, hemacias, colonias, recursos, zonas, rastros e a ferida."""

    def __init__(self, arena):
        self.arena = arena
        self.time = 0.0
        self.crowd = None

    def draw_platelets(self):
        a, s = self.arena, self.arena.state
        head = a.path.at(s.escort)
        dx, dz = a.path.direction(s.escort)
        yaw = math.atan2(dx, -dz)
        moving = not s.blocked_by and not s.wound_closed
        phase = s.escort*3.2
        right = (-dz, dx)
        if s.wound_closed:
            # Repair crew spread along the closed wound.
            for i in range(6):
                x = -8+i*3.2
                model('platelet').draw(Vec3(x, 0, -65.2), 0, self.time*2+i, False, 0, 0, .5+.5*math.sin(self.time*3+i))
            return
        # A big crate of repair materials carried by the crew (references: platelets carrying loads).
        cx, cy, cz = head
        rl.draw_cube(rl.Vector3(cx, cy+.85, cz), 1.6, 1.0, 1.6, color((214, 168, 104)))
        rl.draw_cube_wires(rl.Vector3(cx, cy+.85, cz), 1.62, 1.02, 1.62, color((120, 84, 50)))
        rl.draw_cube(rl.Vector3(cx, cy+1.36, cz), 1.66, .04, .18, color((120, 84, 50)))
        for i, (f, r) in enumerate(((1.1, -.6), (1.1, .6), (-1.1, -.6), (-1.1, .6), (0, 1.25), (0, -1.25))):
            px = cx+dx*f+right[0]*r
            pz = cz+dz*f+right[1]*r
            model('platelet').draw(Vec3(px, cy, pz), yaw, phase+i*1.7, moving)
        ring = (232, 84, 76) if s.blocked_by else (110, 228, 196)
        rl.draw_cylinder_wires(rl.Vector3(cx, cy+.05, cz), BALANCE['escort_block_distance'], BALANCE['escort_block_distance'], .05, 32, color(ring, 180))
        # Dotted route ahead of the escort.
        for k in range(1, 16):
            p = a.path.at(s.escort+k*1.6)
            rl.draw_cube(rl.Vector3(p[0], p[1]+.06, p[2]), .26, .04, .26, color((255, 255, 255), 200))

    def draw_wound(self):
        s = self.arena.state
        if s.wound_closed:
            for i in range(-9, 10, 2):
                rl.draw_line_3d(rl.Vector3(i, .1, -66), rl.Vector3(i*.8, -2.3, -88), color((236, 172, 196)))
            for j in range(9):
                z = -66-j*2.6
                y = .1-2.4*j/8
                rl.draw_line_3d(rl.Vector3(-9, y, z), rl.Vector3(9, y, z), color((236, 172, 196)))
            rl.draw_plane(rl.Vector3(0, -2.3, -78), rl.Vector2(19, 19), color((236, 172, 196), 120))
        else:
            pulse = .5+.5*math.sin(self.time*2.2)
            rl.draw_sphere(rl.Vector3(0, -3.2, -80), 3.5+pulse*.4, color((120, 40, 60), 120))

    def draw_rbcs(self):
        for ident, cell in self.arena.rbc_view.cells.items():
            if cell['state'] in ('dead', 'inside'):
                continue
            x, y, z = cell['pos']
            model('red_blood_cell').draw(Vec3(x, y, z), cell['yaw'], cell['phase'], cell['moving'],
                                         0, 0, 0, rl.Color(255, 200, 200, 255) if cell['state'] in ('flee', 'hide') else None)
            # Oxygen box carried in front.
            fx, fz = math.sin(cell['yaw']), -math.cos(cell['yaw'])
            rl.draw_cube(rl.Vector3(x+fx*.38, y+1.0, z+fz*.38), .42, .3, .32, rl.Color(240, 244, 248, 255))
            rl.draw_cube(rl.Vector3(x+fx*.38, y+1.0, z+fz*.38), .43, .08, .33, rl.Color(130, 190, 230, 255))
            if cell['state'] in ('flee', 'hide'):
                rl.draw_sphere(rl.Vector3(x, y+2.3+.08*math.sin(self.time*9), z), .12, rl.Color(255, 90, 80, 255))

    def draw_colonies(self):
        a, s = self.arena, self.arena.state
        for colony in s.colonies:
            x, y, z = colony['pos']
            growth = 1+colony['dev']/BALANCE['colony_dev_cap']*.6
            hp = colony['hp']/BALANCE['colony_health']
            rnd = random.Random(colony['id'])
            pulse = math.sin(self.time*2.4+colony['id'])*.06
            base = (150, 84, 170) if colony['id'] % 2 else (110, 170, 96)
            for i in range(9):
                ang = rnd.uniform(0, math.tau)
                r = rnd.uniform(0, .9)*growth
                py = y+rnd.uniform(.4, 1.4)*growth
                rad = rnd.uniform(.38, .62)*growth*(1+pulse)
                shade = .75+.25*rnd.random()
                rl.draw_sphere_ex(rl.Vector3(x+math.cos(ang)*r, py, z+math.sin(ang)*r), rad, 7, 9,
                                  color(tuple(c*shade for c in base)))
            rl.draw_sphere_ex(rl.Vector3(x, y+1.1*growth, z), .72*growth, 9, 11, color((236, 214, 120)))
            for k in range(6):
                ang = k*math.tau/6+self.time*.4
                rl.draw_line_3d(rl.Vector3(x, y+.05, z), rl.Vector3(x+math.cos(ang)*2.4*growth, y+.05, z+math.sin(ang)*2.4*growth),
                                color((120, 70, 140)))
            if colony.get('fortified', 0) > 0:
                rl.draw_sphere_wires(rl.Vector3(x, y+1.1, z), 1.9*growth, 8, 10, color((250, 200, 90)))
            if colony.get('marked', 0) > 0:
                rl.draw_cylinder_wires(rl.Vector3(x, y+.05, z), 2.2*growth, 2.2*growth, .05, 24, color((111, 197, 244)))
            # Health band on a post (visible up close).
            rl.draw_cube(rl.Vector3(x, y+2.9*growth, z), 1.6, .12, .12, color((40, 40, 50)))
            rl.draw_cube(rl.Vector3(x-.8+.8*hp, y+2.9*growth, z), 1.6*hp, .14, .14, color((230, 90, 90)))
        for slot, (x, y, z) in a.builds.items():
            progress = .5+.5*math.sin(self.time*6)
            rl.draw_sphere_wires(rl.Vector3(x, y+.8, z), .9, 6, 8, color((200, 150, 220), 200))
            rl.draw_cylinder(rl.Vector3(x, y+.02, z), 1.2, 1.2, .04+progress*.05, 16, color((160, 100, 190), 150))

    def draw_drops(self):
        for drop in self.arena.drops:
            x, y, z = drop['pos']
            bob = .12*math.sin(self.time*3+drop['id'])
            if drop['kind'] == 'resource':
                rl.draw_sphere(rl.Vector3(x, y+.45+bob, z), .28, rl.Color(236, 90, 76, 255))
                rl.draw_sphere_wires(rl.Vector3(x, y+.45+bob, z), .42, 5, 6, rl.Color(255, 200, 120, 255))
            else:
                rl.draw_cube(rl.Vector3(x, y+.5+bob, z), .3, .3, .3, rl.Color(138, 241, 211, 255))
                rl.draw_cube_wires(rl.Vector3(x, y+.5+bob, z), .44, .44, .44, rl.Color(240, 255, 250, 255))

    def draw_zones(self):
        for zone in self.arena.zones:
            x, y, z = zone["pos"]
            r = zone["radius"]
            kind = zone["kind"]
            tint = {"biofilm": (93, 180, 133), "mature": (60, 140, 90), "acid": (170, 220, 80),
                    "cloud": (157, 121, 189)}.get(kind, (200, 200, 200))
            rl.draw_cylinder(rl.Vector3(x, y-.9, z), r, r, .05, 32, color(tint, 150))
            if kind == "cloud":
                for i in range(6):
                    ang = i*math.tau/6+self.time*.3
                    rl.draw_sphere(rl.Vector3(x+math.cos(ang)*r*.55, y+.4+.2*math.sin(self.time+i), z+math.sin(ang)*r*.55),
                                   r*.45, color(tint, 70))
            if kind == "mature":
                for i in range(5):
                    ang = i*1.7+self.time
                    rl.draw_sphere(rl.Vector3(x+math.cos(ang)*r*.6, y-.7+(self.time*.6+i*.2) % 1.2, z+math.sin(ang)*r*.6), .18, color((150, 220, 150)))

    def draw_effects(self):
        for fx in self.arena.effects:
            x, y, z = fx['pos']
            t = 1-fx['life']/.6
            r = fx['radius']*(.3+.7*t)
            tint = {'slam': (240, 220, 200), 'burst': (170, 230, 90), 'ult': (255, 230, 140), 'repair': (250, 200, 90)}.get(fx['kind'], (255, 255, 255))
            rl.draw_cylinder_wires(rl.Vector3(x, y+.1, z), r, r, .1, 28, color(tint, 255*(1-t)))
            if fx['kind'] in ('burst', 'ult'):
                rl.draw_sphere_wires(rl.Vector3(x, y+1, z), r*.7, 6, 8, color(tint, 255*(1-t)))

    def draw_recon(self):
        from .layout import RECON
        s = self.arena.state
        x, y, z = RECON
        if s.recon_available():
            rl.draw_cylinder_wires(rl.Vector3(x, y+.05, z), BALANCE['recon_radius'], BALANCE['recon_radius'], .05, 32,
                                   color((111, 197, 244)))
            if s.recon > 0:
                k = s.recon/BALANCE['recon_channel']
                rl.draw_cylinder(rl.Vector3(x, y+.03, z), BALANCE['recon_radius']*k, BALANCE['recon_radius']*k, .03, 32,
                                 color((111, 197, 244), 140))
        # The antenna light spins faster while revealing.
        speed = 6 if s.reveal > 0 else 1.5
        ang = self.time*speed
        rl.draw_sphere(rl.Vector3(x+math.cos(ang)*.9, 31.2, z+math.sin(ang)*.9), .25,
                       color((255, 90, 80) if s.reveal > 0 else (255, 220, 120)))

    def draw_crowd(self):
        if self.crowd is None:
            from .layout import AMBIENT_SPOTS
            rnd = random.Random(5)
            spots = AMBIENT_SPOTS[:]
            rnd.shuffle(spots)
            self.crowd = [(p, rnd.choice(('red_blood_cell', 'red_blood_cell', 'platelet')), rnd.uniform(0, math.tau), rnd.random())
                          for p in spots[:40]]
        for (x, y, z, yaw), key, phase, k in self.crowd:
            sway = math.sin(self.time*(1+k)+phase)*.25
            model(key).draw(Vec3(x, y, z), yaw+sway, phase+self.time, False, 0, 0, max(0, math.sin(self.time*.7+phase))*.3*k)

    def render(self):
        self.time += rl.get_frame_time()
        self.draw_wound()
        self.draw_platelets()
        self.draw_rbcs()
        self.draw_colonies()
        self.draw_drops()
        self.draw_zones()
        self.draw_effects()
        self.draw_recon()
        self.draw_crowd()
        me = self.arena.actors.get(self.game.session.local_slot)
        if me and me.alive and me.team != CELLS and getattr(me, 'preview', None):
            x, y, z = me.preview
            ok = not me.build_problem
            tint = (120, 230, 150) if ok else (240, 90, 80)
            rl.draw_cylinder_wires(rl.Vector3(x, y+.05, z), 1.3, 1.3, .05, 24, color(tint))
            if me.build:
                k = me.build['progress']/BALANCE['colony_build_time']
                rl.draw_cylinder(rl.Vector3(x, y+.03, z), 1.3*k, 1.3*k, .04, 24, color(tint, 150))
