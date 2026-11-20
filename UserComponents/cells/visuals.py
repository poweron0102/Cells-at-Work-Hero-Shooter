"""Renderizadores de combate e objetivos registrados no Camera3D do motor."""
import math
import random
import time
import pyray as rl
from EasyCells3D.Components.Camera3D import Renderable3D
from EasyCells3D.Geometry import Vec3
from .catalog import CELLS, BALANCE, HEROES

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
    render_order = 10  # depois do SilhouettePass (5), que precisa so do cenario no buffer de profundidade

    def __init__(self, actor):
        self.actor = actor
        self.last_position = None
        self.phase = 0
        self.args = None  # pose deste quadro (calculada uma vez, usada tambem pela silhueta)
        self.motion = None
        self.air_since = self.land_at = None
        self.pose_at = 0.0
        self.speed = 0.0

    def on_destroy(self):
        from .model_lighting import release
        super().on_destroy()
        release()

    def camera_inside(self):
        """Espectador na visao deste ator: a camera fica dentro do modelo, entao nao desenha."""
        cam = self.camera.transform.position if self.camera else None
        return cam is not None and (cam-self.actor.transform.position-Vec3(0, .6, 0)).magnitude() < 1.0

    def prepare(self):
        """Pose do quadro para ``CharacterModel.draw`` (idempotente ate o render deste quadro)."""
        if self.args is not None:
            return self.args
        a = self.actor
        p = a.transform.position
        delta = p-self.last_position if self.last_position else Vec3(0, 0, 0)
        distance = delta.magnitude()
        self.last_position = Vec3(p.x, p.y, p.z)
        horizontal = math.hypot(delta.x, delta.z)
        self.phase += min(horizontal, .5)*2.3 if a.hero == 'macrophage' else min(distance, .5)*5
        revealed = a.reveal > 0 or a.marked > 0
        tint = None
        if a.hurt > 0:
            tint = rl.Color(255, 170, 170, 255)
        now = time.perf_counter()
        since = now - a.fire_time
        kick = max(0.0, 1 - since / .14) ** 2 if since >= 0 else 0.0
        moving = distance > .002
        if a.hero == 'macrophage':
            from .weapons import smooth
            dt, self.pose_at = now - self.pose_at, now
            if dt > .2 or distance > 1.4:
                self.air_since = self.land_at = None
                self.speed = 0.0
            else:
                speed = horizontal / max(dt, 1e-4)
                self.speed += (speed - self.speed) * min(1.0, dt * 10)
            if a.local:
                airborne = not a.controller.is_grounded
            else:
                airborne = (self.air_since is None and delta.y > .055
                            and delta.y > horizontal * .6
                            or self.air_since is not None and now - self.air_since < .55)
            if airborne and self.air_since is None:
                self.air_since = now
            elif not airborne and self.air_since is not None:
                self.land_at, self.air_since = now, None
            moving = self.speed > .3
            speed = HEROES[a.hero].speed
            reload = now - a.reload_at
            if a.local:
                reload = 1.6 - a.weapon.reload_time
            self.motion = {'time': now, 'walk': smooth(.3, 1.5, self.speed),
                           'run': smooth(speed * 1.05, speed * 1.25, self.speed),
                           'Fire': since, 'Reload': reload, 'Melee': now - a.melee_at}
            if self.air_since is not None:
                self.motion['Jump'] = now - self.air_since
            elif self.land_at is not None:
                self.motion['Land'] = now - self.land_at
        else:
            self.motion = None
        self.args = (p-Vec3(0, .95, 0), a.yaw, self.phase, moving, 1 if revealed else 0,
                     a.shield.value, a.action, tint, kick)
        return self.args

    def render(self):
        a = self.actor
        session = self.game.session
        local = a.slot == session.local_slot
        if not a.alive or (local and a.third_person < .3) or self.camera_inside():
            self.args = None
            return
        args = self.prepare()
        self.args = None
        a.tp_muzzle = model(a.hero).draw(*args, motion=self.motion)
        me = a.arena.actors.get(session.local_slot)
        if me is not None and me.team != a.team:
            from .outline import ENEMY, draw_outline
            draw_outline(model(a.hero), args, ENEMY, motion=self.motion)


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
        phase = s.escort * math.tau / .65  # Distância de um ciclo completo das duas botas.
        right = (-dz, dx)
        if s.wound_closed:
            # Repair crew spread along the closed wound.
            for i in range(6):
                x = -8+i*3.2
                model('platelet').draw(Vec3(x, 0, -65.2), 0, self.time+i*.31, animation='Repair')
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
            # Health band on a post (visible up close).
            rl.draw_cube(rl.Vector3(x, y+2.9*growth, z), 1.6, .12, .12, color((40, 40, 50)))
            rl.draw_cube(rl.Vector3(x-.8+.8*hp, y+2.9*growth, z), 1.6*hp, .14, .14, color((230, 90, 90)))

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
        self.draw_recon()
        self.draw_crowd()
