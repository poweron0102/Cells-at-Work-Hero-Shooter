"""Efeitos de disparo: projéteis visuais, clarões, impactos, faíscas, respingos e marcas.

Os acertos continuam instantâneos (hitscan a partir do olho, em ``combat.py``). Aqui só se
desenha o que o jogador vê: um projétil brilhante que sai do cano (da arma em primeira pessoa
ou da mão do personagem) e viaja até o ponto atingido, um rastro que se apaga, o clarão do
cano e o impacto no fim. Cada herói tem um estilo (``STYLES``); habilidades usam ``kind``.

Tudo é desenhado com quads texturizados (texturas geradas uma única vez) em mistura aditiva,
sem escrever profundidade, para que os brilhos não se recortem uns aos outros.
"""
import math
import random
import time

import pyray as rl
import raylib as _r

from EasyCells3D.Components.Camera3D import Renderable3D
from EasyCells3D.Geometry import Vec3

# --------------------------------------------------------------------------------------
# Estilos
# --------------------------------------------------------------------------------------

_BASE = dict(core=(255, 244, 214), glow=(255, 190, 100), speed=240.0, length=3.0, width=.03, glow_w=.14,
             trail=(255, 226, 180), trail_a=60, trail_life=.22, blob=0.0, arc=0.0, flash='star', flash_size=.3,
             impact='spark', life_extra=.05)

STYLES = {
    # Células: projéteis quentes e retos.
    'neutrophil': dict(core=(255, 246, 222), glow=(255, 186, 96), speed=250, length=3.0, width=.028, glow_w=.13),
    'macrophage': dict(core=(255, 236, 196), glow=(255, 150, 70), speed=190, length=1.3, width=.024, glow_w=.1,
                       trail_a=34, trail_life=.16, flash_size=.5),
    'b_cell': dict(core=(236, 248, 255), glow=(80, 160, 255), speed=330, length=7.0, width=.04, glow_w=.22,
                   trail=(150, 205, 255), trail_a=120, trail_life=.4, flash='ring', flash_size=.36,
                   impact='spark_blue'),
    'killer_t': dict(core=(255, 238, 220), glow=(255, 110, 54), speed=290, length=4.5, width=.032, glow_w=.16,
                     trail_a=70, flash_size=.38),
    # Bactérias: glóbulos orgânicos, mais lentos, com leve arco e respingo.
    'pneumococcus': dict(core=(246, 230, 255), glow=(164, 120, 255), speed=95, length=1.0, width=.06, glow_w=.3,
                         trail=(200, 170, 255), trail_a=50, trail_life=.3, blob=.085, arc=.025, flash='spit',
                         flash_size=.34, impact='splat'),
    'staphylococcus': dict(core=(255, 250, 206), glow=(250, 200, 50), speed=90, length=.8, width=.06, glow_w=.28,
                           trail=(255, 226, 120), trail_a=44, trail_life=.3, blob=.075, arc=.03, flash='spit',
                           flash_size=.32, impact='splat'),
    'pseudomonas': dict(core=(232, 255, 196), glow=(130, 236, 50), speed=110, length=1.6, width=.05, glow_w=.26,
                        trail=(170, 250, 110), trail_a=60, trail_life=.35, blob=.07, arc=.02, flash='spit',
                        flash_size=.3, impact='splat'),
    'streptococcus': dict(core=(255, 226, 240), glow=(255, 80, 156), speed=210, length=2.0, width=.026, glow_w=.12,
                          trail=(255, 150, 200), trail_a=40, trail_life=.18, flash='spit', flash_size=.22,
                          impact='splat_small'),
    # Habilidades.
    'mark': dict(core=(232, 252, 255), glow=(60, 200, 255), speed=260, length=5.0, width=.06, glow_w=.34,
                 trail=(120, 220, 255), trail_a=150, trail_life=.6, flash='ring', flash_size=.5, impact='spark_blue'),
    'sticky': dict(core=(255, 248, 196), glow=(240, 180, 40), speed=70, length=1.2, width=.09, glow_w=.4,
                   trail=(250, 210, 90), trail_a=80, trail_life=.45, blob=.14, arc=.05, flash='spit', flash_size=.5,
                   impact='splat_big'),
    'acid': dict(core=(240, 255, 200), glow=(140, 240, 40), speed=60, length=1.4, width=.1, glow_w=.46,
                 trail=(170, 250, 90), trail_a=90, trail_life=.6, blob=.16, arc=.08, flash='spit', flash_size=.55,
                 impact='splat_big'),
    'beam': dict(core=(240, 250, 255), glow=(90, 170, 255), speed=0, length=0, width=.12, glow_w=.9,
                 trail=(140, 200, 255), trail_a=255, trail_life=.6, flash='ring', flash_size=.9,
                 impact='spark_blue'),
}
for _k, _v in STYLES.items():
    STYLES[_k] = {**_BASE, **_v}

SPECIAL_KINDS = ('mark', 'sticky', 'acid', 'beam')


def style_for(kind, hero):
    if kind in SPECIAL_KINDS:
        return STYLES[kind]
    return STYLES.get(hero, STYLES['neutrophil'])


def tracer_life(kind, hero, start, end):
    """Duração do registro do traçado: viagem do projétil + rastro apagando."""
    st = style_for(kind, hero)
    if st['speed'] <= 0:
        return st['trail_life']
    dist = math.dist(start, end)
    return (dist + st['length']) / st['speed'] + max(st['trail_life'], .08) + st['life_extra']


# --------------------------------------------------------------------------------------
# Texturas procedurais
# --------------------------------------------------------------------------------------

_TEX = {}


def _make(name, size_w, size_h, fn):
    data = bytearray(size_w * size_h * 4)
    for j in range(size_h):
        v = (j + .5) / size_h * 2 - 1
        for i in range(size_w):
            u = (i + .5) / size_w * 2 - 1
            a = max(0.0, min(1.0, fn(u, v)))
            k = (j * size_w + i) * 4
            data[k:k + 4] = bytes((255, 255, 255, int(a * 255)))
    buf = rl.ffi.new('unsigned char[]', bytes(data))
    img = rl.Image(buf, size_w, size_h, 1, rl.PixelFormat.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8)
    tex = rl.load_texture_from_image(img)
    rl.set_texture_filter(tex, rl.TextureFilter.TEXTURE_FILTER_BILINEAR)
    rl.set_texture_wrap(tex, rl.TextureWrap.TEXTURE_WRAP_CLAMP)
    _TEX[name] = tex


def _glow(u, v):
    r = math.hypot(u, v)
    return (max(0.0, 1 - r) ** 2.2)


def _core(u, v):
    r = math.hypot(u, v)
    return max(0.0, 1 - r * 1.15) ** .8


def _streak(u, v):
    # u: -1 cauda -> +1 cabeça; v: transversal.
    along = ((u + 1) / 2) ** 1.6
    head = 1.0 if u < .85 else max(0.0, 1 - (u - .85) / .15)
    return along * head * math.exp(-(v * 2.6) ** 2)


def _beam(u, v):
    return math.exp(-(v * 2.4) ** 2) * min(1.0, (1 - abs(u)) * 8)


def _star(u, v):
    r = math.hypot(u, v)
    core = max(0.0, 1 - r * 1.6) ** 1.5
    spike = max(math.exp(-abs(v) * 30) * max(0.0, 1 - abs(u)) ** 1.5,
                math.exp(-abs(u) * 30) * max(0.0, 1 - abs(v)) ** 1.5)
    d1, d2 = (u + v) * .7071, (u - v) * .7071
    diag = .55 * max(math.exp(-abs(d1) * 34) * max(0.0, 1 - abs(d2) * 1.5) ** 2,
                     math.exp(-abs(d2) * 34) * max(0.0, 1 - abs(d1) * 1.5) ** 2)
    return core + spike + diag + .25 * _glow(u, v)


def _ring(u, v):
    r = math.hypot(u, v)
    return math.exp(-((r - .62) * 9) ** 2) + max(0.0, 1 - r * 2.2) ** 1.4


def _splat(u, v):
    r = math.hypot(u, v)
    a = math.atan2(v, u)
    edge = .52 + .13 * math.sin(a * 5 + .7) + .07 * math.sin(a * 11 + 2.1) + .05 * math.sin(a * 3)
    body = 1.0 if r < edge else max(0.0, 1 - (r - edge) * 14)
    drops = 0.0
    for k, (dx, dy, rr) in enumerate(((.78, .1, .07), (-.55, .62, .06), (-.2, -.84, .08), (.5, -.62, .05),
                                       (-.82, -.25, .045))):
        d = math.hypot(u - dx, v - dy)
        drops = max(drops, 1.0 if d < rr else max(0.0, 1 - (d - rr) * 30))
    shade = .82 + .18 * (1 - min(1.0, r / max(edge, .01)))
    return max(body, drops) * shade


def _hole(u, v):
    r = math.hypot(u, v)
    scorch = max(0.0, 1 - r) ** 1.3 * .7
    core = 1.0 if r < .22 else max(0.0, 1 - (r - .22) * 10)
    return max(scorch, core)


def textures():
    if not _TEX:
        _make('glow', 64, 64, _glow)
        _make('core', 32, 32, _core)
        _make('streak', 64, 16, _streak)
        _make('beam', 16, 16, _beam)
        _make('star', 96, 96, _star)
        _make('ring', 64, 64, _ring)
        _make('splat', 64, 64, _splat)
        _make('hole', 32, 32, _hole)
    return _TEX


def release_textures():
    for tex in _TEX.values():
        rl.unload_texture(tex)
    _TEX.clear()


# --------------------------------------------------------------------------------------
# Primitivas de desenho (rlgl cru, para gastar poucas chamadas Python por quad)
# --------------------------------------------------------------------------------------

_V3, _TC, _C4 = _r.rlVertex3f, _r.rlTexCoord2f, _r.rlColor4ub


def quad(p0, p1, p2, p3, c, a):
    """Quad texturizado (já dentro de rlBegin(RL_QUADS)); uv (0,0)-(1,0)-(1,1)-(0,1)."""
    _C4(c[0], c[1], c[2], a)
    _TC(0, 0)
    _V3(p0[0], p0[1], p0[2])
    _TC(0, 1)
    _V3(p3[0], p3[1], p3[2])
    _TC(1, 1)
    _V3(p2[0], p2[1], p2[2])
    _TC(1, 0)
    _V3(p1[0], p1[1], p1[2])


def billboard(p, size, right, up, c, a, angle=0.0):
    ca, sa = math.cos(angle) * size, math.sin(angle) * size
    rx, ry, rz = right[0] * ca + up[0] * sa, right[1] * ca + up[1] * sa, right[2] * ca + up[2] * sa
    ux, uy, uz = up[0] * ca - right[0] * sa, up[1] * ca - right[1] * sa, up[2] * ca - right[2] * sa
    x, y, z = p
    quad((x - rx - ux, y - ry - uy, z - rz - uz), (x + rx - ux, y + ry - uy, z + rz - uz),
         (x + rx + ux, y + ry + uy, z + rz + uz), (x - rx + ux, y - ry + uy, z - rz + uz), c, a)


MIN_ANGLE = .0024  # largura mínima (rad) para o projétil continuar visível a distância


def ribbon(a, b, width, eye, c, alpha, min_angle=0.0):
    """Faixa voltada para a câmera de a (u=0) até b (u=1). ``min_angle`` garante uma largura
    mínima na tela (a largura cresce com a distância até a câmera)."""
    dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    mx, my, mz = (a[0] + b[0]) * .5 - eye[0], (a[1] + b[1]) * .5 - eye[1], (a[2] + b[2]) * .5 - eye[2]
    sx, sy, sz = dy * mz - dz * my, dz * mx - dx * mz, dx * my - dy * mx
    n = math.sqrt(sx * sx + sy * sy + sz * sz)
    if n < 1e-9:
        return
    if min_angle:
        width = max(width, math.sqrt(mx * mx + my * my + mz * mz) * min_angle)
    k = width * .5 / n
    sx, sy, sz = sx * k, sy * k, sz * k
    quad((a[0] - sx, a[1] - sy, a[2] - sz), (b[0] - sx, b[1] - sy, b[2] - sz),
         (b[0] + sx, b[1] + sy, b[2] + sz), (a[0] + sx, a[1] + sy, a[2] + sz), c, alpha)


class Batch:
    """Agrupa quads por textura/mistura e envia em poucos draw calls."""

    def __init__(self):
        self.items = {}

    def add(self, key, fn, *args):
        self.items.setdefault(key, []).append((fn, args))

    def flush(self):
        tex = textures()
        for (blend, name), calls in self.items.items():
            rl.begin_blend_mode(blend)
            rl.rl_set_texture(tex[name].id)
            rl.rl_begin(rl.RL_QUADS)
            for fn, args in calls:
                fn(*args)
            rl.rl_end()
            rl.rl_set_texture(0)
            rl.end_blend_mode()
        self.items.clear()


ADD = rl.BlendMode.BLEND_ADDITIVE
ALPHA = rl.BlendMode.BLEND_ALPHA


def lerp3(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def mix(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


# --------------------------------------------------------------------------------------
# Renderizador
# --------------------------------------------------------------------------------------

class ShotEffects(Renderable3D):
    """Projéteis, rastros, clarões de terceira pessoa, impactos, partículas e marcas."""

    render_order = 50

    MAX_DECALS = 90
    MAX_PARTICLES = 500

    def __init__(self, arena):
        self.arena = arena
        self.particles = []
        self.decals = []
        self.flashes = []
        self.rng = random.Random(7)
        self.last = time.perf_counter()

    # -- origem visual -------------------------------------------------------------------
    def visual_start(self, shot):
        """Do cano: viewmodel para o jogador local, mão do personagem para os outros."""
        a = shot['a']
        actor = self.arena.actors.get(shot.get('slot'))
        if actor is None:
            return a
        session = self.game.session
        cam = self.camera.transform if self.camera else None
        if actor.slot == session.local_slot and cam is not None:
            from .weapons import view_to_world
            # Viewmodel visível: sai do cano; com zoom (sem viewmodel), logo abaixo da mira.
            return view_to_world(actor.vm_muzzle or (-.04, -.09, .6), self.camera)
        muzzle = getattr(actor, 'tp_muzzle', None)
        if muzzle is not None:
            return muzzle
        return a

    def first_seen(self, shot, eye):
        shot['seen'] = True
        actor = self.arena.actors.get(shot.get('slot'))
        hero = actor.hero if actor is not None else None
        shot['style'] = st = style_for(shot.get('kind', 'shot'), hero)
        start = self.visual_start(shot)
        shot['va'] = start
        shot['age'] = 0.0
        b = shot['b']
        shot['dist'] = math.dist(start, b)
        shot['done'] = False
        local = actor is not None and actor.slot == self.game.session.local_slot
        if not local:  # o jogador local tem o clarão do viewmodel
            d = Vec3(b[0] - start[0], b[1] - start[1], b[2] - start[2])
            n = d.magnitude() or 1
            self.flashes.append(dict(pos=start, dir=(d.x / n, d.y / n, d.z / n), st=st, age=0.0,
                                     life=.06 if st['flash'] != 'spit' else .09,
                                     angle=self.rng.uniform(0, math.tau), size=st['flash_size']))

    # -- impactos ------------------------------------------------------------------------
    def impact(self, shot):
        st = shot['style']
        kind = shot.get('impact')
        if not kind:
            return
        b = shot['b']
        a = shot['va']
        d = Vec3(b[0] - a[0], b[1] - a[1], b[2] - a[2])
        n = d.magnitude() or 1
        d = d * (1 / n)
        normal = Vec3(-d.x, -d.y, -d.z)
        if kind == 'world':
            hit = self.game.physics_world.raycast(Vec3(*b) - d * .25, d, .6, 1 | 8)
            if hit is not None and hit.normal is not None:
                normal = hit.normal.normalize()
        style = st['impact']
        rng = self.rng
        organic = style.startswith('splat')
        big = style == 'splat_big'
        actor_hit = kind == 'actor'
        base = (b[0] + normal.x * .02, b[1] + normal.y * .02, b[2] + normal.z * .02)
        # Clarão e lufada.
        self.particles.append(dict(kind='flash', pos=base, vel=(0, 0, 0), age=0, life=.07 if not organic else .12,
                                   size=(.35 if not organic else .5) * (1.6 if big else 1) * (1.3 if actor_hit else 1),
                                   color=st['core'] if not organic else st['glow'], g=0))
        self.particles.append(dict(kind='puff', pos=base, vel=(normal.x * .6, normal.y * .6 + .3, normal.z * .6),
                                   age=0, life=.35 if not organic else .5, size=.18 * (2 if big else 1),
                                   color=st['glow'] if organic else (210, 205, 195), g=0))
        if organic:
            count = 14 if big else (5 if style == 'splat_small' else 9)
            for _ in range(count):
                v = self._spray(normal, rng, 1.2, 4.5 if big else 3.2)
                self.particles.append(dict(kind='drop', pos=base, vel=v, age=0, life=rng.uniform(.35, .7),
                                           size=rng.uniform(.03, .065) * (1.5 if big else 1), color=st['glow'],
                                           core=st['core'], g=9.0))
        else:
            count = 10 if actor_hit else 8
            spark_col = (150, 210, 255) if style == 'spark_blue' else (255, 214, 140)
            for _ in range(count):
                v = self._spray(normal, rng, 2.0, 7.5)
                self.particles.append(dict(kind='spark', pos=base, vel=v, age=0, life=rng.uniform(.12, .32),
                                           size=rng.uniform(.012, .022), color=spark_col, g=9.8))
        if kind == 'world':
            size = (.42 if big else .22) if organic else .07
            self.decals.append(dict(pos=(b[0] + normal.x * .012, b[1] + normal.y * .012, b[2] + normal.z * .012),
                                    normal=(normal.x, normal.y, normal.z), size=size * rng.uniform(.85, 1.2),
                                    angle=rng.uniform(0, math.tau), age=0, life=9.0 if organic else 7.0,
                                    tex='splat' if organic else 'hole',
                                    color=mix(st['glow'], (60, 60, 40), .25) if organic else (26, 24, 24),
                                    alpha=210 if organic else 200))
            if len(self.decals) > self.MAX_DECALS:
                del self.decals[:len(self.decals) - self.MAX_DECALS]
        if len(self.particles) > self.MAX_PARTICLES:
            del self.particles[:len(self.particles) - self.MAX_PARTICLES]

    @staticmethod
    def _spray(normal, rng, lo, hi):
        while True:
            r = Vec3(rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))
            if .05 < r.magnitude() <= 1:
                break
        r = r.normalize()
        v = (normal * 1.1 + r).normalize() * rng.uniform(lo, hi)
        return (v.x, v.y + .8, v.z)

    # -- loop de desenho -----------------------------------------------------------------
    def render(self):
        now = time.perf_counter()
        dt = min(.05, max(0.0, now - self.last))
        self.last = now
        cam = self.camera
        if cam is None:
            return
        t = cam.global_transform
        eye = t.position.to_tuple
        fwd, up = t.forward, t.up
        right = fwd.cross(up).normalize()
        R, U = right.to_tuple, up.to_tuple
        textures()
        batch = Batch()
        for shot in list(self.arena.tracers):
            if not shot.get('seen'):
                self.first_seen(shot, eye)
            else:
                shot['age'] += dt
            self.draw_shot(shot, batch, eye, R, U)
        self.update_flashes(dt, batch, R, U)
        self.update_particles(dt, batch, eye, R, U)
        self.update_decals(dt, batch)
        rl.rl_draw_render_batch_active()
        rl.rl_disable_depth_mask()
        rl.rl_disable_backface_culling()
        batch.flush()
        rl.rl_enable_backface_culling()
        rl.rl_enable_depth_mask()

    def draw_shot(self, shot, batch, eye, R, U):
        st, age = shot['style'], shot['age']
        a, b, dist = shot['va'], shot['b'], shot['dist']
        if st['speed'] <= 0:
            self.draw_beam(shot, batch, eye, R, U)
            return
        travel = st['speed'] * age
        head_d = min(dist, travel)
        tail_d = min(dist, max(0.0, travel - st['length']))
        if dist <= 1e-6:
            return
        if travel >= dist and not shot['done']:
            shot['done'] = True
            self.impact(shot)
        arc = st['arc'] * dist

        def at(d):
            k = d / dist
            p = lerp3(a, b, k)
            if arc:
                return (p[0], p[1] + arc * 4 * k * (1 - k), p[2])
            return p

        # Rastro tênue do cano até a cabeça, apagando com o tempo.
        trail_k = max(0.0, 1 - age / st['trail_life'])
        if trail_k > 0 and head_d > .05:
            alpha = int(st['trail_a'] * trail_k ** 1.5)
            if alpha > 2:
                segs = 6 if arc else 1
                prev = at(0)
                for i in range(1, segs + 1):
                    cur = at(head_d * i / segs)
                    batch.add((ADD, 'beam'), ribbon, prev, cur, st['width'] * (1.4 + 2.5 * (1 - trail_k)), eye,
                              st['trail'], alpha, MIN_ANGLE * .8)
                    prev = cur
        if tail_d >= dist:
            return
        h, tl = at(head_d), at(tail_d)
        batch.add((ADD, 'streak'), ribbon, tl, h, st['glow_w'], eye, st['glow'], 170, MIN_ANGLE * 4)
        batch.add((ADD, 'streak'), ribbon, tl, h, st['width'], eye, st['core'], 255, MIN_ANGLE)
        if st['blob']:
            batch.add((ADD, 'glow'), billboard, h, st['blob'] * 2.6, R, U, st['glow'], 200)
            batch.add((ADD, 'core'), billboard, h, st['blob'], R, U, st['core'], 255)
        elif head_d < dist:
            batch.add((ADD, 'glow'), billboard, h, st['glow_w'] * .9, R, U, st['glow'], 120)

    def draw_beam(self, shot, batch, eye, R, U):
        st, age = shot['style'], shot['age']
        a, b = shot['va'], shot['b']
        if not shot['done']:
            shot['done'] = True
            self.impact(shot)
        k = max(0.0, 1 - age / st['trail_life'])
        if k <= 0:
            return
        pulse = .85 + .15 * math.sin(age * 60)
        w = st['width'] * (.6 + .4 * k) * pulse
        batch.add((ADD, 'beam'), ribbon, a, b, st['glow_w'] * (1.3 - .3 * k), eye, st['glow'], int(200 * k))
        batch.add((ADD, 'beam'), ribbon, a, b, w * 2.2, eye, st['trail'], int(220 * k))
        batch.add((ADD, 'beam'), ribbon, a, b, w, eye, st['core'], int(255 * k))
        # Anéis de anticorpos ao longo do feixe.
        dist = math.dist(a, b)
        n = int(dist / 2.5)
        for i in range(n):
            q = ((i + .5) / n + age * .8) % 1.0
            p = lerp3(a, b, q)
            batch.add((ADD, 'ring'), billboard, p, .35 + .1 * math.sin(i + age * 20), R, U, st['glow'], int(160 * k))

    def update_flashes(self, dt, batch, R, U):
        keep = []
        for f in self.flashes:
            f['age'] += dt
            if f['age'] > f['life']:
                continue
            keep.append(f)
            st = f['st']
            k = 1 - f['age'] / f['life']
            size = f['size'] * (.7 + .3 * k)
            tex = {'star': 'star', 'ring': 'ring'}.get(st['flash'], 'glow')
            batch.add((ADD, 'glow'), billboard, f['pos'], size * 1.5, R, U, st['glow'], int(150 * k))
            batch.add((ADD, tex), billboard, f['pos'], size, R, U, st['core'], int(255 * k), f['angle'])
        self.flashes = keep

    def update_particles(self, dt, batch, eye, R, U):
        keep = []
        for p in self.particles:
            p['age'] += dt
            if p['age'] >= p['life']:
                continue
            keep.append(p)
            x, y, z = p['pos']
            vx, vy, vz = p['vel']
            vy -= p['g'] * dt
            if p['kind'] in ('puff',):
                vx, vy, vz = vx * (1 - 3 * dt), vy * (1 - 3 * dt), vz * (1 - 3 * dt)
            p['vel'] = (vx, vy, vz)
            p['pos'] = (x + vx * dt, y + vy * dt, z + vz * dt)
            k = 1 - p['age'] / p['life']
            kind = p['kind']
            if kind == 'spark':
                tail = (p['pos'][0] - vx * .035, p['pos'][1] - vy * .035, p['pos'][2] - vz * .035)
                batch.add((ADD, 'beam'), ribbon, tail, p['pos'], p['size'], eye, p['color'], int(255 * k))
            elif kind == 'drop':
                batch.add((ALPHA, 'core'), billboard, p['pos'], p['size'] * (.6 + .4 * k), R, U, p['color'],
                          int(230 * min(1.0, k * 2)))
                batch.add((ADD, 'core'), billboard, p['pos'], p['size'] * .5, R, U, p['core'], int(120 * k))
            elif kind == 'flash':
                batch.add((ADD, 'star'), billboard, p['pos'], p['size'] * (.6 + .4 * k), R, U, p['color'],
                          int(255 * k))
            else:
                grow = 1 + (1 - k) * 2.2
                batch.add((ALPHA, 'glow'), billboard, p['pos'], p['size'] * grow, R, U, p['color'], int(110 * k * k))
        self.particles = keep

    def update_decals(self, dt, batch):
        keep = []
        for d in self.decals:
            d['age'] += dt
            if d['age'] >= d['life']:
                continue
            keep.append(d)
            fade = min(1.0, (d['life'] - d['age']) / 2.0)
            n = Vec3(*d['normal'])
            helper = Vec3(0, 1, 0) if abs(n.y) < .9 else Vec3(1, 0, 0)
            t1 = helper.cross(n).normalize()
            t2 = n.cross(t1).normalize()
            batch.add((ALPHA, d['tex']), billboard, d['pos'], d['size'], t1.to_tuple, t2.to_tuple, d['color'],
                      int(d['alpha'] * fade), d['angle'])
        self.decals = keep

    def on_destroy(self):
        super().on_destroy()
        release_textures()
