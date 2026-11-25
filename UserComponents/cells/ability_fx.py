"""VFX das habilidades: zonas, ondas de choque, membrana/barreira, domo, parede, torretas,
clones, granadas, previas de posicionamento e aneis de equipe.

Substitui os antigos wireframes por quads texturizados (texturas procedurais compartilhadas
com shots.py) em mistura aditiva/alfa, sem escrever profundidade. Regra de legibilidade:
o contorno de tudo que e de um jogador usa a cor fixa da equipe relativa a quem olha
(aliado = turquesa, inimigo = vermelho); o miolo usa a cor tematica do heroi.
"""
import math
import random
import time

import pyray as rl

from EasyCells3D.Components.Camera3D import Renderable3D
from EasyCells3D.Geometry import Vec3
from . import shots
from .shots import Batch, billboard, ribbon, quad, ADD, ALPHA
from .catalog import BALANCE, CELLS
from .combat import direction

ALLY = (40, 222, 210)
ENEMY = (255, 76, 86)
GOLD = (250, 199, 55)
FLAT_R, FLAT_U = (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)

ZONE_TINT = {'biofilm': (93, 200, 133), 'mature': (70, 170, 90), 'acid': (170, 230, 70), 'cloud': (170, 120, 210),
             'rain': (110, 190, 255), 'dome': (250, 196, 80)}
FX_TINT = {'slam': (240, 226, 206), 'burst': (170, 236, 80), 'ult': (255, 230, 140), 'repair': (250, 200, 90),
           'antibody': (120, 200, 255), 'spit': (255, 140, 190), 'shatter': (200, 150, 255),
           'perforin': (255, 70, 70), 'heal': (120, 255, 170), 'punch': (255, 150, 90), 'backstab': (255, 90, 90),
           'spawn': (140, 220, 255), 'pop': (255, 170, 210), 'crumble': (230, 170, 70), 'launch': (240, 226, 206)}
LEAP_TINT = (255, 140, 90)


# --------------------------------------------------------------------------------------
# Texturas extras (registradas no cache de shots.py e liberadas com ele)
# --------------------------------------------------------------------------------------

def _disc(u, v):
    r = math.hypot(u, v)
    if r > 1:
        return 0.0
    rim = max(0.0, 1-abs(r-.9)/.1)
    return .32*(r**2)+rim


def _hex(u, v):
    r = math.hypot(u, v)
    if r > 1:
        return 0.0
    # grade hexagonal: distancia ao centro da celula mais proxima
    s = 7.0
    x, y = u*s, v*s
    q = (2/3*x)
    rr = (-1/3*x+math.sqrt(3)/3*y)
    cq, cr = round(q), round(rr)
    cx = 1.5*cq
    cy = math.sqrt(3)*(cr+cq/2)
    d = math.hypot(x-cx, y-cy)
    edge = max(0.0, min(1.0, (d-.62)/.3))
    rim = max(0.0, 1-abs(r-.92)/.08)
    return min(1.0, (.18+.82*edge)*(1-r*.35)+rim)


def _hexrect(u, v):
    """Coagulo: favo hexagonal com borda retangular brilhante (paredes)."""
    s = 5.0
    x, y = u*s*1.6, v*s
    q = (2/3*x)
    rr = (-1/3*x+math.sqrt(3)/3*y)
    cq, cr = round(q), round(rr)
    cx = 1.5*cq
    cy = math.sqrt(3)*(cr+cq/2)
    d = math.hypot(x-cx, y-cy)
    cell = .35+.45*max(0.0, min(1.0, (d-.55)/.35))
    border = max(0.0, 1-min(1-abs(u), 1-abs(v))/.06)
    return min(1.0, cell+border)


def _puff(u, v):
    r = math.hypot(u, v)
    n = .5+.5*math.sin(u*7.1+math.cos(v*5.3)*2)*math.cos(v*6.2-u*2.4)
    return max(0.0, max(0.0, 1-r)**1.6*(.65+.35*n))


def _net(u, v):
    r = math.hypot(u, v)
    if r > 1:
        return 0.0
    a = abs(math.sin(u*9))+abs(math.sin(v*9))
    line = max(0.0, 1-min(abs(math.sin((u+v)*7)), abs(math.sin((u-v)*7)))*5)
    return line*(1-r**4)+max(0.0, 1-abs(r-.93)/.07)


def _y(u, v):
    """Anticorpo (Y)."""
    def seg(ax, ay, bx, by):
        px, py = u-ax, v-ay
        dx, dy = bx-ax, by-ay
        t = max(0.0, min(1.0, (px*dx+py*dy)/(dx*dx+dy*dy)))
        return math.hypot(px-dx*t, py-dy*t)
    d = min(seg(0, .9, 0, 0), seg(0, 0, -.6, -.75), seg(0, 0, .6, -.75))
    return max(0.0, 1-d/.18)


def textures():
    tex = shots.textures()
    if 'disc' not in tex:
        shots._make('disc', 128, 128, _disc)
        shots._make('hex', 128, 128, _hex)
        shots._make('hexrect', 128, 64, _hexrect)
        shots._make('puff', 64, 64, _puff)
        shots._make('net', 64, 64, _net)
        shots._make('y', 32, 32, _y)
    return tex


def team_color(owner, me):
    if owner is None or me is None:
        return ALLY
    return ALLY if owner.team == me.team else ENEMY


def surface_basis(normal):
    """Eixos (direita, cima) de um quad deitado na superficie de ``normal`` (None = chao plano)."""
    if normal is None:
        return FLAT_R, FLAT_U
    nx, ny, nz = normal
    hx, hy, hz = (0.0, 1.0, 0.0) if abs(ny) < .9 else (1.0, 0.0, 0.0)
    ax, ay, az = hy*nz-hz*ny, hz*nx-hx*nz, hx*ny-hy*nx
    k = math.sqrt(ax*ax+ay*ay+az*az) or 1.0
    ax, ay, az = ax/k, ay/k, az/k
    return (ax, ay, az), (ny*az-nz*ay, nz*ax-nx*az, nx*ay-ny*ax)


def ground(batch, pos, radius, tint, alpha, tex='ring', blend=ADD, angle=0.0, lift=.06, normal=None):
    """Quad deitado no chao (ou colado na superficie de ``normal``: rampa, parede, teto)."""
    x, y, z = pos
    r, u = surface_basis(normal)
    n = normal or (0.0, 1.0, 0.0)
    batch.add((blend, tex), billboard, (x+n[0]*lift, y+n[1]*lift, z+n[2]*lift), radius, r, u, tint,
              int(max(0, min(255, alpha))), angle)


def vertical(batch, center, right, half_w, half_h, tint, alpha, tex, blend=ADD):
    cx, cy, cz = center
    rx, ry, rz = right[0]*half_w, right[1]*half_w, right[2]*half_w
    batch.add((blend, tex), quad, (cx-rx, cy+half_h, cz-rz), (cx+rx, cy+half_h, cz+rz), (cx+rx, cy-half_h, cz+rz),
              (cx-rx, cy-half_h, cz-rz), tint, int(max(0, min(255, alpha))))


def model(key):
    from .visuals import model as cached
    return cached(key)


class AbilityEffects(Renderable3D):
    render_order = 45

    def __init__(self, arena):
        self.arena = arena
        self.time = 0.0
        self.last = time.perf_counter()
        self.rng = random.Random(3)

    # -- utilitarios --------------------------------------------------------------------
    def me(self):
        return self.arena.actors.get(self.game.session.local_slot)

    def render(self):
        now = time.perf_counter()
        dt = min(.05, max(0.0, now-self.last))
        self.last = now
        self.time += dt
        cam = self.camera
        if cam is None:
            return
        t = cam.global_transform
        eye = t.position.to_tuple
        fwd, up = t.forward, t.up
        right = fwd.cross(up).normalize()
        R, U = right.to_tuple, up.to_tuple
        textures()
        me = self.me()
        # Solidos primeiro (modelos com profundidade).
        self.draw_minions(me)
        batch = Batch()
        self.draw_team_rings(batch, me)
        self.draw_objective_rings(batch, me)
        self.draw_zones(batch, me, eye, R, U)
        self.draw_effects(batch, eye, R, U)
        self.draw_fronts(batch, me, eye)
        self.draw_status(batch, me, R, U)
        self.draw_projectiles(batch, eye, R, U, me)
        self.draw_previews(batch, me, R, U)
        self.draw_minion_rings(batch, me)
        rl.rl_draw_render_batch_active()
        rl.rl_disable_depth_mask()
        rl.rl_disable_backface_culling()
        self.draw_volumes(me)
        rl.rl_draw_render_batch_active()
        for wall, edge, h, fade in self.wall_faces:
            x, y, z = wall['pos']
            right = (math.cos(wall['yaw']), 0.0, math.sin(wall['yaw']))
            n = (-right[2], 0.0, right[0])
            for side in (-1, 1):
                c = (x+n[0]*.31*side, y+h/2, z+n[2]*.31*side)
                vertical(batch, c, right, BALANCE['wall_width']/2, h/2, (226, 120, 50), int(200*fade), 'hexrect', ALPHA)
                vertical(batch, c, right, BALANCE['wall_width']/2, h/2, (255, 190, 90), int(70*fade), 'hexrect')
        batch.flush()
        rl.rl_enable_backface_culling()
        rl.rl_enable_depth_mask()

    # -- volumes translucidos (domo, parede) --------------------------------------------
    def draw_volumes(self, me):
        self.wall_faces = []
        for zone in self.arena.zones:
            if zone['kind'] != 'dome':
                continue
            owner = self.arena.actors.get(zone['owner'])
            edge = team_color(owner, me)
            grow = min(1.0, zone.get('age', 1)/.35)
            fade = min(1.0, zone['life']/.6)
            x, y, z = zone['pos']
            r = zone['radius']*(.6+.4*grow)
            tint = tuple(int(a*.55+b*.45) for a, b in zip(ZONE_TINT['dome'], edge))
            rl.begin_blend_mode(ALPHA)
            rl.draw_sphere_ex(rl.Vector3(x, y, z), r, 18, 24, rl.Color(*tint, int(28*fade)))
            rl.end_blend_mode()
        for ident, wall in self.arena.walls.items():
            owner = self.arena.actors.get(ident//1000)
            edge = team_color(owner, me)
            grow = min(1.0, (wall['max']-wall['life'])/.25)
            fade = min(1.0, wall['life']/.5)
            x, y, z = wall['pos']
            h = 2.6*grow
            rl.rl_push_matrix()
            rl.rl_translatef(x, y+h/2, z)
            rl.rl_rotatef(-math.degrees(wall['yaw']), 0, 1, 0)
            rl.begin_blend_mode(ALPHA)
            rl.draw_cube(rl.Vector3(0, 0, 0), BALANCE['wall_width'], h, .6, rl.Color(170, 70, 40, int(70*fade)))
            rl.draw_cube(rl.Vector3(0, h/2-.03, 0), BALANCE['wall_width']+.04, .06, .62, rl.Color(*edge, int(230*fade)))
            rl.end_blend_mode()
            rl.rl_pop_matrix()
            self.wall_faces.append((wall, edge, h, fade))

    # -- aneis de equipe e objetivos ----------------------------------------------------
    def draw_team_rings(self, batch, me):
        session = self.game.session
        for a in self.arena.actors.values():
            if not a.alive or (a.slot == session.local_slot and a.third_person < .3):
                continue
            p = a.transform.position
            feet = (p.x, p.y-.93, p.z)
            tint = team_color(a, me)
            ground(batch, feet, .62, tint, 210, 'ring')
            ground(batch, feet, .5, tint, 60, 'disc', ALPHA)
            if a.fx.get('ult', 0) > 0:
                pulse = .5+.5*math.sin(self.time*8)
                ground(batch, feet, 1.1+.15*pulse, GOLD, 200, 'ring')
                ground(batch, feet, 1.0, GOLD, 70, 'glow')

    def draw_objective_rings(self, batch, me):
        a, s = self.arena, self.arena.state
        if not s.wound_closed:
            head = a.path.at(s.escort)
            tint = (232, 84, 76) if s.blocked_by else (110, 228, 196)
            r = BALANCE['escort_block_distance']
            ground(batch, head, r, tint, 150, 'ring', angle=self.time*.2)
            ground(batch, head, r, tint, 26, 'disc', ALPHA)
        for colony in s.colonies:
            growth = 1+colony['dev']/BALANCE['colony_dev_cap']*.6
            if colony.get('marked', 0) > 0:
                ground(batch, colony['pos'], 2.4*growth, (111, 197, 244), 230, 'ring', angle=-self.time)
            if colony.get('fortified', 0) > 0:
                x, y, z = colony['pos']
                batch.add((ADD, 'hex'), billboard, (x, y+1.1*growth, z), 2.0*growth, (1, 0, 0), (0, 1, 0), GOLD, 90)
        for slot, (x, y, z) in a.builds.items():
            k = .5+.5*math.sin(self.time*6)
            ground(batch, (x, y, z), 1.3, (200, 150, 230), 200, 'ring')
            ground(batch, (x, y, z), 1.2*k, (160, 100, 190), 120, 'disc', ALPHA)
        if me and me.alive and me.team != CELLS and getattr(me, 'preview', None):
            ok = not me.build_problem
            tint = (120, 230, 150) if ok else (240, 90, 80)
            ground(batch, me.preview, 1.3, tint, 230, 'ring')
            if me.build:
                k = me.build['progress']/BALANCE['colony_build_time']
                ground(batch, me.preview, 1.3*k, tint, 140, 'disc', ALPHA)

    # -- zonas ----------------------------------------------------------------------------
    def draw_zones(self, batch, me, eye, R, U):
        for zone in self.arena.zones:
            kind = zone['kind']
            owner = self.arena.actors.get(zone['owner'])
            edge = team_color(owner, me)
            tint = ZONE_TINT.get(kind, (220, 220, 220))
            x, y, z = zone['pos']
            r = zone['radius']
            age = zone.get('age', 1.0)
            grow = min(1.0, age/.3)
            fade = min(1.0, zone['life']/.6)
            k = grow*fade
            floor = (x, y, z)
            normal = zone.get('normal')
            ground(batch, floor, r*grow, edge, 200*k, 'ring', angle=self.time*.3, normal=normal)
            if kind in ('biofilm', 'mature', 'acid'):
                ground(batch, floor, r*.98*grow, tint, 150*k, 'splat', ALPHA, angle=zone['radius']*7+x, normal=normal)
                ground(batch, floor, r*grow, tint, 60*k, 'glow', normal=normal)
                # Bolhas sobem da poca (para fora da superficie, se estiver numa parede/rampa).
                sa, sb = surface_basis(normal)
                nx, ny, nz = normal or (0.0, 1.0, 0.0)
                rng = random.Random(int(x*13+z*7))
                for i in range(5 if kind != 'mature' else 9):
                    ang, rad = rng.uniform(0, math.tau), rng.uniform(0, r*.8)
                    ph = (self.time*.7+rng.random()) % 1.0
                    ca, sn = math.cos(ang)*rad, math.sin(ang)*rad
                    h = .1+ph*(1.2 if kind == 'mature' else .5)
                    bubble = (x+sa[0]*ca+sb[0]*sn+nx*h, y+sa[1]*ca+sb[1]*sn+ny*h, z+sa[2]*ca+sb[2]*sn+nz*h)
                    batch.add((ADD, 'core'), billboard, bubble, .08+.06*rng.random(), R, U, tint,
                              int(200*(1-ph)*k))
            elif kind == 'cloud':
                ground(batch, floor, r*grow, tint, 70*k, 'disc', ALPHA)
                for i in range(16):
                    ang = i*math.tau/16+self.time*(.25 if i % 2 else -.18)
                    rad = r*(.25+.6*((i*37) % 10)/10)
                    h = .6+1.6*((i*53) % 10)/10+.25*math.sin(self.time+i)
                    batch.add((ALPHA, 'puff'), billboard, (x+math.cos(ang)*rad, y+h, z+math.sin(ang)*rad),
                              r*.42*grow, R, U, tint, int(95*k), self.time*.2+i)
            elif kind == 'rain':
                ground(batch, floor, r*grow, tint, 70*k, 'disc', ALPHA)
                ground(batch, floor, r*grow, tint, 120*k, 'glow')
                rng = random.Random(7)
                for i in range(34):
                    ang, rad = rng.uniform(0, math.tau), math.sqrt(rng.random())*r
                    speed, off = rng.uniform(14, 20), rng.random()
                    fall = ((self.time*speed/12+off) % 1.0)
                    px, pz = x+math.cos(ang)*rad, z+math.sin(ang)*rad
                    py = y+12*(1-fall)
                    batch.add((ADD, 'beam'), ribbon, (px, py+1.4, pz), (px, py, pz), .07, eye, (170, 220, 255), int(140*k))
                    batch.add((ADD, 'y'), billboard, (px, py, pz), .22, R, U, (220, 240, 255), int(255*k))
                    if fall > .93:
                        ground(batch, (px, y, pz), .5*(fall-.93)/.07+.2, (200, 235, 255), 200*k, 'ring')
            elif kind == 'dome':
                ground(batch, floor, r*grow, tint, 30*k, 'disc', ALPHA)
                for i in range(2):
                    ph = (self.time*.5+i/3) % 1.0
                    batch.add((ADD, 'ring'), billboard, (x, y+r*.05+ph*r*.9, z), r*math.sqrt(max(0.0, 1-ph*ph))*grow,
                              FLAT_R, FLAT_U, edge, int(55*(1-ph)*k))

    # -- efeitos pontuais (ondas de choque etc.) ----------------------------------------
    def draw_effects(self, batch, eye, R, U):
        for fx in self.arena.effects:
            kind = fx['kind']
            x, y, z = fx['pos']
            t = 1-fx['life']/.6
            tint = FX_TINT.get(kind, (255, 255, 255))
            r = fx['radius']
            a = 1-t
            if kind == 'spit' and fx.get('extra') is not None:
                f = direction(fx['extra'])
                for i in range(6):
                    d = (t+i*.06)*r
                    if d > r:
                        continue
                    px, pz = x+f.x*d, z+f.z*d
                    batch.add((ADD, 'ring'), billboard, (px, y+1.0, pz), .6+d*.45, (math.cos(fx['extra']), 0, math.sin(fx['extra'])),
                              (0, 1, 0), tint, int(130*a*(1-i/6)))
                continue
            if kind in ('ult', 'spawn', 'pop', 'heal', 'perforin', 'backstab', 'punch', 'shatter'):
                batch.add((ADD, 'star' if kind in ('pop', 'backstab', 'punch', 'shatter') else 'glow'), billboard,
                          (x, y+(1.0 if kind == 'ult' else .2), z), r*(.4+.8*t), R, U, tint, int(230*a))
            if kind == 'heal' or kind == 'ult':
                for i in range(8):
                    ang = i*math.tau/8+t*2
                    batch.add((ADD, 'core'), billboard, (x+math.cos(ang)*.8, y+.2+t*2.2, z+math.sin(ang)*.8), .09,
                              R, U, tint, int(255*a))
            if kind == 'crumble' and fx.get('extra') is not None:
                rgt = (math.cos(fx['extra']), 0, math.sin(fx['extra']))
                for i in range(12):
                    s = (i/11-.5)*BALANCE['wall_width']
                    batch.add((ALPHA, 'core'), billboard, (x+rgt[0]*s, y+1.3-t*t*2.6+(i % 3)*.3, z+rgt[2]*s), .25,
                              R, U, tint, int(230*a))
                continue
            if kind == 'slam' and fx.get('extra') == 'leap':
                # Salto de impacto: clarao, segunda onda rapida, rachaduras e poeira subindo.
                batch.add((ADD, 'star'), billboard, (x, y+.5, z), r*.55*(1-t)+.3, R, U, LEAP_TINT, int(255*a))
                ground(batch, (x, y, z), r*(.15+1.25*t**.6), LEAP_TINT, 230*a*a, 'ring')
                ground(batch, (x, y, z), r*.75, (60, 40, 30), 150*a, 'splat', ALPHA, angle=x+z)
                rng = random.Random(int(x*13+z*29))
                for i in range(14):
                    ang = i*math.tau/14+rng.uniform(-.2, .2)
                    d = r*(.35+.75*t)*rng.uniform(.7, 1)
                    h = .2+t*rng.uniform(.6, 1.8)
                    batch.add((ALPHA, 'puff'), billboard, (x+math.cos(ang)*d, y+h, z+math.sin(ang)*d),
                              .45+.9*t, R, U, (205, 190, 170), int(150*a), ang)
            elif kind == 'launch':
                for i in range(8):
                    ang = i*math.tau/8
                    d = r*(.3+.7*t)
                    batch.add((ALPHA, 'puff'), billboard, (x+math.cos(ang)*d, y+.15+t*.5, z+math.sin(ang)*d),
                              .3+.5*t, R, U, tint, int(140*a), ang)
            # Onda no chao (todas as outras).
            ground(batch, (x, y, z), r*(.25+.75*t), tint, 255*a, 'ring', normal=fx.get('normal'))
            ground(batch, (x, y, z), r*(.2+.8*t), tint, 90*a, 'disc', ALPHA, normal=fx.get('normal'))
            if kind in ('slam', 'burst', 'antibody'):
                rng = random.Random(int(x*31+z*17))
                for i in range(10):
                    ang = rng.uniform(0, math.tau)
                    d = r*(.2+.7*t)*rng.uniform(.6, 1)
                    h = math.sin(min(1.0, t*1.4)*math.pi)*rng.uniform(.3, 1.3)
                    batch.add((ADD if kind != 'slam' else ALPHA, 'y' if kind == 'antibody' else 'core'), billboard,
                              (x+math.cos(ang)*d, y+.1+h, z+math.sin(ang)*d), .14 if kind != 'antibody' else .3,
                              R, U, tint, int(230*a), ang)

    # -- membrana do Engolir / barreira -------------------------------------------------
    def draw_fronts(self, batch, me, eye):
        session = self.game.session
        for a in self.arena.actors.values():
            if not a.alive or not a.front or a.front_radius <= 0:
                continue
            if a.slot == session.local_slot and a.third_person < .3:
                continue
            c = a.front_center()
            right = (math.cos(a.yaw), 0.0, math.sin(a.yaw))
            r = a.front_radius
            edge = team_color(a, me)
            wobble = 1+.04*math.sin(self.time*9)
            flash = 1.0 if a.absorbed_fx > 0 or a.fx.get('absorb', 0) > 0 else 0.0
            if a.front == 'engulf':
                pink = (255, 120, 170)
                behind = a.slot == session.local_slot
                vertical(batch, c, right, r*wobble, r/wobble, pink, (45 if behind else 90)+60*flash, 'disc', ALPHA)
                vertical(batch, c, right, r*1.05, r*1.05, edge, 170, 'ring')
                vertical(batch, c, right, r*.6*wobble, r*.6, (255, 190, 220), (15 if behind else 35)+45*flash, 'glow')
            else:
                purple = (190, 140, 255)
                k = a.barrier_hp/BALANCE['barrier_health'] if a.local else 1.0
                vertical(batch, c, right, r*1.25, r, purple, 120+80*flash, 'hex')
                vertical(batch, c, right, r*1.28, r*1.03, edge, 170*(.5+.5*k), 'ring')

    # -- estados sobre os herois ----------------------------------------------------------
    def draw_status(self, batch, me, R, U):
        session = self.game.session
        for a in self.arena.actors.values():
            if not a.alive or (a.slot == session.local_slot and a.third_person < .3):
                continue
            p = a.transform.position
            if a.fx.get('root', 0) > 0:
                ground(batch, (p.x, p.y-.93, p.z), .9, (240, 240, 230), 230, 'net', ALPHA, self.time)
            if a.fx.get('leap', 0) > 0:
                self.draw_leap_trail(batch, a, R, U)
            if a.fx.get('perforin', 0) > 0:
                pulse = .5+.5*math.sin(self.time*(6+12*(1-min(1, a.fx['perforin']/3))))
                batch.add((ADD, 'glow'), billboard, (p.x, p.y+.1, p.z), .9+.3*pulse, R, U, (255, 60, 60), int(140+100*pulse))
            if a.fx.get('antiheal', 0) > 0:
                # Toxina: bolhas roxas subindo em volta do corpo (sem cura).
                for i in range(6):
                    ph = (self.time*.9+i/6) % 1.0
                    ang = i*math.tau/6+self.time*1.5
                    batch.add((ADD, 'core'), billboard, (p.x+math.cos(ang)*.45, p.y-.8+ph*1.9, p.z+math.sin(ang)*.45),
                              .07, R, U, (196, 120, 245), int(230*(1-ph)))
            if a.shield.value > 0 and a.hero != 'pneumococcus' or a.shield.value > 75:
                batch.add((ADD, 'ring'), billboard, (p.x, p.y+.05, p.z), 1.15, R, U, (140, 210, 255), 110)
            if a.guard > 0 or a.fx.get('frenzy', 0) > 0 or a.fx.get('haste', 0) > 0:
                tint = (120, 255, 200) if a.fx.get('haste', 0) > 0 else (190, 255, 120)
                ground(batch, (p.x, p.y-.9, p.z), .9, tint, 160, 'glow')

    def draw_leap_trail(self, batch, a, R, U):
        """Rastro do Salto de impacto: copias do brilho pelas ultimas posicoes do heroi."""
        trails = self.__dict__.setdefault('trails', {})
        p = a.transform.position
        now = self.time
        pts = [(q, t) for q, t in trails.get(a.slot, []) if now-t < .22 and math.dist(q, p.to_tuple) < 8]
        pts.append((p.to_tuple, now))
        trails[a.slot] = pts[-14:]
        cam = self.camera.global_transform.position.to_tuple
        for (q0, t0), (q1, _) in zip(pts, pts[1:]):
            k = 1-(now-t0)/.22
            batch.add((ADD, 'beam'), ribbon, q0, q1, .9*k, cam, LEAP_TINT, int(120*k))
        batch.add((ADD, 'glow'), billboard, (p.x, p.y+.1, p.z), 1.0, R, U, LEAP_TINT, 110)

    # -- torretas e clones ---------------------------------------------------------------
    def draw_minions(self, me):
        for m in self.arena.minions.values():
            x, y, z = m['pos']
            grow = min(1.0, m.get('age', 1)/.3)
            if m['kind'] == 'turret':
                tint = (255, 170, 170, 255) if m.get('hurt', 0) > 0 else None
                pos = Vec3(x, y-(1-grow)*1.2, z)
                model('plasma_turret').draw(pos, m['yaw'], 0, False, 0, 0, m.get('recoil', 0)*.25, tint)
            else:
                k = min(1.0, m.get('life', 1)/.4) if m.get('life', 0) else 1.0
                model('streptococcus').draw(Vec3(x, y, z), m['yaw'], m.get('age', 0)*9, True, 0, 0, 0,
                                            (255, 200, 230, 255) if k > .3 else (255, 255, 255, 120))

    def draw_minion_rings(self, batch, me):
        for m in self.arena.minions.values():
            owner = self.arena.actors.get(m['slot'])
            edge = team_color(owner, me)
            ground(batch, m['pos'], .7, edge, 220, 'ring')
            if m['kind'] == 'turret' and me is not None and owner is me:
                ground(batch, m['pos'], BALANCE['turret_range'], edge, 40, 'ring', angle=self.time*.1)

    # -- granadas --------------------------------------------------------------------------
    def draw_projectiles(self, batch, eye, R, U, me):
        for p in self.arena.projectiles:
            owner = self.arena.actors.get(p['slot'])
            tint = (120, 200, 255) if p['kind'] == 'antibody' else (150, 240, 60)
            pts = p['trail']
            for a, b in zip(pts, pts[1:]):
                batch.add((ADD, 'beam'), ribbon, a, b, .12, eye, tint, 120)
            batch.add((ADD, 'glow'), billboard, p['pos'], .45, R, U, tint, 220)
            batch.add((ADD, 'y' if p['kind'] == 'antibody' else 'core'), billboard, p['pos'], .2, R, U,
                      (255, 255, 255), 255, self.time*8)
            batch.add((ADD, 'ring'), billboard, p['pos'], .32, R, U, team_color(owner, me), 200)

    # -- previas locais (posicionamento, arco, pouso) ------------------------------------
    def draw_previews(self, batch, me, R, U):
        if me is None or not me.alive:
            return
        if me.placing and me.place:
            point, ok, yaw = me.place
            tint = ALLY if ok else ENEMY
            if me.placing == 'turret':
                ground(batch, point, .7, tint, 255, 'ring', angle=self.time)
                ground(batch, point, .65, tint, 90, 'disc', ALPHA)
                ground(batch, point, BALANCE['turret_range'], tint, 70, 'ring', angle=-self.time*.2)
                x, y, z = point
                for i in range(4):
                    ph = (self.time*.8+i/4) % 1
                    batch.add((ADD, 'ring'), billboard, (x, y+ph*1.3, z), .55*(1-ph*.4), FLAT_R, FLAT_U, tint,
                              int(200*(1-ph)))
            else:
                right = (math.cos(yaw), 0.0, math.sin(yaw))
                x, y, z = point
                vertical(batch, (x, y+1.3, z), right, BALANCE['wall_width']/2, 1.3, tint, 120, 'hexrect')
                ground(batch, point, BALANCE['wall_width']/2, tint, 160, 'ring')
        if me.aiming and me.arc:
            pts, landing = me.arc
            for i, p in enumerate(pts[1::2]):
                batch.add((ADD, 'core'), billboard, p, .07, R, U, (190, 255, 120), 220)
            if landing:
                ground(batch, landing, 3.5, (170, 240, 70), 230, 'ring', angle=self.time)
                ground(batch, landing, 3.4, (170, 240, 70), 60, 'disc', ALPHA)
        plan = getattr(me, 'leap_plan', None)
        if plan is not None:
            # Circulo de pouso: o anel interno fecha ate o impacto.
            x, y, z = plan['target']
            point = (x, y-.93, z)
            r = BALANCE['leap_radius']
            k = min(1.0, plan['t']/max(plan['time'], .01))
            ground(batch, point, r, LEAP_TINT, 235, 'ring', angle=self.time*2)
            ground(batch, point, r*.98, LEAP_TINT, 55, 'disc', ALPHA)
            ground(batch, point, r*(1-.85*k)+.15, (255, 220, 190), 200, 'ring', angle=-self.time*3)
