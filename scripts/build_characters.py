"""Gera os dez personagens 3D do jogo no Blender (modo headless) e exporta GLB + JSON.

Uso (a partir da raiz do repositório):

    & 'C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe' --background --factory-startup `
        --python scripts\\build_characters.py -- [--only neutrophil,b_cell] [--no-preview]

Todo personagem é modelado do zero com primitivas procedurais (lathe, tubos varridos,
elipsoides, placas extrudadas) e algumas passagens de modificadores do Blender
(Subdivision/Bevel), aplicados antes da exportação. As cores ficam num atributo de cor
por canto (byte color, sRGB) e cada parte é exportada como um objeto de malha separado,
com um único material, para que o jogo desenhe cada parte com um draw call e anime as
partes girando-as em torno do pivô registrado no JSON.

Espaço dos personagens no Blender: Z para cima, frente em -Y, lado esquerdo do
personagem em +X.  O exportador glTF converte para Y para cima / frente +Z; o lado
esquerdo continua em +X.  Pés em z=0 e origem entre os pés.
"""
import json
import math
import random
import struct
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'Assets' / 'Characters3D'
PREVIEW = ROOT / '.scratch' / 'characters'
TAU = math.tau
CONVENTION = ('glTF/raylib: Y para cima, personagem olha para +Z, pés em y=0 e origem entre os pés. '
              'Sufixo _l = lado esquerdo do personagem = +X; _r = lado direito = -X. '
              '"mesh" = índice em model.meshes do raylib (nós do GLB em ordem, um primitivo por parte). '
              '"pivot" = articulação no espaço do personagem (metros). '
              '"swing": static|arm|leg|weapon|tail|tentacle|head. '
              '"phase" = defasagem (rad) do ciclo; "action" = como a parte reage ao ataque.')


# ---------------------------------------------------------------------------------------
# Geometria básica: cada gerador devolve (verts, faces) em coordenadas locais do Blender.
# ---------------------------------------------------------------------------------------

def V(*a):
    return Vector(a[0]) if len(a) == 1 else Vector(a)


def xform(loc=(0, 0, 0), rot=(0, 0, 0), scale=1.0):
    """Matriz TRS; rot em graus (Euler XYZ)."""
    if isinstance(scale, (int, float)):
        scale = (scale, scale, scale)
    return (Matrix.Translation(V(loc)) @ Euler([math.radians(a) for a in rot], 'XYZ').to_matrix().to_4x4()
            @ Matrix.Diagonal((*scale, 1)))


def _bridge(rings):
    faces = []
    for a, b in zip(rings, rings[1:]):
        if len(a) == 1 and len(b) == 1:
            continue
        if len(a) == 1:
            n = len(b)
            faces += [(a[0], b[(j + 1) % n], b[j]) for j in range(n)]
        elif len(b) == 1:
            n = len(a)
            faces += [(a[j], a[(j + 1) % n], b[0]) for j in range(n)]
        else:
            n = len(a)
            faces += [(a[j], a[(j + 1) % n], b[(j + 1) % n], b[j]) for j in range(n)]
    return faces


def lathe(profile, seg=16, sx=1.0, sy=1.0, rfunc=None, a0=0.0):
    """Superfície de revolução em torno de Z. profile = [(raio, z)] percorrido de baixo para
    cima pelo lado de fora (sentido anti-horário no plano r/z); raio 0 vira polo."""
    verts, rings = [], []
    for i, (r, z) in enumerate(profile):
        if r <= 1e-7:
            rings.append([len(verts)])
            verts.append(V(0, 0, z))
            continue
        ring = []
        for j in range(seg):
            a = a0 + TAU * j / seg
            k = rfunc(i, a) if rfunc else 1.0
            ring.append(len(verts))
            verts.append(V(r * k * math.cos(a) * sx, r * k * math.sin(a) * sy, z))
        rings.append(ring)
    return verts, _bridge(rings)


def ellipsoid(r, seg=14, rings=9, zcut=None):
    """Elipsoide centrado na origem. r = raio ou (rx, ry, rz)."""
    rx, ry, rz = (r, r, r) if isinstance(r, (int, float)) else r
    prof = []
    for i in range(rings + 1):
        phi = -math.pi / 2 + math.pi * i / rings
        prof.append((math.cos(phi) if 0 < i < rings else 0.0, math.sin(phi)))
    v, f = lathe(prof, seg)
    return [V(p.x * rx, p.y * ry, p.z * rz) for p in v], f


def dome(r, h, seg=16, rings=5, flat=0.0):
    """Meia elipsoide (fundo fechado) de raio r e altura h: copas de bonés, cabelos."""
    prof = [(0, 0)]
    for i in range(rings + 1):
        phi = (math.pi / 2) * i / rings
        prof.append((r * math.cos(phi) if i < rings else 0.0, h * math.sin(phi) + flat * 0))
    return lathe(prof, seg)


def tube(pts, radii, seg=12, caps=('round', 'round'), hint=(1, 0, 0), rfunc=None):
    """Tubo varrido ao longo de uma polilinha. radii: float ou (ru, rv) por ponto; 0 = ponta.
    caps: 'round', 'flat' ou None em cada extremidade."""
    pts = [V(p) for p in pts]
    n = len(pts)
    rr = [(r, r) if isinstance(r, (int, float)) else tuple(r) for r in radii]
    tangents = []
    for i in range(n):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == n - 1:
            t = pts[-1] - pts[-2]
        else:
            t = (pts[i + 1] - pts[i]).normalized() + (pts[i] - pts[i - 1]).normalized()
        tangents.append(t.normalized())
    h = V(hint)
    u = h - tangents[0] * h.dot(tangents[0])
    if u.length < 1e-4:
        u = V(0, 1, 0) - tangents[0] * tangents[0].y
    u.normalize()
    frames = []
    for t in tangents:
        u = (u - t * u.dot(t)).normalized()
        frames.append((u.copy(), t.cross(u).normalized()))
    verts, rings = [], []

    def ring(c, ru, rv, uu, vv, i):
        if ru <= 1e-7:
            rings.append([len(verts)])
            verts.append(c.copy())
            return
        idx = []
        for j in range(seg):
            a = TAU * j / seg
            k = rfunc(i, a) if rfunc else 1.0
            idx.append(len(verts))
            verts.append(c + uu * (ru * k * math.cos(a)) + vv * (rv * k * math.sin(a)))
        rings.append(idx)

    def cap(i, sign, kind):
        (ru, rv), (uu, vv), t, c = rr[i], frames[i], tangents[i] * sign, pts[i]
        if kind is None or ru <= 1e-7:
            return []
        if kind == 'flat':
            return [(c, ru * .7, rv * .7), (c, 0, 0)]
        out = []
        for phi in (math.pi / 5, 2 * math.pi / 5):
            out.append((c + t * (min(ru, rv) * math.sin(phi)), ru * math.cos(phi), rv * math.cos(phi)))
        out.append((c + t * min(ru, rv), 0, 0))
        return out

    start = cap(0, -1, caps[0])
    for c, ru, rv in reversed(start):
        ring(c, ru, rv, *frames[0], 0)
    for i in range(n):
        ring(pts[i], *rr[i], *frames[i], i)
    for c, ru, rv in cap(n - 1, 1, caps[1]):
        ring(c, ru, rv, *frames[-1], n - 1)
    return verts, _bridge(rings)


def box(size):
    sx, sy, sz = [s / 2 for s in size]
    v = [V(x * sx, y * sy, z * sz) for z in (-1, 1) for y in (-1, 1) for x in (-1, 1)]
    f = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    return v, f


def slab(outline, depth):
    """Polígono 2D (plano XY local) extrudado em Z, centrado em z=0."""
    pts = [V(x, y, 0) for x, y in outline]
    area = sum(a.x * b.y - b.x * a.y for a, b in zip(pts, pts[1:] + pts[:1]))
    if area < 0:
        pts.reverse()
    n = len(pts)
    verts = [p + V(0, 0, -depth / 2) for p in pts] + [p + V(0, 0, depth / 2) for p in pts]
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return verts, faces


def bezier(p0, p1, p2, p3, steps=12):
    p0, p1, p2, p3 = map(V, (p0, p1, p2, p3))
    out = []
    for i in range(steps + 1):
        t = i / steps
        m = 1 - t
        out.append(p0 * m ** 3 + p1 * 3 * m * m * t + p2 * 3 * m * t * t + p3 * t ** 3)
    return out


def apply_matrix(geo, m):
    v, f = geo
    return [m @ p for p in v], f


def cut(geo, keep):
    """Remove faces cujo centróide não satisfaz keep(c)."""
    v, f = geo
    f = [face for face in f if keep(sum((v[i] for i in face), V(0, 0, 0)) / len(face))]
    used = sorted({i for face in f for i in face})
    remap = {old: new for new, old in enumerate(used)}
    return [v[i] for i in used], [tuple(remap[i] for i in face) for face in f]


def mirror_x(geo):
    v, f = geo
    return [V(-p.x, p.y, p.z) for p in v], [tuple(reversed(face)) for face in f]


def modifiers(geo, mods):
    """Passa a geometria por modificadores reais do Blender e devolve o resultado aplicado.
    mods = [('SUBSURF', {'levels': 1}), ('BEVEL', {...}), ...]."""
    v, f = geo
    me = bpy.data.meshes.new('tmp')
    me.from_pydata([tuple(p) for p in v], [], f)
    ob = bpy.data.objects.new('tmp', me)
    bpy.context.scene.collection.objects.link(ob)
    for kind, opts in mods:
        mod = ob.modifiers.new(kind.lower(), kind)
        for k, val in opts.items():
            setattr(mod, k, val)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    m2 = ev.to_mesh()
    verts = [V(p.co) for p in m2.vertices]
    faces = [tuple(p.vertices) for p in m2.polygons]
    ev.to_mesh_clear()
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    return verts, faces


def subsurf(geo, levels=1):
    return modifiers(geo, [('SUBSURF', {'levels': levels, 'render_levels': levels})])


def orient(geo):
    """Garante normais para fora: volume assinado (em torno do centróide) deve ser positivo."""
    v, f = geo
    if not f:
        return geo
    c = sum(v, V(0, 0, 0)) / len(v)
    vol = 0.0
    for face in f:
        a = v[face[0]] - c
        for i in range(1, len(face) - 1):
            vol += a.dot((v[face[i]] - c).cross(v[face[i + 1]] - c))
    if vol < 0:
        ORIENT_FLIPS[0] += 1
        return v, [tuple(reversed(face)) for face in f]
    return geo


ORIENT_FLIPS = [0]


# ---------------------------------------------------------------------------------------
# Partes (uma malha exportada por parte)
# ---------------------------------------------------------------------------------------

def hexc(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


class Part:
    def __init__(self, name, swing='static', pivot=(0, 0, 0), parent='body', phase=0.0, action=None, amp=None):
        self.name, self.swing, self.pivot, self.parent = name, swing, V(pivot), parent
        self.phase, self.action, self.amp = phase, action, amp
        self.verts, self.faces, self.fcol, self.fsmooth = [], [], [], []

    def add(self, geo, color, at=None, smooth=True, mirror=False):
        """Adiciona geometria; at = matriz (xform) ou posição (x, y, z)."""
        if at is not None:
            m = at if isinstance(at, Matrix) else Matrix.Translation(V(at))
            geo = apply_matrix(geo, m)
        geo = orient(geo)
        geos = [geo, mirror_x(geo)] if mirror else [geo]
        for v, f in geos:
            base = len(self.verts)
            self.verts.extend(v)
            col = hexc(color) if isinstance(color, str) else color
            for face in f:
                self.faces.append(tuple(base + i for i in face))
                self.fcol.append(col)
                self.fsmooth.append(smooth)
        return self

    # atalhos
    def ell(self, c, r, color, seg=10, rings=7, rot=(0, 0, 0), smooth=True, mirror=False):
        return self.add(ellipsoid(r, seg, rings), color, xform(c, rot), smooth, mirror)

    def tube(self, pts, radii, color, seg=12, caps=('round', 'round'), mirror=False, smooth=True, **kw):
        return self.add(tube(pts, radii, seg, caps, **kw), color, None, smooth, mirror)

    def box(self, c, size, color, rot=(0, 0, 0), mirror=False, smooth=False, bevel=0.0):
        geo = box(size)
        if bevel:
            geo = modifiers(geo, [('BEVEL', {'width': bevel, 'segments': 2})])
        return self.add(geo, color, xform(c, rot), smooth, mirror)

    def cone(self, base, tip, r, color, seg=8, mirror=False, smooth=True, flat=1.0, hint=(1, 0, 0)):
        return self.add(tube([base, tip], [(r, r * flat), 0], seg, ('flat', None), hint=hint), color, None,
                        smooth, mirror)

    def ring(self, c, r, thick, color, rot=(0, 0, 0), seg=16, sx=1.0, sy=1.0, h=None, mirror=False):
        """Faixa (anel achatado) em volta de Z local: cintos, punhos, braçadeiras."""
        h = h if h is not None else thick
        prof = [(r, -h / 2), (r + thick, -h / 2 * .7), (r + thick, h / 2 * .7), (r, h / 2)]
        prof = prof + [prof[0]]
        v, f = lathe(prof, seg, sx, sy)
        return self.add((v, f), color, xform(c, rot), True, mirror)


# ---------------------------------------------------------------------------------------
# Peças humanoides reutilizáveis
# ---------------------------------------------------------------------------------------

INK = '#25252b'
WHITE = '#fbfbfb'


def torso(p, rings, color, seg=16):
    """rings = [(z, rx, ry, dy)] de baixo para cima; primeiro e último fecham em polo."""
    pts = [V(0, r[3] if len(r) > 3 else 0, r[0]) for r in rings]
    radii = [(r[1], r[2]) for r in rings]
    p.add(tube(pts, radii, seg, (None, None), hint=(1, 0, 0)), color)


def face(p, c, s, skin, iris, *, hide_r=False, mouth='#b5545a', smile=False, lashes=None, brows=None,
         eye_w=1.0, mask=None, brow_tilt=-6):
    """Cabeça anime: crânio, mandíbula, orelhas, olhos grandes e boca. c = centro do crânio."""
    c = V(c)
    p.add(head_mesh(s), skin, c)
    p.ell(c + V(0.097, 0.012, -0.012) * s, (0.016 * s, 0.024 * s, 0.03 * s), skin, 8, 6, mirror=True)
    for side in (1, -1):
        if hide_r and side < 0:
            continue
        e = c + V(side * 0.041 * eye_w, -0.093, -0.012) * s
        rot = (0, 0, -side * 16)
        p.ell(e, (0.026 * s * eye_w, 0.012 * s, 0.03 * s), WHITE, 10, 6, rot=rot)
        p.ell(e + V(0, -0.006, -0.002) * s, (0.017 * s * eye_w, 0.01 * s, 0.024 * s), iris, 10, 6, rot=rot)
        p.ell(e + V(0, -0.010, -0.002) * s, (0.009 * s, 0.008 * s, 0.014 * s), INK, 8, 5, rot=rot)
        p.ell(e + V(side * -0.006, -0.013, 0.008) * s, (0.005 * s, 0.004 * s, 0.006 * s), WHITE, 6, 4)
        lash = lashes or INK
        p.box(e + V(0, -0.008, 0.03) * s, (0.056 * s * eye_w, 0.012 * s, 0.008 * s), lash, rot=(0, -side * 6, -side * 16))
        if brows:
            p.box(e + V(side * 0.004, -0.006, 0.054) * s, (0.044 * s, 0.01 * s, 0.009 * s), brows,
                  rot=(0, side * brow_tilt, -side * 16))
    if mask:
        # Máscara negra das bactérias: faixa em volta dos olhos.
        p.ell(c + V(0, -0.072, -0.008) * s, (0.098 * s, 0.04 * s, 0.035 * s), mask, 14, 6)
    m = c + V(0, -0.095, -0.083) * s
    if smile:
        arc = [m + V(x, -0.002 * (1 - abs(x) / 0.03), 0.012 * (x / 0.03) ** 2) * s for x in (-0.03, -0.015, 0, 0.015, 0.03)]
        p.tube(arc, [0.004 * s, 0.006 * s, 0.007 * s, 0.006 * s, 0.004 * s], '#7a2830', 6)
        p.box(m + V(0, -0.006, 0.006) * s, (0.03 * s, 0.004 * s, 0.006 * s), WHITE)
    else:
        p.ell(m, (0.014 * s, 0.006 * s, 0.005 * s), mouth, 8, 4)


def head_mesh(s):
    """Crânio + mandíbula numa só malha suave (sem costura de sombreamento no rosto)."""
    v, f = ellipsoid((0.100 * s, 0.104 * s, 0.12 * s), 18, 12)
    out = []
    for q in v:
        t = max(0.0, -q.z / (0.12 * s))
        x = q.x * (1 - 0.36 * t ** 1.5)
        y = q.y * (1 - 0.12 * t) if q.y < 0 else q.y * (1 - 0.3 * t)
        z = q.z * (1.1 if q.z < 0 else 1.0)
        out.append(V(x, y - 0.012 * s * t, z))
    return out, f


def hair_shell(p, c, s, color, front=0.035, back_drop=0.0, r=1.0, seg=18):
    """Cabelo como casca sobre o crânio, aberta na face."""
    c = V(c)
    geo = ellipsoid((0.112 * s * r, 0.116 * s * r, 0.124 * s * r), seg, 11)
    geo = apply_matrix(geo, Matrix.Translation(c + V(0, 0.008, 0.012) * s))
    geo = cut(geo, lambda q: not (q.y < c.y - 0.03 * s and q.z < c.z + front * s)
              and q.z > c.z - (0.07 + back_drop) * s - max(0, q.y - c.y) * 0.8)
    p.add(geo, color)


def spikes(p, c, s, color, items, seg=6):
    """items = [(direção, comprimento, raio, desvio_da_base)]."""
    c = V(c)
    for d, length, r, off in items:
        d = V(d).normalized()
        base = c + V(off) * s + d * 0.09 * s
        p.cone(base, base + d * length * s, r * s, color, seg, flat=.55, hint=(0, 0, 1) if abs(d.z) < .8 else (1, 0, 0))


def bangs(p, c, s, color, xs, drop=0.07, fwd=0.105, length=1.0):
    c = V(c)
    for x, tilt in xs:
        base = c + V(x, -0.07, 0.085) * s
        tip = c + V(x + tilt, -fwd, 0.085 - drop * length) * s
        p.cone(base, tip, 0.032 * s, color, 6, flat=.45, hint=(0, 1, 0))


def ball_cap(p, c, s, crown, brim, tilt=-8, r=0.122, h=0.105, brim_len=0.13, brim_w=0.12, visor_drop=8,
             badge=None, crown_seg=18, sx=1.0, sy=1.04, z_off=0.035, puff=1.0):
    """Boné: copa em domo + aba. c = centro do crânio."""
    c = V(c)
    m = xform(c + V(0, 0.006, z_off) * s, (tilt, 0, 0))
    prof = [(0, -0.012 * s)]
    for i in range(7):
        phi = (math.pi / 2) * i / 6
        prof.append((r * s * puff * math.cos(phi) if i < 6 else 0.0, h * s * math.sin(phi)))
    v, f = lathe(prof, crown_seg, sx, sy)
    p.add(apply_matrix((v, f), m), crown)
    p.add(apply_matrix(lathe([(r * s * sx * .98, -0.014 * s), (r * s * sx * 1.02, -0.004 * s),
                               (r * s * sx * 1.0, 0.012 * s), (r * s * sx * .98, -0.014 * s)], crown_seg, 1, sy / sx),
                       m), crown)
    pts = []
    for i in range(13):
        a = math.pi + math.pi * i / 12
        pts.append((brim_w * s * math.cos(a), -0.02 * s + brim_len * s * math.sin(a) - r * s * sy * .55))
    pts += [(brim_w * s * .9, -r * s * sy * .25), (-brim_w * s * .9, -r * s * sy * .25)]
    pts = pts[:13] + [pts[13]] + [pts[14]]
    geo = slab(pts, 0.012 * s)
    p.add(geo, brim, m @ xform((0, 0, 0.0), (-visor_drop, 0, 0)), smooth=False)
    if badge:
        p.ell(m @ V(0, -r * s * sy * .92, 0.05 * s), (0.022 * s, 0.006 * s, 0.022 * s), badge, 10, 5,
              rot=(-25 + tilt, 0, 0))
    return m


def hand(p, c, s, color, fist=True, side=1):
    c = V(c)
    if fist:
        p.ell(c, (0.034 * s, 0.04 * s, 0.042 * s), color, 10, 7)
        p.ell(c + V(side * 0.026, -0.012, 0.004) * s, (0.013 * s, 0.018 * s, 0.022 * s), color, 6, 5)
    else:
        p.ell(c, (0.022 * s, 0.042 * s, 0.05 * s), color, 10, 7, rot=(0, 0, 0))
        p.ell(c + V(0, -0.008, -0.05) * s, (0.02 * s, 0.035 * s, 0.03 * s), color, 8, 5)
        p.ell(c + V(0, -0.032, -0.006) * s, (0.012 * s, 0.014 * s, 0.024 * s), color, 6, 4)


def limb(p, pts, radii, color, seg=12):
    p.tube(pts, radii, color, seg, ('round', 'round'))


def sneaker(p, ankle, s, upper, sole, accent=None, toe=None, length=0.27, width=0.105, height=0.1, boot=0.0,
            boot_col=None, laces=None):
    a = V(ankle)
    x, y = a.x, a.y
    cy = y - 0.04 * s
    p.ell(V(x, cy, height * .55 * s), (width * .5 * s, length * .5 * s, height * .55 * s), upper, 14, 8)
    p.ell(V(x, cy - length * .22 * s, height * .42 * s), (width * .5 * s, length * .3 * s, height * .42 * s),
          toe or upper, 12, 7)
    p.box(V(x, cy, 0.014 * s), (width * 1.04 * s, length * 1.02 * s, 0.028 * s), sole, bevel=0.008 * s)
    if accent:
        p.box(V(x, cy + 0.02 * s, height * .55 * s), (width * 1.02 * s, 0.05 * s, height * .5 * s), accent)
    if boot:
        p.tube([V(x, y, 0.06 * s), V(x, y + 0.004, boot * s)], [0.058 * s, 0.062 * s], boot_col or upper, 14,
               ('flat', 'flat'))
    if laces:
        for i in range(4 if boot else 2):
            z = (0.11 + i * 0.045) * s
            p.box(V(x, y - 0.058 * s, z), (0.042 * s, 0.008 * s, 0.007 * s), laces)


# ---------------------------------------------------------------------------------------
# Humanoide base
# ---------------------------------------------------------------------------------------

class Rig:
    """Marcos anatômicos de um adulto (escala s), já com as larguras do personagem."""

    def __init__(self, s=1.0, shoulder=0.185, hip=0.092, female=False, hs=1.15):
        self.s = s
        self.hsz = s * hs  # escala da cabeça (cabeças maiores leem melhor à distância)
        self.ankle, self.knee, self.hip_z = 0.085 * s, 0.48 * s, 0.89 * s
        self.waist, self.chest, self.sh_z = 1.04 * s, 1.25 * s, 1.405 * s
        self.neck, self.head = 1.45 * s, 1.625 * s
        self.sh_x, self.hip_x = shoulder * s, hip * s
        self.female = female

    @property
    def head_c(self):
        # Queixo fica na mesma altura; a cabeça cresce para cima.
        return V(0, 0.004 * self.s, self.head + 0.13 * (self.hsz - self.s))


def human_parts(rig, arm_amp=0.55, leg_amp=0.5, weapon_arm_amp=None):
    s = rig.s
    body = Part('body')
    arm_l = Part('arm_l', 'arm', (rig.sh_x, 0, rig.sh_z), phase=math.pi, amp=arm_amp)
    arm_r = Part('arm_r', 'arm', (-rig.sh_x, 0, rig.sh_z), phase=0.0, action='slash',
                 amp=weapon_arm_amp if weapon_arm_amp is not None else arm_amp)
    leg_l = Part('leg_l', 'leg', (rig.hip_x, 0, rig.hip_z), phase=0.0, amp=leg_amp)
    leg_r = Part('leg_r', 'leg', (-rig.hip_x, 0, rig.hip_z), phase=math.pi, amp=leg_amp)
    return body, arm_l, arm_r, leg_l, leg_r


def male_torso(p, rig, color, wide=1.0, chest=1.0):
    s, w = rig.s, wide
    torso(p, [(0.80 * s, 0.0, 0.0), (0.82 * s, 0.10 * s * w, 0.07 * s), (0.87 * s, 0.150 * s * w, 0.095 * s),
              (0.94 * s, 0.158 * s * w, 0.10 * s), (1.04 * s, 0.145 * s * w, 0.094 * s),
              (1.16 * s, 0.156 * s * w, 0.10 * s * chest), (1.27 * s, 0.178 * s * w, 0.108 * s * chest, -0.006 * s),
              (1.36 * s, 0.19 * s * w, 0.102 * s * chest, -0.002 * s), (1.41 * s, 0.192 * s * w, 0.092 * s),
              (1.44 * s, 0.155 * s * w, 0.08 * s), (1.465 * s, 0.075 * s * w, 0.06 * s), (1.475 * s, 0.0, 0.0)],
           color, 18)


def female_torso(p, rig, color, bust=1.0):
    s = rig.s
    torso(p, [(0.80 * s, 0.0, 0.0), (0.82 * s, 0.10 * s, 0.07 * s), (0.87 * s, 0.150 * s, 0.098 * s),
              (0.95 * s, 0.152 * s, 0.10 * s), (1.05 * s, 0.122 * s, 0.084 * s), (1.15 * s, 0.13 * s, 0.09 * s),
              (1.24 * s, 0.148 * s, 0.10 * s * bust, -0.012 * s), (1.32 * s, 0.155 * s, 0.098 * s * bust, -0.01 * s),
              (1.385 * s, 0.165 * s, 0.085 * s), (1.42 * s, 0.13 * s, 0.07 * s), (1.445 * s, 0.065 * s, 0.05 * s),
              (1.452 * s, 0.0, 0.0)], color, 18)
    if bust > 0:
        p.ell(V(0.055 * s, -0.06 * s, 1.27 * s), (0.06 * s, 0.05 * s * bust, 0.055 * s), color, 12, 7, mirror=True)


def neck(p, rig, color, r=0.042):
    s = rig.s
    p.tube([V(0, 0.006 * s, 1.40 * s), V(0, 0.0, rig.head - 0.08 * s)], [r * s, r * s * .95], color, 12)


def std_arm(part, rig, side, sleeve, skin_or_glove, *, pose='hang', sleeve_end=1.0, cuff=None, upper=0.052,
            fore=0.043, muscle=1.0, forearm_col=None, fist=False, hold=None):
    """Braço completo em uma parte. pose: 'hang' (relaxado) ou 'hold' (antebraço à frente).
    Retorna a posição da mão."""
    s = rig.s
    sh = V(side * rig.sh_x, 0.0, rig.sh_z)
    if pose == 'hold':
        el = V(side * (rig.sh_x + 0.045 * s), 0.035 * s, rig.sh_z - 0.27 * s)
        wr = V(side * (rig.sh_x + 0.055 * s), -0.16 * s, rig.sh_z - 0.40 * s)
    else:
        el = V(side * (rig.sh_x + 0.05 * s), 0.025 * s, rig.sh_z - 0.28 * s)
        wr = V(side * (rig.sh_x + 0.07 * s), -0.035 * s, rig.sh_z - 0.53 * s)
    if hold is not None:
        wr = V(hold)
    u, f = upper * s * muscle, fore * s * muscle
    part.ell(sh + V(0, 0, -0.012 * s), (u * 1.12, u * 1.1, u * 1.1), sleeve, 12, 8)
    part.tube([sh, el], [u, u * .9], sleeve, 12)
    fcol = forearm_col or sleeve
    if sleeve_end < 1.0:
        mid = el.lerp(wr, sleeve_end)
        part.tube([el, wr], [f * 1.02, f * .82], fcol, 12)
        part.tube([el, mid], [u * .95, f * 1.15], sleeve, 12, ('round', 'flat'))
        if cuff:
            d = (wr - el).normalized()
            part.add(tube([mid - d * 0.02 * s, mid + d * 0.012 * s], [f * 1.25, f * 1.22], 12, ('flat', 'flat')),
                     cuff)
    else:
        part.tube([el, wr], [u * .92, f * .9], sleeve, 12)
        if cuff:
            d = (wr - el).normalized()
            part.add(tube([wr - d * 0.05 * s, wr - d * 0.005 * s], [f * 1.2, f * 1.15], 12, ('flat', 'flat')), cuff)
    d = (wr - el).normalized()
    hc = wr + d * 0.045 * s
    hand(part, hc, s, skin_or_glove, fist=fist or pose == 'hold', side=side)
    return hc


def std_leg(part, rig, side, pants, *, shorts=None, shorts_len=0.25, cuff=None, skin=None, knee_dy=-0.01,
            thigh=0.078, calf=0.056, ankle_r=0.042, upper_len=None):
    s = rig.s
    hip = V(side * rig.hip_x, 0, rig.hip_z + 0.03 * s)
    kn = V(side * (rig.hip_x + 0.006 * s), knee_dy * s, rig.knee)
    an = V(side * (rig.hip_x + 0.008 * s), 0.0, rig.ankle + 0.03 * s)
    if shorts:
        # Coxa nua (ou meia-calça) com a barra do short presa à perna.
        part.tube([hip, kn, an], [thigh * s, calf * .95 * s, ankle_r * s], skin, 12)
        mid = hip.lerp(kn, shorts_len / 0.4)
        part.tube([hip + V(0, 0, 0.02 * s), mid], [thigh * 1.18 * s, thigh * 1.2 * s], shorts, 14, ('round', 'flat'))
        if cuff:
            d = (mid - hip).normalized()
            part.add(tube([mid - d * 0.04 * s, mid + d * 0.005 * s], [thigh * 1.3 * s, thigh * 1.3 * s], 14,
                          ('flat', 'flat')), cuff)
    else:
        part.tube([hip, kn], [thigh * s, calf * 1.05 * s], pants, 12)
        part.tube([kn, an], [calf * 1.05 * s, ankle_r * 1.2 * s], pants, 12)
        if cuff:
            part.add(tube([an + V(0, 0, 0.04 * s), an + V(0, 0, 0.1 * s)], [ankle_r * 1.65 * s, ankle_r * 1.7 * s],
                          14, ('flat', 'flat')), cuff)
    return hip, kn, an


# ---------------------------------------------------------------------------------------
# Personagens
# ---------------------------------------------------------------------------------------

def build_neutrophil():
    rig = Rig(1.0)
    s = rig.s
    W, W2, SH, SK, HAIR = '#eef2f4', '#dfe6ea', '#b9c4cb', '#f2e3d6', '#f6f7f8'
    body, arm_l, arm_r, leg_l, leg_r = human_parts(rig, weapon_arm_amp=0.3)
    male_torso(body, rig, W)
    neck(body, rig, SK)
    # Jaqueta: barra solta, placa do zíper, bolsos, cinto, gola.
    body.ring(V(0, 0, 0.99 * s), 0.146 * s, 0.012 * s, SH, h=0.035 * s, sx=1, sy=.66, seg=18)
    body.box(V(0, -0.104 * s, 0.997 * s), (0.05 * s, 0.012 * s, 0.035 * s), '#8d979e')
    body.box(V(0, -0.106 * s, 1.2 * s), (0.016 * s, 0.01 * s, 0.4 * s), SH)
    body.box(V(0.075 * s, -0.112 * s, 1.31 * s), (0.08 * s, 0.012 * s, 0.075 * s), W2, mirror=True)
    body.box(V(0.075 * s, -0.118 * s, 1.345 * s), (0.084 * s, 0.014 * s, 0.022 * s), SH, mirror=True)
    for side in (1, -1):
        body.add(slab([(0, 0), (0.06 * s, 0.0), (0.035 * s, -0.07 * s)], 0.012 * s), W2,
                 xform(V(side * 0.035 * s, -0.07 * s, 1.47 * s), (75, 0, side * 25)), smooth=False)
    body.ring(V(0, 0.0, 1.445 * s), 0.05 * s, 0.018 * s, W2, h=0.05 * s, sx=1, sy=.95)
    # Bainha da faca no quadril direito.
    body.box(V(-0.15 * s, 0.03 * s, 0.86 * s), (0.03 * s, 0.05 * s, 0.22 * s), '#c6ced3', rot=(0, -8, 0))
    hc = rig.head_c
    hs = rig.hsz
    face(body, hc, hs, SK, '#2b2b32', hide_r=True, brows='#c9cfd3', brow_tilt=8)
    hair_shell(body, hc, hs, HAIR)
    bangs(body, hc, hs, HAIR, [(-0.06, -0.01), (-0.035, 0.0), (-0.01, 0.01), (0.02, 0.012), (0.05, 0.02)],
          drop=0.09)
    # Franja longa cobrindo o olho direito.
    body.add(slab([(0, 0), (0.07 * hs, 0.01 * hs), (0.06 * hs, -0.11 * hs), (0.02 * hs, -0.14 * hs), (-0.005 * hs, -0.08 * hs)],
                  0.016 * hs), HAIR, xform(hc + V(-0.075, -0.098, 0.06) * hs, (90, 0, -12)), smooth=False)
    spikes(body, hc, hs, HAIR, [((0.9, 0.3, -0.3), 0.05, 0.03, (0, 0.01, 0)), ((-0.9, 0.3, -0.3), 0.05, 0.03, (0, 0.01, 0)),
                               ((0.4, 0.9, -0.4), 0.06, 0.035, (0, 0, 0)), ((-0.4, 0.9, -0.4), 0.06, 0.035, (0, 0, 0)),
                               ((0, 1, -0.5), 0.06, 0.04, (0, 0, 0))])
    m = ball_cap(body, hc, hs, '#f1f4f5', '#e4e9ec', badge=None)
    # Letreiro do boné (白血球) como placa clara com três blocos de "texto".
    for i in range(3):
        body.box(m @ V((i - 1) * 0.034 * hs, -0.124 * hs, 0.05 * hs), (0.026 * hs, 0.006 * hs, 0.024 * hs), '#4b5258',
                 rot=(-28, 0, 0))
    # Receptor: haste + alvo.
    top = m @ V(0, 0.01 * hs, 0.1 * hs)
    body.tube([top, top + V(0, 0, 0.12 * hs)], [0.006 * hs, 0.006 * hs], '#8e989e', 6)
    tgt = top + V(0, 0, 0.155 * hs)
    body.add(tube([tgt + V(0, 0.006 * hs, 0), tgt - V(0, 0.006 * hs, 0)], [0.036 * hs, 0.036 * hs], 18, ('flat', 'flat')),
             WHITE)
    body.add(tube([tgt + V(0, 0.0, 0), tgt - V(0, 0.009 * hs, 0)], [0.026 * hs, 0.026 * hs], 18, ('flat', 'flat')), INK)
    body.add(tube([tgt - V(0, 0.002 * hs, 0), tgt - V(0, 0.011 * hs, 0)], [0.018 * hs, 0.018 * hs], 18, ('flat', 'flat')),
             WHITE)
    body.add(tube([tgt - V(0, 0.004 * hs, 0), tgt - V(0, 0.013 * hs, 0)], [0.008 * hs, 0.008 * hs], 12, ('flat', 'flat')),
             INK)
    # Braços: luvas brancas, emblema no braço esquerdo.
    hcl = std_arm(arm_l, rig, 1, W, '#fafcfc', cuff=W2, fist=True)
    arm_l.box(V(rig.sh_x + 0.058 * s, 0.0, rig.sh_z - 0.12 * s), (0.012 * s, 0.05 * s, 0.065 * s), SH, rot=(0, -8, 0))
    hcr = std_arm(arm_r, rig, -1, W, '#fafcfc', pose='hold', cuff=W2)
    arm_r.action, arm_l.action = 'recoil', 'slash'
    weapon = Part('weapon', 'weapon', arm_l.pivot, parent='arm_l', action='slash')
    knife(weapon, hcl, s, blade='#d6dee4', grip='#3a3f46', length=0.2, fwd=(0, -1, -0.45))
    for side, leg in ((1, leg_l), (-1, leg_r)):
        hip, kn, an = std_leg(leg, rig, side, W)
        for z, dz in ((0.74, 0.0), (0.64, 0.0)):
            q = hip.lerp(kn, (hip.z - z * s) / (hip.z - kn.z))
            leg.add(tube([q - V(0, 0, 0.012 * s), q + V(0, 0, 0.012 * s)], [0.087 * s, 0.087 * s], 14,
                         ('flat', 'flat')), SH)
        sneaker(leg, an, s, '#e3e8eb', '#9aa4aa', boot=0.3, boot_col='#e3e8eb', laces='#7f8a91', height=0.11)
    return dict(height=1.88, parts=[body, arm_l, arm_r, leg_l, leg_r, weapon], mount=dict(part='arm_r', pos=hcr))


def knife(p, hand_c, s, blade, grip, length=0.2, width=0.034, fwd=(0, -1, 0.25)):
    d = V(fwd).normalized()
    hc = V(hand_c)
    g0, g1 = hc + d * -0.06 * s, hc + d * 0.055 * s
    p.tube([g0, g1], [0.016 * s, 0.017 * s], grip, 8)
    p.add(tube([g1, g1 + d * 0.012 * s], [(0.04 * s, 0.012 * s), (0.04 * s, 0.012 * s)], 10, ('flat', 'flat'),
               hint=(1, 0, 0)), '#59616a')
    # Lâmina de adaga: placa losangular no plano XY local, apontada para +Y local.
    L, w = length * s, width * s
    outline = [(-w / 2, 0), (w / 2, 0), (w * .55, L * .55), (0, L), (-w * .55, L * .55)]
    geo = slab(outline, 0.008 * s)
    # Alinha +Y local com d, plano da lâmina vertical.
    z_axis = V(1, 0, 0)
    y_axis = d
    x_axis = y_axis.cross(z_axis).normalized()
    m = Matrix((x_axis, y_axis, z_axis)).transposed().to_4x4()
    m.translation = g1 + d * 0.012 * s
    p.add(geo, blade, m, smooth=False)
    p.add(tube([g1 + d * 0.012 * s, g1 + d * (L * .9)], [0.003 * s, 0.002 * s], 6), '#9aa3ab')


def build_killer_t():
    rig = Rig(1.07, shoulder=0.215, hip=0.1)
    s = rig.s
    BK, BK2, SK, HAIR = '#2d3136', '#3b4046', '#e0aa80', '#ecc65a'
    body, arm_l, arm_r, leg_l, leg_r = human_parts(rig, weapon_arm_amp=0.35)
    male_torso(body, rig, BK, wide=1.17, chest=1.12)
    neck(body, rig, SK, r=0.05)
    body.ring(V(0, 0, 0.99 * s), 0.164 * s, 0.012 * s, '#16181b', h=0.04 * s, sx=1.05, sy=.64, seg=18)
    body.box(V(0, -0.11 * s, 0.99 * s), (0.05 * s, 0.012 * s, 0.035 * s), '#9ea6ad')
    body.box(V(0, -0.123 * s, 1.22 * s), (0.014 * s, 0.01 * s, 0.38 * s), BK2)
    body.box(V(0.085 * s, -0.122 * s, 1.31 * s), (0.08 * s, 0.012 * s, 0.07 * s), BK2, mirror=True)
    for side in (1, -1):
        body.add(slab([(0, 0), (0.07 * s, 0.0), (0.04 * s, -0.08 * s)], 0.012 * s), BK2,
                 xform(V(side * 0.04 * s, -0.072 * s, 1.475 * s), (70, 0, side * 25)), smooth=False)
    body.ring(V(0, 0.0, 1.455 * s), 0.055 * s, 0.018 * s, BK2, h=0.05 * s, sx=1, sy=.95)
    hc = rig.head_c
    hs = rig.hsz
    face(body, hc, hs, SK, '#6b3e22', smile=True, brows='#b98d34', brow_tilt=12)
    hair_shell(body, hc, hs, HAIR)
    bangs(body, hc, hs, HAIR, [(-0.06, -0.02), (-0.03, -0.01), (0.0, 0.0), (0.03, 0.01), (0.06, 0.02)], drop=0.075)
    spikes(body, hc, hs, HAIR, [((1, 0.1, -0.2), 0.07, 0.035, (0, 0, -0.02)), ((-1, 0.1, -0.2), 0.07, 0.035, (0, 0, -0.02)),
                               ((0.8, 0.5, -0.4), 0.07, 0.035, (0, 0, -0.03)), ((-0.8, 0.5, -0.4), 0.07, 0.035, (0, 0, -0.03)),
                               ((0.3, 1, -0.3), 0.08, 0.04, (0, 0, 0)), ((-0.3, 1, -0.3), 0.08, 0.04, (0, 0, 0)),
                               ((0, 1, -0.7), 0.06, 0.04, (0, 0, -0.03))])
    m = ball_cap(body, hc, hs, '#26292e', '#1d1f23', tilt=-6)
    # Painel branco com "KILL".
    panel = xform((0, -0.124 * hs, 0.048 * hs), (-26, 0, 0))
    body.add(apply_matrix(box((0.17 * hs, 0.006 * hs, 0.058 * hs)), panel), '#f2f2f0', at=m)
    letters = [  # (x, z, largura, altura, rotação) em unidades da placa: K I L L
        (-0.062, 0, 0.009, 0.042, 0), (-0.048, 0.01, 0.009, 0.026, 42), (-0.048, -0.01, 0.009, 0.026, -42),
        (-0.022, 0, 0.009, 0.042, 0),
        (0.006, 0, 0.009, 0.042, 0), (0.016, -0.0165, 0.026, 0.009, 0),
        (0.044, 0, 0.009, 0.042, 0), (0.054, -0.0165, 0.026, 0.009, 0)]
    for x, z, w, hgt, rot in letters:
        lm = panel @ xform((x * hs, -0.004 * hs, z * hs), (0, rot, 0))
        body.add(apply_matrix(box((w * hs, 0.004 * hs, hgt * hs)), lm), INK, at=m)
    # Braços musculosos: manga curta preta, antebraço à mostra.
    hcl = std_arm(arm_l, rig, 1, BK, SK, sleeve_end=0.0, forearm_col=SK, cuff=BK2, muscle=1.35, fist=True)
    _upper_skin(arm_l, rig, 1, SK, BK, BK2)
    hcr = std_arm(arm_r, rig, -1, BK, SK, pose='hold', sleeve_end=0.0, forearm_col=SK, cuff=BK2, muscle=1.35)
    _upper_skin(arm_r, rig, -1, SK, BK, BK2)
    arm_r.action, arm_l.action = 'recoil', 'slash'
    weapon = Part('weapon', 'weapon', arm_l.pivot, parent='arm_l', action='slash')
    knife(weapon, hcl, s, blade='#7c858e', grip='#15171a', length=0.25, width=0.042, fwd=(0, -1, -0.45))
    for side, leg in ((1, leg_l), (-1, leg_r)):
        hip, kn, an = std_leg(leg, rig, side, BK, thigh=0.088, calf=0.062)
        sneaker(leg, an, s, '#1e2024', '#0f1012', boot=0.17, boot_col='#1e2024', laces='#3a3e44', height=0.11,
                width=0.115)
    return dict(height=1.95, parts=[body, arm_l, arm_r, leg_l, leg_r, weapon], mount=dict(part='arm_r', pos=hcr))


def _upper_skin(part, rig, side, skin, sleeve, cuff):
    """Bíceps à mostra abaixo da manga curta (sobrepõe a parte de baixo do braço)."""
    s = rig.s
    sh = V(side * rig.sh_x, 0.0, rig.sh_z)
    el = V(side * (rig.sh_x + 0.05 * s), 0.025 * s, rig.sh_z - 0.28 * s)
    if part.name == 'arm_r':
        el = V(side * (rig.sh_x + 0.045 * s), 0.035 * s, rig.sh_z - 0.27 * s)
    mid = sh.lerp(el, 0.45)
    part.tube([mid, el], [0.067 * s, 0.056 * s], skin, 12)
    part.add(tube([sh.lerp(el, 0.12), mid + (el - sh).normalized() * 0.01], [0.074 * s, 0.076 * s], 14,
                  ('round', 'flat')), sleeve)
    part.add(tube([mid - (el - sh).normalized() * 0.005, mid + (el - sh).normalized() * 0.015],
                  [0.079 * s, 0.079 * s], 14, ('flat', 'flat')), cuff)


def build_b_cell():
    rig = Rig(1.04)
    s = rig.s
    BL, BL2, BL3, SK, HAIR, GL = '#7097bf', '#5b7fa8', '#8fb2d6', '#f2d2b6', '#9b5630', '#bfc2c6'
    body, arm_l, arm_r, leg_l, leg_r = human_parts(rig, weapon_arm_amp=0.2)
    male_torso(body, rig, BL)
    neck(body, rig, SK)
    body.box(V(0, -0.106 * s, 1.2 * s), (0.014 * s, 0.01 * s, 0.42 * s), BL2)
    for side in (1, -1):
        body.box(V(side * 0.075 * s, -0.113 * s, 1.3 * s), (0.075 * s, 0.012 * s, 0.08 * s), BL, )
        body.box(V(side * 0.075 * s, -0.119 * s, 1.335 * s), (0.08 * s, 0.014 * s, 0.026 * s), BL2)
        body.add(slab([(0, 0), (0.065 * s, 0.0), (0.04 * s, -0.075 * s)], 0.012 * s), BL2,
                 xform(V(side * 0.035 * s, -0.07 * s, 1.47 * s), (72, 0, side * 25)), smooth=False)
    body.ring(V(0, 0.0, 1.445 * s), 0.05 * s, 0.018 * s, BL2, h=0.05 * s, sx=1, sy=.95)
    hc = rig.head_c
    hs = rig.hsz
    face(body, hc, hs, SK, '#4a4a55', smile=True, brows='#6e3b1f')
    hair_shell(body, hc, hs, HAIR)
    bangs(body, hc, hs, HAIR, [(-0.07, -0.03), (-0.04, -0.01), (-0.01, 0.0), (0.02, 0.01), (0.05, 0.02), (0.075, 0.03)],
          drop=0.07)
    spikes(body, hc, hs, HAIR, [((1, 0.0, -0.3), 0.07, 0.03, (0, -0.02, -0.03)), ((-1, 0.0, -0.3), 0.07, 0.03, (0, -0.02, -0.03)),
                               ((0.9, 0.5, -0.1), 0.07, 0.035, (0, 0, 0)), ((-0.9, 0.5, -0.1), 0.07, 0.035, (0, 0, 0)),
                               ((0.5, 0.9, -0.6), 0.08, 0.04, (0, 0, 0)), ((-0.5, 0.9, -0.6), 0.08, 0.04, (0, 0, 0)),
                               ((0, 1, -0.4), 0.07, 0.04, (0, 0, 0))])
    ball_cap(body, hc, hs, BL, BL2, tilt=-14, visor_drop=4)
    # Braço esquerdo com braçadeira "B".
    std_arm(arm_l, rig, 1, BL, GL, sleeve_end=0.55, forearm_col=SK, cuff=BL3)
    am = xform(V(rig.sh_x + 0.062 * s, -0.005 * s, rig.sh_z - 0.13 * s), (0, -10, 0))
    arm_l.add(box((0.012 * s, 0.075 * s, 0.075 * s)), WHITE, am)
    for x, z, w, hgt in ((-0.016, 0, 0.01, 0.05), (0.006, 0.012, 0.024, 0.02), (0.008, -0.012, 0.026, 0.022)):
        arm_l.add(box((0.006 * s, w * s, hgt * s)), INK, am @ xform((0.005 * s, x * s, z * s)))
    for x, z, w, hgt in ((0.006, 0.012, 0.008, 0.007), (0.006, -0.012, 0.009, 0.008)):
        arm_l.add(box((0.008 * s, w * s, hgt * s)), WHITE, am @ xform((0.006 * s, x * s, z * s)))
    hcr = std_arm(arm_r, rig, -1, BL, GL, pose='hold', sleeve_end=0.55, forearm_col=SK, cuff=BL3)
    arm_r.action = 'recoil'
    for side, leg in ((1, leg_l), (-1, leg_r)):
        hip, kn, an = std_leg(leg, rig, side, BL, cuff=BL3)
        leg.tube([an + V(0, 0, 0.02 * s), an + V(0, 0, 0.07 * s)], [0.04 * s, 0.042 * s], SK, 10)
        sneaker(leg, an, s, '#eef0f2', '#39414d', accent='#3d4652', height=0.11, laces='#c8ccd0')
    return dict(height=1.88, parts=[body, arm_l, arm_r, leg_l, leg_r], mount=dict(part='arm_r', pos=hcr))


def build_macrophage():
    rig = Rig(1.0, shoulder=0.165, hip=0.085, female=True)
    s = rig.s
    CR, CR2, LACE, SK, HAIR = '#efe2cf', '#e0cfb8', '#fbf7f1', '#f6dccb', '#c9a17a'
    body, arm_l, arm_r, leg_l, leg_r = human_parts(rig, leg_amp=0.32, weapon_arm_amp=0.18)
    female_torso(body, rig, CR, bust=1.0)
    neck(body, rig, SK, r=0.036)
    # Saia em sino com dobras, babados na barra e faixa recortada.
    folds = lambda i, a: 1 + 0.028 * math.sin(a * 9) * min(1, i / 3)
    body.add(lathe([(0, 1.06 * s), (0.125 * s, 1.06 * s), (0.17 * s, 0.98 * s), (0.27 * s, 0.75 * s),
                    (0.36 * s, 0.5 * s), (0.42 * s, 0.3 * s), (0.44 * s, 0.2 * s), (0, 0.2 * s)][::-1], 36,
                   rfunc=lambda i, a: 1 + 0.028 * math.sin(a * 9) * min(1, (7 - i) / 3)), CR)
    body.add(lathe([(0, 0.1 * s), (0.45 * s, 0.1 * s), (0.47 * s, 0.13 * s), (0.462 * s, 0.215 * s),
                    (0.44 * s, 0.22 * s), (0, 0.22 * s)], 40, rfunc=lambda i, a: 1 + 0.03 * math.sin(a * 20)), LACE)
    body.add(lathe([(0, 0.06 * s), (0.44 * s, 0.06 * s), (0.455 * s, 0.08 * s), (0.45 * s, 0.13 * s), (0, 0.13 * s)],
                   40, rfunc=lambda i, a: 1 + 0.035 * math.sin(a * 20 + 1.6)), '#f6ede2')
    body.add(lathe([(0, 0.22 * s), (0.442 * s, 0.22 * s), (0.425 * s, 0.32 * s), (0, 0.32 * s)], 40,
                   rfunc=lambda i, a: 1 + (0.012 if i in (1, 2) else 0) * abs(math.sin(a * 10))), '#f3e6d6')
    for i in range(16):
        a = TAU * i / 16
        r = 0.437 * s
        body.ell(V(r * math.cos(a), r * math.sin(a), 0.255 * s), (0.022 * s, 0.02 * s, 0.024 * s), LACE, 6, 4)
    body.ring(V(0, 0, 1.06 * s), 0.12 * s, 0.012 * s, CR2, h=0.05 * s, sx=1, sy=.7, seg=18)
    # Peitilho de renda, gola alta e babados dos ombros.
    body.box(V(0, -0.098 * s, 1.31 * s), (0.06 * s, 0.012 * s, 0.17 * s), LACE, rot=(-6, 0, 0))
    for i in range(4):
        body.ell(V(0, -0.104 * s, (1.39 - i * 0.045) * s), (0.04 * s, 0.012 * s, 0.018 * s), LACE, 10, 5)
    body.add(lathe([(0.036 * s, 1.43 * s), (0.05 * s, 1.44 * s), (0.052 * s, 1.5 * s), (0.04 * s, 1.5 * s),
                    (0.036 * s, 1.43 * s)], 16, rfunc=lambda i, a: 1 + 0.08 * math.sin(a * 10)), LACE)
    for side in (1, -1):
        for k in range(3):
            body.add(slab([(0, 0), (0.12 * s, 0.02 * s), (0.14 * s, -0.045 * s), (0.02 * s, -0.05 * s)],
                          0.012 * s), LACE if k % 2 == 0 else '#f3e9dc',
                     xform(V(side * 0.07 * s, (-0.06 + k * 0.05) * s, 1.42 * s), (75 + k * 10, -side * 25, side * (12 - k * 8))),
                     smooth=False)
    hc = rig.head_c
    hs = rig.hsz
    face(body, hc, hs, SK, '#8f5a2c', mouth='#d06a72', brows='#a9805a', lashes='#4a3020')
    hair_shell(body, hc, hs, HAIR, back_drop=0.05)
    bangs(body, hc, hs, HAIR, [(-0.07, -0.01), (-0.045, 0.0), (-0.02, 0.0), (0.03, 0.01), (0.06, 0.015)], drop=0.075)
    for side in (1, -1):
        body.tube([hc + V(side * 0.095, -0.03, 0.05) * hs, hc + V(side * 0.11, -0.04, -0.06) * hs,
                   hc + V(side * 0.095, -0.03, -0.13) * hs], [0.03 * hs, 0.032 * hs, 0.012 * hs], HAIR, 10)
    # Touca franzida.
    cap_c = hc + V(0, 0.012, 0.045) * hs
    body.add(apply_matrix(lathe([(0, -0.01 * hs), (0.125 * hs, -0.01 * hs), (0.14 * hs, 0.04 * hs), (0.13 * hs, 0.1 * hs),
                                 (0.08 * hs, 0.14 * hs), (0, 0.15 * hs)], 24,
                                rfunc=lambda i, a: 1 + (0.035 * math.sin(a * 10) if 1 <= i <= 3 else 0)),
                          xform(cap_c, (-14, 0, 0))), '#f6efe3')
    body.add(apply_matrix(lathe([(0.118 * hs, -0.02 * hs), (0.142 * hs, -0.012 * hs), (0.142 * hs, 0.012 * hs),
                                 (0.118 * hs, 0.018 * hs), (0.118 * hs, -0.02 * hs)], 36,
                                rfunc=lambda i, a: 1 + 0.045 * math.sin(a * 18)), xform(cap_c, (-14, 0, 0))), LACE)
    # Trança (parte própria, balança como cauda).
    braid = Part('braid', 'tail', hc + V(0, 0.1, -0.05) * hs, phase=0.6, amp=0.25)
    pts = bezier(hc + V(0.03, 0.1, -0.05) * hs, hc + V(0.1, 0.2, -0.25) * hs, V(0.2 * hs, 0.17 * hs, 1.15 * hs),
                 V(0.24 * hs, 0.1 * hs, 1.0 * hs), 9)
    for i, q in enumerate(pts):
        nxt = pts[min(i + 1, len(pts) - 1)]
        r = (0.038 - i * 0.002) * hs
        braid.ell(q + V((-1) ** i * 0.008 * hs, 0, 0), (r, r * .9, r * 1.25), HAIR, 8, 6, rot=(0, (-1) ** i * 25, 0))
    tip = pts[-1]
    braid.ell(tip + V(0, 0, -0.05 * hs), (0.02 * hs, 0.02 * hs, 0.035 * hs), HAIR, 8, 5)
    for side in (1, -1):
        braid.ell(tip + V(side * 0.035 * hs, 0, 0.0), (0.035 * hs, 0.012 * hs, 0.022 * hs), LACE, 8, 5, rot=(0, side * 20, 0))
    braid.ell(tip, (0.014 * hs, 0.014 * hs, 0.014 * hs), LACE, 8, 5)
    # Braços: mangas bufantes, punhos de renda.
    for side, part in ((1, arm_l), (-1, arm_r)):
        sh = V(side * rig.sh_x, 0, rig.sh_z)
        part.ell(sh + V(side * 0.01 * s, 0, -0.03 * s), (0.065 * s, 0.065 * s, 0.07 * s), CR, 12, 8)
    std_arm(arm_l, rig, 1, CR, SK, upper=0.046, fore=0.038, cuff=LACE)
    hcr = std_arm(arm_r, rig, -1, CR, SK, pose='hold', upper=0.046, fore=0.038, cuff=LACE)
    for side, leg in ((1, leg_l), (-1, leg_r)):
        hip, kn, an = std_leg(leg, rig, side, '#efe7dc', thigh=0.07, calf=0.05)
        sneaker(leg, an, s, '#e8e0d4', '#9c9286', boot=0.22, boot_col='#e8e0d4', laces='#8d8378', height=0.12,
                width=0.1)
    return dict(height=1.82, parts=[body, braid, arm_l, arm_r, leg_l, leg_r], mount=dict(part='arm_r', pos=hcr))


def build_red_blood_cell():
    rig = Rig(0.975, shoulder=0.165, hip=0.088, female=True)
    s = rig.s
    RED, RED2, TEE, SK, HAIR, DEN, DEN2 = '#d63a3c', '#9f2530', '#2b2b30', '#f6d6c0', '#d9472e', '#5d89b4', '#88acd2'
    body, arm_l, arm_r, leg_l, leg_r = human_parts(rig, arm_amp=0.7, leg_amp=0.6)
    arm_r.action = 'wave'
    female_torso(body, rig, TEE, bust=0.9)
    # Jaqueta vermelha aberta na frente (casca cortada sobre a camiseta).
    jk = tube([V(0, 0, 1.0 * s), V(0, 0, 1.08 * s), V(0, -0.004, 1.2 * s), V(0, -0.012, 1.3 * s),
               V(0, -0.006, 1.38 * s), V(0, 0, 1.43 * s)],
              [(0.142 * s, 0.098 * s), (0.135 * s, 0.093 * s), (0.142 * s, 0.1 * s), (0.162 * s, 0.112 * s),
               (0.16 * s, 0.096 * s), (0.11 * s, 0.07 * s)], 20, (None, None))
    jk = cut(jk, lambda q: not (q.y < -0.035 * s and abs(q.x) < 0.06 * s + (q.z - 1.0 * s) * 0.15))
    body.add(jk, RED)
    body.add(lathe([(0.062 * s, 1.41 * s), (0.075 * s, 1.43 * s), (0.068 * s, 1.5 * s), (0.055 * s, 1.5 * s),
                    (0.062 * s, 1.41 * s)], 16, 1, .95), RED)
    body.ring(V(0, 0, 1.0 * s), 0.142 * s, 0.012 * s, RED2, h=0.035 * s, sx=1.0, sy=.7, seg=18)
    # Short jeans + cinto.
    torso(body, [(0.79 * s, 0, 0), (0.81 * s, 0.11 * s, 0.075 * s), (0.86 * s, 0.158 * s, 0.104 * s),
                 (0.95 * s, 0.158 * s, 0.106 * s), (0.99 * s, 0.13 * s, 0.09 * s), (1.0 * s, 0, 0)], DEN)
    body.ring(V(0, 0, 0.97 * s), 0.152 * s, 0.01 * s, '#b0282e', h=0.03 * s, sx=1.0, sy=.68, seg=18)
    body.box(V(0, -0.108 * s, 0.97 * s), (0.04 * s, 0.01 * s, 0.03 * s), '#d7dbe0')
    # Bolsinha vermelha na cintura (atrás, à direita).
    body.ell(V(-0.12 * s, 0.1 * s, 0.9 * s), (0.07 * s, 0.05 * s, 0.06 * s), RED, 12, 7)
    body.ell(V(-0.12 * s, 0.12 * s, 0.93 * s), (0.06 * s, 0.04 * s, 0.025 * s), RED2, 10, 5)
    neck(body, rig, SK, r=0.036)
    hc = rig.head_c
    hs = rig.hsz
    face(body, hc, hs, SK, '#d29a2c', mouth='#c45a5a', smile=False, brows='#b33a26', lashes='#5a2018')
    hair_shell(body, hc, hs, HAIR)
    bangs(body, hc, hs, HAIR, [(-0.075, -0.02), (-0.05, -0.01), (-0.02, 0.0), (0.01, 0.0), (0.04, 0.01), (0.07, 0.02)],
          drop=0.085)
    spikes(body, hc, hs, HAIR, [((1, -0.1, -0.5), 0.06, 0.03, (0, -0.02, -0.04)), ((-1, -0.1, -0.5), 0.06, 0.03, (0, -0.02, -0.04)),
                               ((0.6, 0.8, -0.5), 0.06, 0.035, (0, 0, -0.03)), ((-0.6, 0.8, -0.5), 0.06, 0.035, (0, 0, -0.03)),
                               ((0, 1, -0.6), 0.06, 0.04, (0, 0, -0.02))])
    # Boné vermelho volumoso com aba preta e emblema branco.
    m = ball_cap(body, hc, hs, RED, '#232428', tilt=-10, r=0.13, h=0.1, brim_len=0.14, brim_w=0.13, puff=1.1,
                 sx=1.05, sy=1.08, badge=None)
    body.ell(m @ V(0.06 * hs, -0.12 * hs, 0.06 * hs), (0.02 * hs, 0.008 * hs, 0.02 * hs), '#f2f2f2', 10, 5, rot=(-30, 0, 20))
    spikes(body, hc + V(0, 0, 0.16) * hs, s, HAIR, [((0.2, -0.2, 1), 0.05, 0.012, (0, 0, -0.1))])
    for side, part in ((1, arm_l), (-1, arm_r)):
        std_arm(part, rig, side, RED, '#f6f6f4', sleeve_end=0.35, forearm_col=SK, cuff=RED2, upper=0.048, fore=0.038)
    arm_l.ell(V(rig.sh_x + 0.055 * s, -0.01 * s, rig.sh_z - 0.08 * s), (0.008 * s, 0.024 * s, 0.024 * s), WHITE, 10, 5)
    arm_l.ell(V(rig.sh_x + 0.06 * s, -0.01 * s, rig.sh_z - 0.08 * s), (0.006 * s, 0.014 * s, 0.014 * s), RED, 8, 5)
    for side, leg in ((1, leg_l), (-1, leg_r)):
        hip, kn, an = std_leg(leg, rig, side, DEN, shorts=DEN, cuff=DEN2, skin=SK, shorts_len=0.13, thigh=0.074,
                              calf=0.052)
        leg.tube([an + V(0, 0, 0.0), an + V(0, 0, 0.07 * s)], [0.046 * s, 0.046 * s], '#2a2a2e', 10)
        sneaker(leg, an, s, '#d4473b', '#f0ece6', height=0.1, laces='#f3d0c8', width=0.098)
    return dict(height=1.78, parts=[body, arm_l, arm_r, leg_l, leg_r])


def build_platelet():
    s = 0.58
    rig = Rig(s, shoulder=0.18, hip=0.1)
    # Proporções infantis: cabeça grande, pernas curtas.
    rig.head = 0.875
    rig.sh_z, rig.hip_z, rig.knee, rig.ankle = 0.645, 0.43, 0.25, 0.05
    BLU, BLU2, SK, HAIR, SH, CAP = '#a9dcf1', '#8ec8e2', '#f8dccb', '#c8874c', '#e7d6bb', '#efefec'
    body, arm_l, arm_r, leg_l, leg_r = human_parts(rig, arm_amp=0.8, leg_amp=0.55)
    arm_r.action = 'wave'
    hs = 1.32  # escala da cabeça (proporção infantil)
    # Bata azul larga em sino.
    body.add(lathe([(0, 0.355), (0.205, 0.355), (0.215, 0.37), (0.19, 0.48), (0.15, 0.6), (0.12, 0.65),
                    (0.06, 0.68), (0, 0.69)], 24, sx=1.0, sy=.78), BLU)
    body.add(lathe([(0.2, 0.345), (0.218, 0.35), (0.22, 0.38), (0.2, 0.38), (0.2, 0.345)], 24, sx=1, sy=.78), BLU2)
    body.ring(V(0, 0, 0.675), 0.05, 0.01, BLU2, h=0.02, sy=.9)
    torso(body, [(0.33, 0, 0), (0.34, 0.12, 0.08), (0.38, 0.13, 0.085), (0.40, 0, 0)], SH)
    body.tube([V(0, 0, 0.66), V(0, 0, rig.head - 0.1)], [0.03, 0.028], SK, 10)
    hc = V(0, 0.004, rig.head)
    face(body, hc, s * hs * 1.12, SK, '#8a4f22', smile=True, brows='#9a6232', lashes='#4a2810', eye_w=1.08)
    # Cabelo longo pelas costas.
    hair_shell(body, hc, s * hs * 1.12, HAIR, back_drop=0.02)
    body.add(cut(lathe([(0.0, 0.47), (0.13, 0.47), (0.14, 0.6), (0.13, 0.75), (0.12, 0.86), (0.0, 0.9)], 18,
                       sx=1.05, sy=.8), lambda q: q.y > 0.0), HAIR, at=V(0, 0.025, 0))
    bangs(body, hc, s * hs * 1.12, HAIR, [(-0.07, -0.02), (-0.04, -0.01), (-0.01, 0.0), (0.02, 0.01), (0.05, 0.015),
                                           (0.075, 0.025)], drop=0.075)
    for side in (1, -1):
        body.tube([hc + V(side * 0.075, -0.03, 0.03), hc + V(side * 0.085, -0.035, -0.07), V(side * 0.08, -0.01, 0.6)],
                  [0.025, 0.028, 0.01], HAIR, 10)
    m = ball_cap(body, hc, s * hs * 1.12, CAP, '#e2e2de', tilt=-6)
    for i in range(3):
        body.box(m @ V((i - 1) * 0.024, -0.08, 0.035), (0.018, 0.005, 0.018), '#8a8a86', rot=(-28, 0, 0))
    # Bolsa amarela e alça cruzada.
    body.box(V(0.2, -0.02, 0.43), (0.06, 0.16, 0.13), '#f0c24a', bevel=0.015)
    body.box(V(0.232, -0.02, 0.46), (0.012, 0.15, 0.07), '#e2ad32')
    body.tube([V(-0.11, -0.005, 0.66), V(-0.02, -0.085, 0.6), V(0.12, -0.095, 0.5), V(0.2, -0.04, 0.49)],
              [0.012, 0.012, 0.012, 0.012], '#f0c24a', 6, hint=(0, 1, 0))
    body.tube([V(-0.11, 0.005, 0.66), V(0.0, 0.075, 0.6), V(0.12, 0.08, 0.5), V(0.2, 0.0, 0.49)],
              [0.012, 0.012, 0.012, 0.012], '#f0c24a', 6, hint=(0, 1, 0))
    for side, part in ((1, arm_l), (-1, arm_r)):
        sh = V(side * 0.115, 0, rig.sh_z)
        el = V(side * 0.15, 0.01, 0.53)
        wr = V(side * 0.17, -0.02, 0.42)
        part.ell(sh, (0.05, 0.05, 0.045), BLU, 12, 7)
        part.tube([sh, sh.lerp(el, 0.65)], [0.048, 0.05], BLU, 12, ('round', 'flat'))
        part.add(tube([sh.lerp(el, 0.6), sh.lerp(el, 0.7)], [0.052, 0.052], 12, ('flat', 'flat')), BLU2)
        part.tube([sh.lerp(el, 0.3), el, wr], [0.028, 0.026, 0.022], SK, 10)
        hand(part, wr + V(0, -0.005, -0.03), 0.62, SK, fist=False)
        part.pivot = sh
    for side, leg in ((1, leg_l), (-1, leg_r)):
        hip = V(side * 0.065, 0, rig.hip_z)
        an = V(side * 0.07, 0, 0.07)
        leg.tube([hip, V(side * 0.068, 0, 0.3)], [0.06, 0.062], SH, 12, ('round', 'flat'))
        leg.tube([V(side * 0.068, 0, 0.32), an], [0.035, 0.03], SK, 10)
        leg.add(tube([V(side * 0.07, 0.0, 0.02), V(side * 0.07, 0.0, 0.2)], [0.048, 0.05], 14, ('flat', 'flat')),
                '#2c2f36')
        leg.add(tube([V(side * 0.07, 0.0, 0.18), V(side * 0.07, 0.0, 0.235)], [0.054, 0.058], 14, ('flat', 'flat')),
                '#eceeef')
        leg.ell(V(side * 0.07, -0.035, 0.045), (0.05, 0.085, 0.045), '#2c2f36', 12, 7)
        leg.box(V(side * 0.07, -0.03, 0.009), (0.1, 0.17, 0.018), '#dfe2e4', bevel=0.006)
        leg.pivot = hip
    return dict(height=1.0, parts=[body, arm_l, arm_r, leg_l, leg_r])


# ---------------------------------------------------------------------------------------
# Bactérias
# ---------------------------------------------------------------------------------------

def bead_chain(p, pts, r0, r1, color, ring_col=None, every=3, seg=8):
    p.tube(pts, [r0 + (r1 - r0) * i / (len(pts) - 1) for i in range(len(pts))], color, seg)
    if ring_col:
        for i in range(every, len(pts) - 1, every):
            d = (pts[i + 1] - pts[i - 1]).normalized()
            r = (r0 + (r1 - r0) * i / (len(pts) - 1)) * 1.45
            p.add(tube([pts[i] - d * r * .45, pts[i] + d * r * .45], [r, r], seg, ('flat', 'flat')), ring_col)


def claw(p, base, d, length, r, color, curl=(0, 0, -1), seg=5):
    d, c = V(d).normalized(), V(curl).normalized()
    pts = [V(base), V(base) + d * length * .45 + c * length * .05, V(base) + d * length * .85 + c * length * .25,
           V(base) + d * length + c * length * .5]
    p.tube(pts, [r, r * .7, r * .35, 0], color, seg, ('round', None))


def build_pneumococcus():
    LAV, DARK, PALE, CLAW, RING = '#8b90e8', '#666bc6', '#e9ebf6', '#24242c', '#7277d4'
    body = Part('body')
    # Pernas esqueléticas.
    legs = []
    for side, name in ((1, 'leg_l'), (-1, 'leg_r')):
        leg = Part(name, 'leg', (side * 0.11, 0, 1.0), phase=0 if side > 0 else math.pi, amp=0.45)
        hip, kn, an = V(side * 0.11, 0, 1.0), V(side * 0.13, -0.02, 0.55), V(side * 0.13, 0.02, 0.12)
        leg.tube([hip, kn], [0.05, 0.04], LAV, 10)
        leg.ell(kn, (0.06, 0.06, 0.07), LAV, 10, 7)
        leg.add(tube([kn + V(0, -0.02, -0.05), an], [(0.055, 0.045), (0.035, 0.03)], 8, ('round', 'round')), LAV,
                smooth=False)
        for z in (0.36, 0.3):
            leg.add(tube([V(side * 0.13, 0.0, z), V(side * 0.13, 0.0, z + 0.02)], [0.05, 0.05], 10, ('round', 'round')),
                    RING)
        leg.ell(an + V(0, -0.04, -0.06), (0.06, 0.1, 0.05), LAV, 10, 6)
        for k in (-1, 0, 1):
            claw(leg, an + V(k * 0.035, -0.12, -0.08), (k * 0.25, -1, 0.1), 0.09, 0.016, CLAW)
        claw(leg, an + V(0, 0.04, -0.08), (0, 1, 0.1), 0.07, 0.014, CLAW)
        legs.append(leg)
    # Pélvis blindada, barra do quadril, ventre pálido, caixa torácica.
    body.ell(V(0, 0, 1.02), (0.13, 0.09, 0.08), LAV, 14, 8)
    body.ell(V(0.06, -0.04, 0.98), (0.07, 0.06, 0.07), LAV, 10, 7, mirror=True)
    body.tube([V(-0.2, 0, 1.1), V(0.2, 0, 1.1)], [0.025, 0.025], LAV, 8)
    body.ell(V(0.21, 0, 1.1), 0.04, LAV, 10, 6, mirror=True)
    torso(body, [(1.08, 0, 0), (1.1, 0.06, 0.045), (1.2, 0.07, 0.05), (1.3, 0.09, 0.06), (1.32, 0, 0)], PALE)
    torso(body, [(1.27, 0, 0), (1.29, 0.13, 0.08), (1.36, 0.16, 0.095, -0.01), (1.45, 0.17, 0.095),
                 (1.53, 0.14, 0.08), (1.56, 0, 0)], LAV)
    body.ring(V(0, -0.01, 1.29), 0.125, 0.012, PALE, h=0.02, sy=0.66)
    for i in range(4):
        body.box(V(0, -0.1, 1.36 + i * 0.045), (0.07 - i * 0.008, 0.01, 0.008), DARK)
        body.box(V(0, -0.104, 1.36 + i * 0.045), (0.008, 0.012, 0.03), DARK)
    for side in (1, -1):
        body.tube([V(side * 0.03, -0.05, 1.53), V(side * 0.2, -0.0, 1.52)], [0.03, 0.025], LAV, 8)
    body.tube([V(0, 0.01, 1.52), V(0, 0, 1.66)], [0.035, 0.032], PALE, 8)
    # Cabeça: rosto pálido, máscara negra, capuz pontudo com aletas.
    hc = V(0, 0.0, 1.73)
    face(body, hc, 0.85, PALE, '#f4f4f8', mask=INK, smile=True)
    hood = apply_matrix(ellipsoid((0.11, 0.115, 0.12), 16, 10), Matrix.Translation(hc + V(0, 0.015, 0.02)))
    hood = cut(hood, lambda q: not (q.y < hc.y - 0.02 and q.z < hc.z + 0.03))
    body.add(hood, LAV)
    body.cone(hc + V(0, 0.02, 0.08), hc + V(0, -0.02, 0.24), 0.09, LAV, 10, flat=.5, hint=(0, 1, 0))
    for side in (1, -1):
        body.cone(hc + V(side * 0.07, 0.0, 0.05), hc + V(side * 0.19, 0.02, 0.12), 0.05, LAV, 8, flat=.4,
                  hint=(0, 1, 0))
        body.cone(hc + V(side * 0.08, -0.02, -0.02), hc + V(side * 0.15, -0.05, -0.1), 0.04, LAV, 8, flat=.4,
                  hint=(0, 1, 0))
    for k in range(3):
        body.box(hc + V(0, -0.095 + k * 0.01, 0.1 + k * 0.03), (0.006, 0.02, 0.05), DARK, rot=(30, 0, 0))
    # Braços com garras.
    arms = []
    for side, name in ((1, 'arm_l'), (-1, 'arm_r')):
        arm = Part(name, 'arm', (side * 0.21, 0, 1.52), phase=math.pi if side > 0 else 0, amp=0.5,
                   action='slash' if side < 0 else None)
        sh = V(side * 0.21, 0, 1.52)
        el = V(side * 0.29, 0.04, 1.2)
        wr = V(side * 0.32, -0.04, 0.93)
        if side < 0:  # segura o canhão de cápsula à frente
            el, wr = V(-0.29, 0.07, 1.26), V(-0.29, -0.2, 1.17)
            arm.action = 'recoil'
            mount = dict(part='arm_r', pos=wr)
        arm.ell(sh, 0.06, LAV, 10, 7)
        arm.tube([sh, el], [0.035, 0.03], LAV, 8)
        arm.ell(el, 0.04, LAV, 10, 6)
        arm.add(tube([el, wr], [(0.04, 0.03), (0.03, 0.025)], 8, ('round', 'round')), LAV, smooth=False)
        arm.add(tube([el.lerp(wr, 0.6), el.lerp(wr, 0.66)], [0.04, 0.04], 10), RING)
        arm.ell(wr + V(0, -0.01, -0.04), (0.035, 0.03, 0.05), LAV, 10, 6)
        for k in range(4 if side > 0 else 0):
            b = wr + V(side * (-0.02 + k * 0.015), -0.03 + k * 0.012, -0.08)
            arm.tube([b + V(0, 0, 0.03), b], [0.012, 0.012], LAV, 6)
            claw(arm, b, (side * 0.15, -0.3, -1), 0.13, 0.014, CLAW, curl=(0, -1, 0))
        arms.append(arm)
    # Tentáculos: saem da nuca/ombros, sobem em arco e descem até o chão com garras.
    tents = []
    for side, name in ((1, 'tentacles_a'), (-1, 'tentacles_b')):
        tp = Part(name, 'tentacle', (side * 0.05, 0.08, 1.7), phase=0 if side > 0 else 1.7, amp=0.12)
        specs = [((0.04, 0.07, 1.78), (0.25, 0.2, 2.25), (0.75, 0.35, 1.6), (0.85, 0.3, 0.05)),
                 ((0.06, 0.09, 1.72), (0.45, 0.25, 2.1), (0.62, 0.55, 1.2), (0.55, 0.62, 0.04)),
                 ((0.05, 0.08, 1.65), (0.35, 0.05, 1.9), (0.58, -0.3, 1.3), (0.62, -0.32, 0.05)),
                 ((0.1, 0.05, 1.55), (0.45, 0.1, 1.55), (0.42, 0.25, 0.8), (0.32, 0.42, 0.05))]
        for p0, p1, p2, p3 in specs:
            pts = bezier(V(side * p0[0], p0[1], p0[2]), V(side * p1[0], p1[1], p1[2]), V(side * p2[0], p2[1], p2[2]),
                         V(side * p3[0], p3[1], p3[2]), 10)
            bead_chain(tp, pts, 0.019, 0.013, LAV, RING, every=3, seg=6)
            d = (pts[-1] - pts[-2]).normalized()
            claw(tp, pts[-1], d, 0.15, 0.018, CLAW, curl=(side, 0, 0))
        tents.append(tp)
    return dict(height=2.0, parts=[body, *arms, *legs, *tents], mount=mount)


def build_staphylococcus():
    Y, Y2, Y3, PALE, CLAW = '#e8d84e', '#d2c02a', '#c4b11e', '#f4f1e4', '#24242a'
    rng = random.Random(7)
    body = Part('body')
    # Cacho de esferas (corpo inferior).
    n = 30
    for i in range(n):
        t = (i + 0.5) / n
        z = 1 - 2 * t
        r = math.sqrt(1 - z * z)
        a = i * 2.39996
        q = V(0.28 * r * math.cos(a), 0.25 * r * math.sin(a), 0.6 + 0.33 * z)
        rad = rng.uniform(0.14, 0.165)
        if q.z > 0.88:
            rad *= 0.75
        body.ell(q, rad, (Y2, Y3, '#dccb36')[i % 3], 10, 7)
        # Brilho especular de cada esfera (como no desenho de referência).
        hl = ((q - V(0, 0, 0.6)).normalized() * 0.4 + V(-0.35, -0.55, 0.75).normalized() * 0.6).normalized()
        body.ell(q + hl * rad * 0.93, (rad * 0.2, rad * 0.2, rad * 0.2), '#fbf3a8', 5, 3)
    body.ell(V(0, 0, 0.6), (0.27, 0.24, 0.32), '#8a7a14', 10, 7)
    for i in range(14):
        a = TAU * i / 14
        body.ell(V(0.2 * math.cos(a), 0.17 * math.sin(a), 1.02), (0.075, 0.06, 0.045), Y, 8, 5,
                 rot=(0, 0, math.degrees(a)))
    # Tronco delgado com manchas brancas ovais.
    torso(body, [(0.98, 0, 0), (1.0, 0.1, 0.07), (1.12, 0.08, 0.06), (1.25, 0.1, 0.065), (1.38, 0.14, 0.075),
                 (1.46, 0.12, 0.065), (1.5, 0, 0)], Y)
    for i, z in enumerate((1.12, 1.2, 1.29, 1.38)):
        w = 0.035 if i % 2 else 0.028
        body.ell(V(0, -0.07 - (0.01 if z > 1.25 else 0), z), (w + 0.008, 0.012, 0.022), Y3, 10, 5)
        body.ell(V(0, -0.078 - (0.01 if z > 1.25 else 0), z), (w, 0.012, 0.016), WHITE, 10, 5)
    for side in (1, -1):
        body.cone(V(side * 0.1, -0.03, 1.42), V(side * 0.15, -0.06, 1.56), 0.03, Y, 8)
    body.tube([V(0, 0, 1.45), V(0, 0, 1.58)], [0.03, 0.028], PALE, 8)
    # Cabeça: rosto pálido, capacete amarelo e "cabelo" de esferas.
    hc = V(0, 0, 1.68)
    face(body, hc, 0.88, PALE, '#c99a2a', mask=None, mouth='#7a6a5a')
    helm = apply_matrix(ellipsoid((0.1, 0.105, 0.115), 16, 10), Matrix.Translation(hc + V(0, 0.012, 0.015)))
    helm = cut(helm, lambda q: not (q.y < -0.03 and q.z < hc.z + 0.04 and abs(q.x) < 0.085))
    body.add(helm, Y)
    body.tube([hc + V(0, -0.1, 0.06), hc + V(0, -0.02, 0.13), hc + V(0, 0.09, 0.07)], [0.012, 0.014, 0.012], Y2, 6)
    for side in (1, -1):
        for k, (dx, dz, r) in enumerate(((0.12, 0.06, 0.06), (0.15, -0.02, 0.065), (0.13, -0.1, 0.06),
                                          (0.07, 0.11, 0.055))):
            body.ell(hc + V(side * dx, 0.02, dz), r, Y, 10, 7)
        body.box(hc + V(side * 0.045, -0.085, 0.005), (0.06, 0.01, 0.01), '#4a4030', rot=(0, side * 12, -side * 16))
    # Braços finos com garras.
    arms = []
    for side, name in ((1, 'arm_l'), (-1, 'arm_r')):
        arm = Part(name, 'arm', (side * 0.15, 0, 1.43), phase=math.pi if side > 0 else 0, amp=0.45,
                   action='slash' if side < 0 else None)
        sh, el, wr = V(side * 0.15, 0, 1.43), V(side * 0.24, 0.03, 1.18), V(side * 0.3, -0.05, 0.95)
        if side < 0:  # segura o lançador de cachos à frente
            el, wr = V(-0.24, 0.06, 1.18), V(-0.25, -0.2, 1.1)
            arm.action = 'recoil'
            mount = dict(part='arm_r', pos=wr)
        arm.ell(sh, 0.045, Y, 10, 6)
        arm.tube([sh, el], [0.03, 0.026], Y, 8)
        arm.ell(el, 0.034, Y, 8, 6)
        arm.tube([el, wr], [0.03, 0.026], Y, 8)
        arm.ell(wr + V(0, -0.015, -0.035), (0.034, 0.04, 0.045), Y, 10, 6)
        for k in range(3 if side > 0 else 0):
            claw(arm, wr + V(side * (-0.015 + k * 0.015), -0.04, -0.07), (side * 0.1 * (k - 1), -0.4, -1), 0.1, 0.012,
                 CLAW, curl=(0, -1, 0))
        arms.append(arm)
    # Pernas finas que saem de baixo do cacho até o chão, com garras.
    legs = []
    for side, name in ((1, 'leg_l'), (-1, 'leg_r')):
        leg = Part(name, 'leg', (side * 0.1, -0.05, 0.48), phase=0 if side > 0 else math.pi, amp=0.35)
        top, mid, bot = V(side * 0.1, -0.05, 0.48), V(side * 0.12, -0.09, 0.26), V(side * 0.12, -0.04, 0.09)
        leg.tube([top, mid, bot], [0.05, 0.04, 0.026], Y, 10)
        leg.add(tube([mid, bot], [(0.03, 0.015), (0.02, 0.01)], 6, ('round', 'round'), hint=(0, 1, 0)), Y2)
        claw(leg, bot, (0, -0.2, -1), 0.11, 0.022, CLAW, curl=(0, -1, 0))
        legs.append(leg)
    # Cauda: sai de trás do cacho e desce em curva até o chão, terminando em garra.
    tail = Part('tail', 'tail', (0, 0.3, 0.55), phase=0.0, amp=0.25, action='strike')
    pts = bezier(V(0, 0.25, 0.55), V(0.15, 0.7, 0.75), V(0.35, 0.85, 0.15), V(0.32, 0.62, 0.05), 16)
    tail.tube(pts, [0.05 - 0.03 * i / 16 for i in range(17)], Y, 10)
    tail.ell(pts[-1], (0.035, 0.03, 0.04), Y2, 10, 6)
    claw(tail, pts[-1], (pts[-1] - pts[-3]), 0.14, 0.022, CLAW, curl=(0, 0, 1))
    return dict(height=1.9, parts=[body, *arms, *legs, tail], mount=mount)


def build_pseudomonas():
    G, G2, G3, CLAW = '#c3d76e', '#a6bc55', '#8da044', '#24242a'
    body = Part('body')
    # Tórax bulboso + corpo traseiro alongado (frente em -Y).
    body.ell(V(0, -0.2, 0.62), (0.31, 0.32, 0.36), G, 20, 12)
    body.tube([V(0, -0.15, 0.62), V(0, 0.15, 0.58), V(0, 0.42, 0.5), V(0, 0.55, 0.47)],
              [(0.3, 0.3), (0.27, 0.27), (0.22, 0.2), (0.18, 0.16)], G, 18, ('round', 'flat'), hint=(1, 0, 0))
    # Barriga com segmentos (linhas escuras) e dobras laterais.
    for i in range(5):
        y = -0.38 + i * 0.1
        body.add(cut(apply_matrix(lathe([(0.29, -0.01), (0.31, 0.0), (0.29, 0.01), (0.29, -0.01)], 24),
                                  xform(V(0, y, 0.55), (90, 0, 0), (0.95, 0.95, 1))), lambda q: q.z < 0.42), G3)
    for k in range(3):
        body.box(V(-0.22, -0.32 + k * 0.03, 0.82 - k * 0.04), (0.06, 0.008, 0.008), G3, rot=(0, -40, 20))
    # Cabeça (parte própria) com pescoço, olho único e boca de dentes de tubarão.
    head = Part('head', 'head', (0, -0.25, 0.85), action='lunge', amp=0.12)
    head.tube([V(0, -0.2, 0.75), V(0, -0.28, 0.98), V(0, -0.38, 1.12)], [(0.2, 0.19), (0.17, 0.16), (0.17, 0.17)],
              G, 16, ('round', 'round'))
    hcn = V(0, -0.46, 1.2)
    head.ell(hcn, (0.23, 0.27, 0.25), G, 20, 12, rot=(-15, 0, 0))
    eye = hcn + V(0, -0.215, 0.05)
    head.ell(eye, (0.11, 0.08, 0.115), G2, 16, 9)
    head.ell(eye + V(0, -0.03, 0), (0.095, 0.06, 0.1), WHITE, 16, 9)
    head.ell(eye + V(0, -0.075, 0), (0.07, 0.025, 0.075), '#dca03a', 14, 7)
    head.ell(eye + V(0, -0.088, 0), (0.05, 0.02, 0.055), '#c07a1e', 14, 7)
    head.ell(eye + V(0, -0.1, 0), (0.012, 0.012, 0.045), INK, 8, 5)
    head.ell(eye + V(0.025, -0.1, 0.03), (0.012, 0.008, 0.012), WHITE, 6, 4)
    # Pálpebra superior.
    lid = cut(ellipsoid((0.118, 0.088, 0.125), 16, 9), lambda q: q.z > 0.045)
    head.add(lid, G2, at=eye)
    mouth = hcn + V(0, -0.2, -0.13)
    head.ell(mouth, (0.15, 0.07, 0.065), '#2e4680', 16, 8)
    head.ell(mouth + V(0, -0.012, 0), (0.135, 0.06, 0.05), '#5f8fd8', 16, 8)
    head.ell(mouth + V(0, -0.02, 0), (0.115, 0.05, 0.035), '#24345e', 14, 6)
    for i in range(11):
        a = math.pi * (0.1 + 0.8 * i / 10)
        x = -0.12 * math.cos(a)
        y = -0.045 - 0.025 * math.sin(a)
        base_u = mouth + V(x, y, 0.035)
        head.cone(base_u, base_u + V(0, -0.01, -0.035), 0.012, WHITE, 5)
        base_d = mouth + V(x * 0.9, y + 0.005, -0.035)
        head.cone(base_d, base_d + V(0, -0.01, 0.03), 0.011, WHITE, 5)
    # Lábio/queixo verde que fecha a boca.
    head.ell(mouth + V(0, 0.0, -0.06), (0.15, 0.08, 0.04), G, 14, 7)
    # Seis patas-tentáculo (marcha em tripé) e dois bigodes.
    parts = [body, head]
    legs = [(1, -0.36, 0.0, 'leg_l1'), (-1, -0.36, math.pi, 'leg_r1'), (1, 0.0, math.pi, 'leg_l2'),
            (-1, 0.0, 0.0, 'leg_r2'), (1, 0.34, 0.0, 'leg_l3'), (-1, 0.34, math.pi, 'leg_r3')]
    for side, y, ph, name in legs:
        piv = V(side * 0.2, y, 0.42)
        leg = Part(name, 'leg', piv, phase=ph, amp=0.35)
        pts = bezier(piv, piv + V(side * 0.16, -0.02, -0.12), V(side * 0.42, y - 0.05, 0.02),
                     V(side * 0.52, y - 0.02, 0.06), 10)
        pts += [V(side * 0.56, y + 0.03, 0.1), V(side * 0.54, y + 0.07, 0.12)]
        leg.tube(pts, [0.1 - 0.075 * i / (len(pts) - 1) for i in range(len(pts))], G, 12)
        parts.append(leg)
    whisk = Part('tentacles_a', 'tentacle', (0, -0.45, 0.8), phase=0.8, amp=0.18)
    for side in (1, -1):
        pts = bezier(V(side * 0.16, -0.46, 0.82), V(side * 0.3, -0.62, 0.75), V(side * 0.3, -0.62, 0.3),
                     V(side * 0.42, -0.72, 0.12), 12)
        whisk.tube(pts, [0.03 - 0.022 * i / 12 for i in range(13)], G, 8)
    parts.append(whisk)
    tail = Part('tail', 'tail', (0, 0.5, 0.48), phase=0.0, amp=0.3, action='strike')
    pts = bezier(V(0, 0.48, 0.48), V(0, 0.8, 0.45), V(0.06, 1.0, 0.25), V(0.12, 1.25, 0.02), 14)
    tail.tube(pts, [(0.17 - 0.15 * i / 14, 0.15 - 0.135 * i / 14) for i in range(15)], G, 14, ('round', 'round'))
    parts.append(tail)
    return dict(height=1.5, parts=parts, mount=dict(part='body', pos=V(-0.26, -0.3, 0.92)))


def build_streptococcus():
    PK, PK2, PALE, CLAW, EYE = '#d84f84', '#a83565', '#eef0f5', '#232329', '#e6c843'
    body = Part('body')
    # Pélvis/couraça, ventre pálido, peitoral com costelas.
    torso(body, [(0.94, 0, 0), (0.96, 0.12, 0.08), (1.02, 0.16, 0.1), (1.1, 0.14, 0.09), (1.12, 0, 0)], PK)
    body.ell(V(0, -0.07, 1.0), (0.08, 0.04, 0.05), PALE, 10, 6)
    torso(body, [(1.08, 0, 0), (1.1, 0.075, 0.05), (1.22, 0.075, 0.055), (1.3, 0.1, 0.065), (1.32, 0, 0)], PALE)
    torso(body, [(1.28, 0, 0), (1.3, 0.14, 0.08), (1.37, 0.16, 0.095, -0.005), (1.46, 0.17, 0.095),
                 (1.53, 0.14, 0.08), (1.56, 0, 0)], PK)
    for i in range(3):
        body.tube([V(-0.13, -0.08, 1.33 + i * 0.06), V(0, -0.105, 1.36 + i * 0.06), V(0.13, -0.08, 1.33 + i * 0.06)],
                  [0.014, 0.016, 0.014], PK2, 8)
    body.tube([V(-0.2, -0.04, 1.53), V(0, -0.08, 1.5), V(0.2, -0.04, 1.53)], [0.025, 0.028, 0.025], PK, 8)
    body.tube([V(0, 0.01, 1.52), V(0, 0, 1.66)], [0.034, 0.03], PALE, 8)
    for side in (1, -1):
        body.cone(V(side * 0.14, -0.03, 1.55), V(side * 0.19, -0.03, 1.66), 0.025, CLAW, 6)
        body.cone(V(side * 0.12, -0.03, 1.03), V(side * 0.24, -0.06, 1.0), 0.02, CLAW, 6)
    # Cabeça: rosto pálido, máscara, capacete com chifre central e aletas laterais.
    hc = V(0, 0.0, 1.74)
    face(body, hc, 0.85, PALE, EYE, mask=INK, mouth='#6a5560')
    helm = apply_matrix(ellipsoid((0.105, 0.11, 0.118), 16, 10), Matrix.Translation(hc + V(0, 0.012, 0.018)))
    helm = cut(helm, lambda q: not (q.y < -0.025 and q.z < hc.z + 0.035 and abs(q.x) < 0.08))
    body.add(helm, PK)
    body.add(tube([hc + V(0, 0.0, 0.08), hc + V(0, -0.01, 0.3)], [(0.075, 0.06), 0], 8, ('flat', None)), PK,
             smooth=False)
    for side in (1, -1):
        body.add(tube([hc + V(side * 0.07, 0.0, 0.06), hc + V(side * 0.24, 0.0, 0.1)], [(0.06, 0.03), 0], 6,
                      ('flat', None), hint=(0, 0, 1)), PK, smooth=False)
        body.add(tube([hc + V(side * 0.09, -0.04, -0.03), hc + V(side * 0.12, -0.08, -0.12)], [(0.03, 0.02), 0], 6,
                      ('flat', None)), PK, smooth=False)
    body.box(hc + V(0, -0.1, 0.06), (0.03, 0.02, 0.06), PK, rot=(30, 0, 0))
    # Braços com garras longas.
    arms = []
    for side, name in ((1, 'arm_l'), (-1, 'arm_r')):
        arm = Part(name, 'arm', (side * 0.21, 0, 1.52), phase=math.pi if side > 0 else 0, amp=0.5,
                   action='slash' if side > 0 else 'recoil')
        sh, el, wr = V(side * 0.21, 0, 1.52), V(side * 0.27, 0.04, 1.22), V(side * 0.33, -0.04, 0.96)
        if side < 0:  # segura a SMG de contas à frente
            el, wr = V(-0.28, 0.07, 1.25), V(-0.29, -0.2, 1.16)
            mount = dict(part='arm_r', pos=wr)
        arm.ell(sh, (0.07, 0.065, 0.06), PK, 12, 7)
        arm.cone(sh + V(side * 0.03, 0, 0.04), sh + V(side * 0.09, 0, 0.12), 0.025, CLAW, 6)
        arm.tube([sh, el], [0.032, 0.028], PK, 8)
        arm.ell(el, 0.036, PK, 8, 6)
        arm.add(tube([el, wr], [(0.042, 0.034), (0.03, 0.026)], 8, ('round', 'round')), PK, smooth=False)
        arm.ell(wr + V(0, -0.01, -0.04), (0.032, 0.035, 0.045), PK, 10, 6)
        if side > 0:
            claw(arm, wr + V(0, -0.02, -0.07), (side * 0.15, -0.35, -1), 0.3, 0.03, CLAW, curl=(-side * 0.2, 1, 0))
        arms.append(arm)
    legs = []
    for side, name in ((1, 'leg_l'), (-1, 'leg_r')):
        leg = Part(name, 'leg', (side * 0.1, 0, 0.98), phase=0 if side > 0 else math.pi, amp=0.45)
        hip, kn, an = V(side * 0.1, 0, 0.98), V(side * 0.12, -0.03, 0.52), V(side * 0.12, 0.03, 0.1)
        leg.add(tube([hip, kn], [(0.075, 0.07), (0.055, 0.05)], 8, ('round', 'round')), PK, smooth=False)
        leg.ell(kn + V(0, -0.02, 0), (0.06, 0.06, 0.07), PK2, 10, 6)
        leg.add(tube([kn, an], [(0.065, 0.06), (0.045, 0.04)], 8, ('round', 'round')), PK, smooth=False)
        leg.add(tube([an + V(0, 0.02, 0.0), an + V(0, -0.2, -0.09)], [(0.045, 0.04), 0], 8, ('flat', None)), CLAW,
                smooth=False)
        leg.add(tube([an + V(0, 0.02, -0.02), an + V(0, 0.07, -0.1)], [(0.02, 0.02), 0], 6, ('flat', None)), CLAW)
        legs.append(leg)
    # Cauda segmentada com espinhos (sai da nuca) e pinça na ponta.
    tail = Part('tail', 'tail', (0, 0.08, 1.75), phase=0.0, amp=0.15, action='strike')
    pts = bezier(V(0, 0.08, 1.78), V(0.05, 0.5, 2.25), V(0.45, 0.65, 1.7), V(0.36, 0.45, 0.85), 15)
    for i, q in enumerate(pts):
        r = 0.075 - 0.025 * i / len(pts)
        d = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        tail.add(tube([q - d * r * 0.7, q + d * r * 0.7], [r, r * 1.05], 8, ('round', 'round')),
                 PK if i % 2 else PK2)
        out = d.cross(V(1, 0, 0)).normalized()
        if out.dot(q - V(0.2, 0.4, 1.5)) < 0:
            out = -out
        tail.cone(q + out * r * 0.7, q + out * (r + 0.07), 0.018, CLAW, 6)
    tip = pts[-1]
    d = (pts[-1] - pts[-2]).normalized()
    tail.ell(tip + d * 0.05, (0.06, 0.06, 0.08), PK, 10, 7)
    claw(tail, tip + d * 0.1, d, 0.26, 0.04, CLAW, curl=(0, -1, 0))
    claw(tail, tip + d * 0.08 + V(0.02, 0.02, 0), d + V(0, 0.5, 0), 0.16, 0.03, CLAW, curl=(0, 1, 0))
    # Correntes de contas pendendo dos quadris até o chão, com garras.
    tents = []
    for side, name in ((1, 'tentacles_a'), (-1, 'tentacles_b')):
        tp = Part(name, 'tentacle', (side * 0.17, 0, 1.03), phase=0 if side > 0 else 1.9, amp=0.15)
        pts = bezier(V(side * 0.17, 0.0, 1.03), V(side * 0.55, -0.05, 1.05), V(side * 0.62, -0.05, 0.35),
                     V(side * 0.5, -0.1, 0.06), 18)
        for i, q in enumerate(pts):
            tp.ell(q, 0.036 - 0.008 * i / 18, PK2, 8, 5)
        claw(tp, pts[-1], (side * -0.4, -0.3, -0.6), 0.14, 0.022, CLAW, curl=(-side, 0, 0))
        tents.append(tp)
    return dict(height=2.0, parts=[body, *arms, *legs, tail, *tents], mount=mount)


BUILDERS = {
    'neutrophil': build_neutrophil,
    'macrophage': build_macrophage,
    'b_cell': build_b_cell,
    'killer_t': build_killer_t,
    'pneumococcus': build_pneumococcus,
    'staphylococcus': build_staphylococcus,
    'pseudomonas': build_pseudomonas,
    'streptococcus': build_streptococcus,
    'red_blood_cell': build_red_blood_cell,
    'platelet': build_platelet,
}


# ---------------------------------------------------------------------------------------
# Exportação e metadados
# ---------------------------------------------------------------------------------------

def material():
    mat = bpy.data.materials.get('cel_vertex')
    if mat is None:
        mat = bpy.data.materials.new('cel_vertex')
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        bsdf = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')
        attr = nodes.new('ShaderNodeVertexColor')
        attr.layer_name = 'Color'
        mat.node_tree.links.new(attr.outputs[0], bsdf.inputs[0])
        bsdf.inputs['Roughness'].default_value = 1.0
    return mat


def make_object(key, part, collection):
    me = bpy.data.meshes.new(f'{key}.{part.name}')
    me.from_pydata([tuple(v) for v in part.verts], [], part.faces)
    me.polygons.foreach_set('use_smooth', part.fsmooth)
    attr = me.color_attributes.new('Color', 'BYTE_COLOR', 'CORNER')
    cols = []
    for poly, col in zip(me.polygons, part.fcol):
        c = (col[0] / 255, col[1] / 255, col[2] / 255, 1.0)
        cols.extend(c * poly.loop_total)
    attr.data.foreach_set('color_srgb', cols)
    me.color_attributes.active_color = attr
    me.color_attributes.render_color_index = me.color_attributes.active_color_index
    me.validate(clean_customdata=False)
    me.update()
    ob = bpy.data.objects.new(f'{key}.{part.name}', me)
    collection.objects.link(ob)
    ob.data.materials.append(material())
    return ob


def read_glb(path):
    data = Path(path).read_bytes()
    _, _, length = struct.unpack_from('<III', data, 0)
    off, js, binc = 12, None, b''
    while off < length:
        clen, ctype = struct.unpack_from('<II', data, off)
        off += 8
        chunk = data[off:off + clen]
        off += clen
        if ctype == 0x4E4F534A:
            js = json.loads(chunk)
        elif ctype == 0x004E4942:
            binc = chunk
    return js, binc


def raylib_mesh_indices(gltf):
    """Reproduz LoadGLTF do raylib: nós em ordem, pula nós sem malha, um Mesh por primitivo
    de triângulos."""
    out, idx = {}, 0
    for node in gltf.get('nodes', []):
        if 'mesh' not in node:
            continue
        ids = []
        for prim in gltf['meshes'][node['mesh']]['primitives']:
            if prim.get('mode', 4) != 4:
                continue
            ids.append(idx)
            idx += 1
        out[node.get('name', '')] = ids
    return out, idx


def to_gltf(v):
    """Blender (Z para cima, frente -Y) -> glTF (Y para cima, frente +Z)."""
    return [round(v.x, 4), round(v.z, 4), round(-v.y, 4)]


def build(key):
    spec = BUILDERS[key]()
    parts = spec['parts']
    # Pés exatamente em z=0 (o menor vértice de qualquer parte).
    minz = min(v.z for p in parts for v in p.verts)
    for p in parts:
        for v in p.verts:
            v.z -= minz
        p.pivot = p.pivot - V(0, 0, minz)
    mount = spec.get('mount')
    coll = bpy.data.collections.new(key)
    bpy.context.scene.collection.children.link(coll)
    objs = [make_object(key, p, coll) for p in parts]
    OUT.mkdir(parents=True, exist_ok=True)
    glb = OUT / f'{key}.glb'
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format='GLB', use_selection=True,
                              export_vertex_color='ACTIVE', export_all_vertex_colors=False,
                              export_yup=True, export_apply=True, export_texcoords=False, export_normals=True,
                              export_tangents=False, export_materials='EXPORT', export_animations=False,
                              export_skins=False, export_morph=False, export_cameras=False, export_lights=False,
                              export_extras=False, export_image_format='NONE')
    gltf, _ = read_glb(glb)
    mapping, count = raylib_mesh_indices(gltf)
    tris = 0
    for m in gltf['meshes']:
        for prim in m['primitives']:
            tris += gltf['accessors'][prim['indices']]['count'] // 3
    meta = {'key': key, 'height': spec['height'], 'convention': CONVENTION, 'mesh_count': count,
            'triangles': tris, 'parts': []}
    for p in parts:
        ids = mapping[f'{key}.{p.name}']
        assert len(ids) == 1, (key, p.name, ids)
        entry = {'name': p.name, 'mesh': ids[0], 'pivot': to_gltf(p.pivot), 'parent': p.parent, 'swing': p.swing}
        if p.swing != 'static':
            entry['phase'] = round(p.phase, 4)
        if p.amp is not None:
            entry['amp'] = p.amp
        if p.action:
            entry['action'] = p.action
        meta['parts'].append(entry)
    if mount:
        # Arma (scripts/build_weapons.py) na mão: origem do espaço da arma no centro da mão e
        # cano para a frente do personagem; matriz 3x4 arma -> personagem (glTF).
        x, y, z = to_gltf(V(mount['pos']) - V(0, 0, minz))
        meta['mount'] = {'part': mount['part'], 'matrix': [[1.0, 0.0, 0.0, x], [0.0, 1.0, 0.0, y],
                                                           [0.0, 0.0, 1.0, z]]}
    (OUT / f'{key}.json').write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding='utf-8')
    top = max(v.z for p in parts for v in p.verts)
    per = {p.name: sum(len(f) - 2 for f in p.faces) for p in parts}
    print('   ', per)
    print(f'{key:15s} tris={tris:5d} meshes={count} top={top:.2f} flips={ORIENT_FLIPS[0]} '
          f'parts={[p.name for p in parts]}', flush=True)
    ORIENT_FLIPS[0] = 0
    return objs


# ---------------------------------------------------------------------------------------
# Prévias (Workbench) para conferência visual
# ---------------------------------------------------------------------------------------

def render_previews(groups, name, yaw_deg, spacing=1.6, res_y=900):
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    sh = scene.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'VERTEX'
    sh.show_object_outline = True
    sh.object_outline_color = (0.08, 0.08, 0.1)
    sh.show_cavity = False
    sh.show_shadows = False
    scene.view_settings.view_transform = 'Standard'
    scene.render.film_transparent = False
    scene.world = scene.world or bpy.data.worlds.new('w')
    n = len(groups)
    width = n * spacing
    scene.render.resolution_x, scene.render.resolution_y = int(res_y * width / 2.4), res_y
    shown = {o for objs in groups for o in objs}
    for o in scene.objects:
        if o.type == 'MESH':
            o.hide_render = o not in shown
    empties = []
    n = len(groups)
    for i, objs in enumerate(groups):
        e = bpy.data.objects.new(f'pv{i}', None)
        scene.collection.objects.link(e)
        e.location = ((i - (n - 1) / 2) * spacing, 0, 0)
        e.rotation_euler = (0, 0, math.radians(yaw_deg))
        for o in objs:
            o.parent = e
        empties.append(e)
    cam_data = bpy.data.cameras.new('cam')
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = max(width, 2.4)
    cam = bpy.data.objects.new('cam', cam_data)
    scene.collection.objects.link(cam)
    cam.location = (0, -12, 1.05)
    cam.rotation_euler = (math.radians(90), 0, 0)
    scene.camera = cam
    PREVIEW.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(PREVIEW / f'{name}.png')
    bpy.ops.render.render(write_still=True)
    for objs in groups:
        for o in objs:
            o.parent = None
    for e in empties:
        bpy.data.objects.remove(e)
    bpy.data.objects.remove(cam)


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    keys = list(BUILDERS)
    preview = True
    if '--only' in argv:
        keys = argv[argv.index('--only') + 1].split(',')
    if '--no-preview' in argv:
        preview = False
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    groups = {k: build(k) for k in keys}
    if preview:
        for start in range(0, len(keys), 5):
            chunk = keys[start:start + 5]
            sel = [groups[k] for k in chunk]
            tag = '_'.join(k.split('_')[0][:6] for k in chunk)
            for view, yaw in (('front', 0), ('34', -35), ('back', 180)):
                render_previews(sel, f'blender_{tag}_{view}', yaw)


if __name__ == '__main__':
    main()
