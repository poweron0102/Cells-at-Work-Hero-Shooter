"""Braços de primeira pessoa com esqueleto (``Assets/Weapons/<herói>_arms.glb``, gerados por
``referencias/scripts/personagens/build_fp_arms.py``).

A pose é calculada aqui a cada quadro, no espaço do viewmodel (câmera na origem olhando +Z):

* cada mão vai para uma empunhadura (``Grip``): um cilindro elíptico preso à arma ou a uma peça
  animada (bomba, carregador, ferrolho). A palma encosta no cilindro e cada dedo fecha, falange por
  falange, até tocá-lo — a mão segura o cabo, o guarda-mão, o cartucho;
* um IK de dois ossos liga ombro, cotovelo e punho. O ombro fica fora da tela e desliza em
  direção à mão quando ela está longe demais, então a mão nunca se solta da arma;
* recarga é uma trilha de chaves por mão (empunhadura + ajustes, no tempo): a mão viaja de uma para
  outra em arco, abrindo os dedos no caminho e fechando ao chegar.

Empunhaduras, trilhas, inclinação da arma e curvas das peças ficam em
``Assets/Weapons/<herói>_fp_anim.json`` (editor visual: ``scripts/editor_fp``). O jogo relê o
arquivo quando ele muda, então dá para ajustar com o jogo aberto.

Tudo em Python puro, exceto o carregamento do GLB e o envio da pose ao raylib (skinning na CPU do
próprio raylib). O resolvedor dos dedos roda uma vez por empunhadura e fica em cache.
"""
import json
import math
import time
from pathlib import Path

ASSET_DIR = Path(__file__).resolve().parents[2] / 'Assets' / 'Weapons'
FINGERS = ('index', 'middle', 'ring', 'pinky')
RELAXED = {'index': (.22, .3, .18), 'middle': (.3, .38, .2), 'ring': (.38, .45, .22), 'pinky': (.46, .5, .24),
           'thumb': (.35, .12, .2, .12)}


# --------------------------------------------------------------------------------------
# Vetores (tuplas) e rotações 3x3 (linhas)
# --------------------------------------------------------------------------------------

def add(a, b):
    return a[0] + b[0], a[1] + b[1], a[2] + b[2]


def sub(a, b):
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def mul(a, k):
    return a[0] * k, a[1] * k, a[2] * k


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]


def length(a):
    return math.sqrt(dot(a, a))


def norm(a):
    n = length(a)
    return (a[0] / n, a[1] / n, a[2] / n) if n > 1e-12 else (0.0, 0.0, 0.0)


def lerp(a, b, t):
    return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t


def ortho(v, d):
    """Componente de v perpendicular a d (unitário), normalizada."""
    return norm(sub(v, mul(d, dot(v, d))))


def cols(a, b, c):
    return (a[0], b[0], c[0]), (a[1], b[1], c[1]), (a[2], b[2], c[2])


def mm(a, b):
    return tuple(tuple(a[i][0] * b[0][j] + a[i][1] * b[1][j] + a[i][2] * b[2][j] for j in range(3)) for i in range(3))


def mv(m, v):
    return (m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
            m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
            m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2])


def tr(m):
    return (m[0][0], m[1][0], m[2][0]), (m[0][1], m[1][1], m[2][1]), (m[0][2], m[1][2], m[2][2])


I3 = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def axis_angle(axis, ang):
    x, y, z = axis
    c, s = math.cos(ang), math.sin(ang)
    k = 1 - c
    return ((c + x * x * k, x * y * k - z * s, x * z * k + y * s),
            (y * x * k + z * s, c + y * y * k, y * z * k - x * s),
            (z * x * k - y * s, z * y * k + x * s, c + z * z * k))


def frame(d, ref):
    """Base ortonormal (d, ref ⟂ d, d x ref) como colunas."""
    r = ortho(ref, d)
    return cols(d, r, cross(d, r))


def quat(m):
    """Matriz de rotação -> quaternion (x, y, z, w)."""
    t = m[0][0] + m[1][1] + m[2][2]
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        return (m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s, .25 * s
    if m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2
        return .25 * s, (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s, (m[2][1] - m[1][2]) / s
    if m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2
        return (m[0][1] + m[1][0]) / s, .25 * s, (m[1][2] + m[2][1]) / s, (m[0][2] - m[2][0]) / s
    s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2
    return (m[0][2] + m[2][0]) / s, (m[1][2] + m[2][1]) / s, .25 * s, (m[1][0] - m[0][1]) / s


def qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz)


def qmat(q):
    x, y, z, w = q
    return ((1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
            (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
            (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)))


def slerp(a, b, t):
    d = sum(i * j for i, j in zip(a, b))
    if d < 0:
        b, d = tuple(-i for i in b), -d
    if d > .9995:
        q = tuple(i + (j - i) * t for i, j in zip(a, b))
    else:
        th = math.acos(d)
        s0, s1 = math.sin((1 - t) * th) / math.sin(th), math.sin(t * th) / math.sin(th)
        q = tuple(i * s0 + j * s1 for i, j in zip(a, b))
    n = math.sqrt(sum(i * i for i in q))
    return tuple(i / n for i in q)


def smooth(a, b, x):
    if b == a:
        return 1.0 if x >= b else 0.0
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def m_apply(m, p):
    r, t = m
    return add(mv(r, p), t)


def m_dir(m, d):
    return mv(m[0], d)


# --------------------------------------------------------------------------------------
# Empunhaduras
# --------------------------------------------------------------------------------------

class Grip:
    """Cilindro segurado pela mão, no espaço da arma (glTF: +X esquerda, +Y cima, +Z frente) ou da
    peça ``part``. ``axis`` aponta para o lado do polegar; ``palm`` vai do eixo para a palma; ``r`` =
    (raio na direção da palma, raio perpendicular). ``tilt`` (rad) gira a mão sobre o cilindro;
    ``opp`` = oposição do polegar (rad); ``fix`` = ângulos fixos por dedo, no lugar do resolvedor."""
    __slots__ = ('name', 'c', 'axis', 'palm', 'r', 'part', 'tilt', 'opp', 'fix', 'reach')

    def __init__(self, name, c, axis, palm, r, part=None, tilt=0.0, opp=.5, fix=None, reach=None):
        self.name, self.c, self.axis, self.palm = name, tuple(c), norm(axis), norm(palm)
        self.r = (r, r) if isinstance(r, (int, float)) else tuple(r)
        self.part, self.tilt, self.opp, self.fix = part, tilt, opp, fix or {}
        self.reach = reach  # limite de curvatura por dedo (rad), se diferente do padrão


LIMITS = (math.radians(95), math.radians(105), math.radians(80))
THUMB_LIMITS = (math.radians(50), math.radians(70), math.radians(80))

# Pulso (graus), a partir da mão reta, alinhada com o antebraço. X: + = flexão (dedos para o lado da
# palma), - = extensão. Y: + = desvio para o polegar, - = para o mindinho. O antebraço gira (torce) junto
# com a mão, então o pulso não tem eixo Z. Fora disso a mão não chega.
WRIST_X = (-40.0, 50.0)
WRIST_Y = (-40.0, 10.0)


# Pulso automático: segue o IK e satura suave (tanh) nesta fração do limite.
WRIST_AUTO = 1.0


def clamp_wrist(bend):
    x, y = bend[0], bend[1]
    return min(WRIST_X[1], max(WRIST_X[0], x)), min(WRIST_Y[1], max(WRIST_Y[0], y))


# Tela do viewmodel (weapons.VM_FOV = 50° na vertical, 16:9): o pulso automático tira o cotovelo de vista
# (uma esfera de ELBOW_R em volta dele fica fora da tela), se os limites do pulso deixarem.
VIEW_V = math.radians(25.0)
VIEW_H = math.atan(math.tan(VIEW_V) * 16 / 9)
ELBOW_R = .08
_CV, _SV, _CH, _SH = math.cos(VIEW_V), math.sin(VIEW_V), math.cos(VIEW_H), math.sin(VIEW_H)


def offscreen(p):
    """Quanto (m) o ponto p (espaço da vista) passou da borda de baixo ou das laterais da tela: > 0 =
    fora, < 0 = dentro. Por cima não conta: um cotovelo acima da tela é tão errado quanto um visível."""
    x, y, z = p
    return min(max(-(y * _CV + z * _SV), -(x * _CH + z * _SH), x * _CH - z * _SH), z * _SV - y * _CV)


def soft_wrist(bend, k=WRIST_AUTO):
    """Satura (tanh) cada ângulo em k vezes o limite do seu lado: perto de 0 quase não muda."""
    def f(v, lo, hi):
        lim = (hi if v >= 0 else -lo) * k
        return lim * math.tanh(v / lim) if lim > 0 else 0.0
    return f(bend[0], *WRIST_X), f(bend[1], *WRIST_Y)


class HandRig:
    """Dados de repouso de um braço (lado 'R' ou 'L') e o resolvedor da mão. Python puro."""

    def __init__(self, meta, side):
        rest, h = meta['rest'], meta['hands'][side]
        self.side = side
        b = lambda name: f'{name}.{side}'  # noqa: E731
        self.upper, self.fore, self.hand = b('upperarm'), b('forearm'), b('hand')
        self.S, self.E, self.W = (tuple(rest[x][0]) for x in (self.upper, self.fore, self.hand))
        self.L1, self.L2 = length(sub(self.E, self.S)), length(sub(self.W, self.E))
        self.f, self.n, self.s = (norm(h[k]) for k in ('forward', 'normal', 'thumb'))
        self.palm = tuple(h['palm'])
        self.rest = cols(self.f, self.n, self.s)
        self.right_handed = dot(cross(self.f, self.n), self.s) > 0
        self.arm_rest = frame(self.f, self.n)
        self.chains = {}
        for name in FINGERS + ('thumb',):
            bones = [b(f'{name}{i}') for i in (1, 2, 3)]
            joints = [tuple(rest[x][0]) for x in bones] + [tuple(rest[bones[2]][1])]
            radius = [meta['radius'][x] for x in bones]
            d = norm(sub(joints[1], joints[0]))
            self.chains[name] = (bones, joints, radius, norm(cross(d, self.n)))
        self.opp_axis = norm(cross(self.s, self.n))
        # Y do pulso em graus anatômicos: + = lado do polegar nas duas mãos (o eixo X do repouso aponta
        # para o polegar na direita e para o mindinho na esquerda).
        self.ysign = 1.0 if self.s[0] > 0 else -1.0
        self._cache = {}

    # -- dedos ------------------------------------------------------------------------------
    def deltas(self, name, angles):
        """Rotações (no espaço de repouso) de cada falange para os ângulos dados."""
        _bones, joints, _r, axis = self.chains[name]
        if name == 'thumb':
            opp, a1, a2, a3 = angles
            o = axis_angle(self.opp_axis, opp)
            ax = mv(o, axis)
            acc, out = 0.0, []
            for a in (a1, a2, a3):
                acc += a
                out.append(mm(axis_angle(ax, acc), o))
            return out
        acc, out = 0.0, []
        for a in angles:
            acc += a
            out.append(axis_angle(axis, acc))
        return out

    def points(self, name, deltas, origin=None, rot=I3):
        """Juntas da cadeia: no repouso (origin None) ou posicionadas com punho ``origin`` e mão ``rot``."""
        _bones, joints, _r, _a = self.chains[name]
        p = joints[0] if origin is None else add(origin, mv(rot, sub(joints[0], self.W)))
        pts = [p]
        for k in range(3):
            seg = mv(deltas[k], sub(joints[k + 1], joints[k]))
            p = add(p, seg if origin is None else mv(rot, seg))
            pts.append(p)
        return pts

    def solve(self, grip):
        """Ângulos de cada dedo para fechar sobre o cilindro da empunhadura (em cache)."""
        key = (grip.r, grip.tilt, grip.opp, tuple(sorted(grip.fix.items())), grip.reach)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        rp, rw = grip.r
        u = mv(axis_angle(self.n, -grip.tilt), self.s)  # place() gira a mão +tilt sobre o eixo
        center = add(self.palm, mul(self.n, rp))
        v1, v2 = mul(self.n, -1.0), cross(u, mul(self.n, -1.0))

        def inside(q, r):
            w = sub(q, center)
            a, b = dot(w, v1) / (rp + r * .92), dot(w, v2) / (rw + r * .92)
            return math.sqrt(a * a + b * b)

        out = {}
        for name in FINGERS + ('thumb',):
            if name in grip.fix:
                out[name] = tuple(grip.fix[name])
                continue
            _bones, _joints, radius, _a = self.chains[name]
            thumb = name == 'thumb'
            angles = [grip.opp] if thumb else []
            limits = THUMB_LIMITS if thumb else (grip.reach or LIMITS)
            for k in range(3):
                def end(a, k=k):
                    trial = angles + [a] + [0.0] * (2 - k)
                    return self.points(name, self.deltas(name, tuple(trial)))[k + 1]
                if inside(end(0.0), radius[k]) <= 1.0:
                    angles.append(0.0)
                    continue
                step, x, best, found = math.radians(3), 0.0, (9e9, limits[k]), None
                while x < limits[k]:
                    x = min(limits[k], x + step)
                    val = inside(end(x), radius[k])
                    if val < best[0]:
                        best = (val, x)
                    if val <= 1.0:
                        lo, hi = x - step, x
                        for _ in range(7):
                            mid = (lo + hi) / 2
                            if inside(end(mid), radius[k]) <= 1.0:
                                hi = mid
                            else:
                                lo = mid
                        found = hi
                        break
                angles.append(found if found is not None else best[1])
            out[name] = tuple(angles)
        self._cache[key] = out
        return out

    # -- mão e braço ------------------------------------------------------------------------
    def place(self, grip, space):
        """(punho, rotação da mão) para segurar ``grip``; space = matriz 3x4 arma/peça -> vista."""
        c = m_apply(space, grip.c)
        u = norm(m_dir(space, grip.axis))
        p = ortho(m_dir(space, grip.palm), u)
        n2 = mul(p, -1.0)
        s2 = mv(axis_angle(n2, grip.tilt), u)
        f2 = cross(n2, s2) if self.right_handed else cross(s2, n2)
        rot = mm(cols(f2, n2, s2), tr(self.rest))
        wrist = sub(add(c, mul(p, grip.r[0])), mv(rot, sub(self.palm, self.W)))
        return wrist, rot

    def arm(self, wrist, rot, shoulder, pole):
        """IK de dois ossos: devolve (ombro, cotovelo) com o ombro puxado se a mão estiver longe."""
        d = sub(wrist, shoulder)
        dist = length(d)
        reach = self.L1 + self.L2 - 1e-3
        if dist > reach:
            shoulder = sub(wrist, mul(d, reach / dist))
            d, dist = sub(wrist, shoulder), reach
        dn = mul(d, 1.0 / dist)
        a = (self.L1 ** 2 - self.L2 ** 2 + dist ** 2) / (2 * dist)
        h = math.sqrt(max(0.0, self.L1 ** 2 - a * a))
        elbow = add(shoulder, add(mul(dn, a), mul(ortho(pole, dn), h)))
        return shoulder, elbow

    def wrist_matrix(self, bend):
        """Rotação da mão em relação ao antebraço (eixos do repouso) para o pulso (flexão, desvio) em graus."""
        return euler_xyz((bend[0], bend[1] * self.ysign, 0.0))

    def wrist_angles(self, rot, dfore):
        """(flexão, desvio) em graus, SEM limite, que alinham o antebraço com a direção ``dfore``
        (cotovelo -> punho, espaço da vista) com a mão em ``rot``. Repouso: antebraço em +Z."""
        x, y, z = mv(tr(rot), dfore)
        a = math.degrees(math.asin(max(-1.0, min(1.0, y))))
        b = math.degrees(math.atan2(-x, z))
        return a, b * self.ysign

    def fore_dir(self, rot, bend):
        """Direção do antebraço (cotovelo -> punho, espaço da vista) com a mão em ``rot`` e o pulso ``bend``."""
        a, b = math.radians(bend[0]), math.radians(bend[1] * self.ysign)
        return mv(rot, (-math.cos(a) * math.sin(b), math.sin(a), math.cos(a) * math.cos(b)))

    def auto_wrist(self, wrist, rot, need):
        """Pulso automático: o que o IK pede (``need``), saturando no limite. Se com isso o cotovelo
        aparecer na tela, o pulso mais perto disso, dentro dos limites, que o tira de vista."""
        start = clamp_wrist(soft_wrist(need))

        def cost(b):
            inside = ELBOW_R - offscreen(sub(wrist, mul(self.fore_dir(rot, b), self.L2)))
            return (b[0] - start[0]) ** 2 + (b[1] - start[1]) ** 2 + (5000.0 * inside) ** 2 * (inside > 0)

        best = (cost(start), start)
        if best[0] <= 0.0:
            return start
        (x0, x1), (y0, y1) = WRIST_X, WRIST_Y
        for i in range(10):
            for j in range(6):
                b = (x0 + (x1 - x0) * i / 9, y0 + (y1 - y0) * j / 5)
                c = cost(b)
                if c < best[0]:
                    best = (c, b)
        step = 5.0
        while step > .2:
            c, b = best
            for dx, dy in ((step, 0.0), (-step, 0.0), (0.0, step), (0.0, -step)):
                t = clamp_wrist((b[0] + dx, b[1] + dy))
                ct = cost(t)
                if ct < best[0]:
                    best = (ct, t)
            if best[1] is b:
                step /= 2
        return best[1]

    def ik_wrist(self, wrist, rot, shoulder, pole):
        """Pulso (sem limite) que o IK puro pediria: antebraço do cotovelo do IK até o punho."""
        _S, E = self.arm(wrist, rot, shoulder, pole)
        return self.wrist_angles(rot, norm(sub(wrist, E)))

    def bones(self, wrist, rot, angles, shoulder, pole, bend=None):
        """[(osso, cabeça, rotação delta global)] de todo o braço. A mão manda: o antebraço sai do punho
        na direção dada pelo pulso ``bend`` = (flexão, desvio) em graus, dentro de WRIST_X/WRIST_Y
        (None = automático, ver ``auto_wrist``). O antebraço torce junto com a mão; o ombro, fora da
        tela, acompanha o cotovelo."""
        S, E = self.arm(wrist, rot, shoulder, pole)
        if bend is None:
            bend = self.auto_wrist(wrist, rot, self.wrist_angles(rot, norm(sub(wrist, E))))
        bend = clamp_wrist(bend)
        fore = mm(rot, tr(self.wrist_matrix(bend)))
        E = sub(wrist, mul(mv(fore, (0.0, 0.0, 1.0)), self.L2))
        S = add(E, mul(norm(sub(S, E)), self.L1))
        du = norm(sub(E, S))
        ru = ortho(mv(fore, self.n), du)
        out = [(self.upper, S, mm(frame(du, ru), tr(self.arm_rest))),
               (self.fore, E, fore),
               (self.hand, wrist, rot)]
        for name in FINGERS + ('thumb',):
            deltas = self.deltas(name, angles[name])
            pts = self.points(name, deltas, wrist, rot)
            for k, bone in enumerate(self.chains[name][0]):
                out.append((bone, pts[k], mm(rot, deltas[k])))
        return out


def blend_angles(a, b, t):
    return {k: tuple(x + (y - x) * t for x, y in zip(a[k], b[k])) for k in a}


def load_meta(key):
    path = ASSET_DIR / f'{key}_arms.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


# --------------------------------------------------------------------------------------
# Animação por herói: Assets/Weapons/<herói>_fp_anim.json
# (editada no editor visual: scripts/editor_fp, "Editor Animacao 1a Pessoa.bat")
# --------------------------------------------------------------------------------------

EASES = {
    'smooth': lambda u: u * u * (3 - 2 * u),
    'linear': lambda u: u,
    'in': lambda u: u * u,
    'out': lambda u: 1 - (1 - u) * (1 - u),
    'step': lambda u: 1.0 if u >= 1.0 else 0.0,
}
CURVES = ('tilt', 'bolt', 'mag', 'bump', 'squeeze')
SIDES = ('R', 'L')
ANIM_SUFFIX = '_fp_anim.json'


def anim_path(hero):
    return ASSET_DIR / f'{hero}{ANIM_SUFFIX}'


HEROES = tuple(sorted(p.name[:-len(ANIM_SUFFIX)] for p in ASSET_DIR.glob(f'*{ANIM_SUFFIX}')))


def _num(v, what):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ValueError(f'{what}: esperado um número, veio {v!r}')
    return float(v)


def _vec(v, what, n=3):
    if not isinstance(v, (list, tuple)) or len(v) != n:
        raise ValueError(f'{what}: esperado lista de {n} números, veio {v!r}')
    return tuple(_num(x, what) for x in v)


def _fingers(d, what):
    """{dedo: [graus...]} -> {dedo: (rad...)} (polegar: oposição + 3 falanges)."""
    out = {}
    for name, v in (d or {}).items():
        if name not in FINGERS + ('thumb',):
            raise ValueError(f'{what}: dedo desconhecido {name!r}')
        out[name] = tuple(math.radians(x) for x in _vec(v, f'{what}.{name}', 4 if name == 'thumb' else 3))
    return out


def euler_xyz(deg):
    """Rotação (graus) nos eixos da mão em repouso, mesma ordem do Euler 'XYZ' do three.js."""
    x, y, z = (math.radians(a) for a in deg)
    return mm(mm(axis_angle((1.0, 0.0, 0.0), x), axis_angle((0.0, 1.0, 0.0), y)), axis_angle((0.0, 0.0, 1.0), z))


class Key:
    """Chave da trilha de uma mão: no tempo ``t`` a mão está na empunhadura ``grip``.

    ``arc`` (m, espaço da arma) = desvio no meio do caminho até esta chave; ``offset`` (m, espaço da
    arma) e ``rot`` (graus, eixos da mão em repouso: X lateral, Y costas da mão, Z dedos;
    pivô no punho) ajustam a pose sobre a empunhadura; ``wrist`` = pulso (flexão, desvio) em graus,
    limitado a WRIST_X/WRIST_Y, sem mexer a mão: o antebraço gira em volta do punho (ausente =
    automático); ``fingers`` = ângulos fixos de dedos (graus);
    ``open`` = quanto os dedos relaxam no caminho (padrão .7 se troca de empunhadura); ``ease`` =
    curva do movimento até esta chave (smooth|linear|in|out|step)."""
    __slots__ = ('t', 'grip', 'arc', 'offset', 'rot', 'rot_m', 'wrist', 'fingers', 'open', 'ease')

    def __init__(self, d, grips, what):
        self.t = _num(d.get('t'), f'{what}.t')
        self.grip = d.get('grip')
        if self.grip not in grips:
            raise ValueError(f'{what}: empunhadura {self.grip!r} não existe')
        self.arc = _vec(d['arc'], f'{what}.arc') if d.get('arc') is not None else None
        off = _vec(d['offset'], f'{what}.offset') if d.get('offset') is not None else None
        self.offset = off if off and any(off) else None
        rot = _vec(d['rot'], f'{what}.rot') if d.get('rot') is not None else None
        self.rot = rot if rot and any(rot) else None
        self.rot_m = euler_xyz(self.rot) if self.rot else None
        wr = d.get('wrist')
        if wr is not None:  # [flexão, desvio]; um 3º número (torção, formato antigo) é ignorado
            wr = clamp_wrist(_vec(wr, f'{what}.wrist', 3 if isinstance(wr, (list, tuple)) and len(wr) == 3 else 2))
        self.wrist = wr
        self.fingers = _fingers(d.get('fingers'), f'{what}.fingers')
        self.open = _num(d['open'], f'{what}.open') if d.get('open') is not None else None
        self.ease = d.get('ease') or 'smooth'
        if self.ease not in EASES:
            raise ValueError(f'{what}.ease: use um de {sorted(EASES)}')

    def same_pose(self, o):
        return ((self.grip, self.offset, self.rot, self.wrist, self.fingers)
                == (o.grip, o.offset, o.rot, o.wrist, o.fingers))


def parse_config(data):
    """JSON da animação (dict) -> configuração usada pelo jogo. ValueError com mensagem se inválido."""
    if not isinstance(data, dict):
        raise ValueError('animação: esperado um objeto JSON')
    grips = {}
    for name, g in (data.get('grips') or {}).items():
        w = f'grips.{name}'
        r = g.get('r', .03)
        r = _vec(r, f'{w}.r', 2) if isinstance(r, (list, tuple)) else _num(r, f'{w}.r')
        grips[name] = Grip(name, _vec(g.get('c'), f'{w}.c'), _vec(g.get('axis'), f'{w}.axis'),
                           _vec(g.get('palm'), f'{w}.palm'), r, part=g.get('part') or None,
                           tilt=math.radians(_num(g.get('tilt', 0.0), f'{w}.tilt')),
                           opp=math.radians(_num(g.get('opp', math.degrees(.5)), f'{w}.opp')),
                           fix=_fingers(g.get('fix'), f'{w}.fix'),
                           reach=tuple(math.radians(x) for x in _vec(g['reach'], f'{w}.reach'))
                           if g.get('reach') else None)
        if length(grips[name].axis) < .5 or length(ortho(grips[name].palm, grips[name].axis)) < .5:
            raise ValueError(f'{w}: "axis" e "palm" não podem ser nulos nem paralelos')
    if not grips:
        raise ValueError('animação sem empunhaduras ("grips")')
    tracks = {}
    for side in SIDES:
        raw = (data.get('tracks') or {}).get(side) or []
        keys = sorted((Key(k, grips, f'tracks.{side}[{i}]') for i, k in enumerate(raw)), key=lambda k: k.t)
        if not keys:
            raise ValueError(f'tracks.{side}: a mão precisa de pelo menos uma chave')
        tracks[side] = keys
    curves = {}
    for name in CURVES:
        pts = []
        for i, k in enumerate((data.get('curves') or {}).get(name) or []):
            w = f'curves.{name}[{i}]'
            if not isinstance(k, (list, tuple)) or len(k) not in (2, 3):
                raise ValueError(f'{w}: esperado [tempo, valor] ou [tempo, valor, ease]')
            ease = k[2] if len(k) == 3 else 'smooth'
            if ease not in EASES:
                raise ValueError(f'{w}: ease {ease!r} desconhecido')
            pts.append((_num(k[0], w), _num(k[1], w), ease))
        curves[name] = sorted(pts, key=lambda k: k[0])
    tilt = _vec(data.get('tilt', (0, 0, 0, 0, 0, 0)), 'tilt', 6)
    return dict(
        grips=grips,
        shoulders={s: _vec(data['shoulders'][s], f'shoulders.{s}') for s in SIDES},
        poles={s: _vec(data['poles'][s], f'poles.{s}') for s in SIDES},
        tracks=tracks,
        hold={s: tracks[s][0].grip for s in SIDES},
        shell=tuple(_vec(w, 'shell', 2) for w in data.get('shell') or ()),
        tilt=tuple(math.radians(x) for x in tilt[:3]) + tilt[3:],
        curves=curves,
        duration=_num(data.get('duration', 1.6), 'duration'),
    )


def dump_anim(data):
    """JSON da animação legível: listas curtas e chaves em uma linha, floats com 6 casas."""
    def clean(v):
        if isinstance(v, float):
            v = round(v, 6)
            return 0.0 if v == 0 else v
        if isinstance(v, dict):
            return {k: clean(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [clean(x) for x in v]
        return v

    def fmt(v, ind):
        flat = json.dumps(v, ensure_ascii=False)
        if not isinstance(v, (dict, list)) or len(flat) + ind <= 110:
            return flat
        pad = ' ' * (ind + 2)
        if isinstance(v, dict):
            body = [f'{pad}{json.dumps(k, ensure_ascii=False)}: {fmt(x, ind + 2)}' for k, x in v.items()]
            return '{\n' + ',\n'.join(body) + '\n' + ' ' * ind + '}'
        return '[\n' + ',\n'.join(pad + fmt(x, ind + 2) for x in v) + '\n' + ' ' * ind + ']'

    return fmt(clean(data), 0) + '\n'


def curve(keys, p):
    """Valor de uma curva [(tempo, valor, ease)] no progresso p (constante fora das chaves)."""
    if not keys:
        return 0.0
    if p <= keys[0][0]:
        return keys[0][1]
    for (t0, v0, _e0), (t1, v1, e1) in zip(keys, keys[1:]):
        if p < t1:
            u = (p - t0) / (t1 - t0) if t1 > t0 else 1.0
            return v0 + (v1 - v0) * EASES[e1](max(0.0, min(1.0, u)))
    return keys[-1][1]


def reload_parts(hero, p, cfg=None):
    """Estado das peças durante a recarga (progresso p 0..1): bomba/ferrolho, carregador e o solavanco
    da arma quando algo encaixa (``bump``, em metros)."""
    cfg = cfg or config(hero)
    if cfg is None:
        return {}
    return {name: curve(pts, p) for name, pts in cfg['curves'].items() if name != 'tilt'}


def reload_state(hero, p, cfg=None):
    """Peças da arma na recarga, prontas para ``weapons.part_local``, e o solavanco (m): ``squeeze`` (0..1)
    vira a escala da bolsa (``pulse``) das armas orgânicas."""
    parts = reload_parts(hero, p, cfg)
    bump = parts.pop('bump', 0.0)
    squeeze = parts.pop('squeeze', 0.0)
    if squeeze:
        parts['pulse'] = 1 - .45 * squeeze
    return parts, bump


def reload_offsets(hero, p, cfg=None):
    """Inclinação da arma na recarga: (roll, pitch, yaw [rad], x, y, z [m]) já pesada pela curva 'tilt'."""
    cfg = cfg or config(hero)
    if cfg is None:
        return (0.0,) * 6
    w = curve(cfg['curves']['tilt'], p)
    return tuple(x * w for x in cfg['tilt'])


def held_shell(hero, p, cfg=None):
    """O cartucho está na mão esquerda neste instante da recarga?"""
    cfg = cfg or config(hero)
    spans = cfg['shell'] if cfg else ()
    return p is not None and any(a <= p < b for a, b in spans)


_CONFIG = {}
RELOAD_CHECK = .3  # s entre verificações do arquivo (o jogo relê a animação salva pelo editor)


def config(hero):
    """Animação do herói (None se não houver). Relida automaticamente quando o arquivo muda."""
    now = time.monotonic()
    hit = _CONFIG.get(hero)
    if hit is not None and now - hit[2] < RELOAD_CHECK:
        return hit[1]
    path = anim_path(hero)
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        mtime = None
    if hit is not None and hit[0] == mtime:
        _CONFIG[hero] = (mtime, hit[1], now)
        return hit[1]
    cfg = None
    if mtime is not None:
        try:
            cfg = parse_config(json.loads(path.read_text(encoding='utf-8')))
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            print(f'[fp_arms] {path.name} inválido, mantendo a versão anterior: {exc}', flush=True)
            cfg = hit[1] if hit is not None else None
    _CONFIG[hero] = (mtime, cfg, now)
    return cfg


def track(keys, p):
    """Na trilha de uma mão: (chave de saída, chave de chegada, progresso 0..1 já com a curva)."""
    if p is None or p <= keys[0].t:
        return keys[0], keys[0], 1.0
    for a, b in zip(keys, keys[1:]):
        if p < b.t:
            u = (p - a.t) / (b.t - a.t) if b.t > a.t else 1.0
            return a, b, EASES[b.ease](max(0.0, min(1.0, u)))
    return keys[-1], keys[-1], 1.0


def key_pose(rig, grips, key, space):
    """(punho, rotação da mão, ângulos dos dedos) da mão parada na chave ``key``."""
    g = grips[key.grip]
    wrist, rot = rig.place(g, space(g.part))
    if key.rot_m is not None:
        rot = mm(rot, key.rot_m)
    if key.offset is not None:
        wrist = add(wrist, m_dir(space(None), key.offset))
    angles = rig.solve(g)
    if key.fingers:
        angles = dict(angles)
        angles.update(key.fingers)
    return wrist, rot, angles


# --------------------------------------------------------------------------------------
# GPU (raylib)
# --------------------------------------------------------------------------------------

class ArmsAsset:
    """Modelo com esqueleto + uma animação de um quadro reescrita a cada pose."""

    def __init__(self, key):
        import pyray as rl
        import raylib as raw
        ffi = raw.ffi
        meta = load_meta(key)
        if meta is None:
            raise OSError(f'sem braços para {key}')
        self.rl, self.key = rl, key
        self.model = rl.load_model(str(ASSET_DIR / f'{key}_arms.glb'))
        sk = self.model.skeleton
        names = [ffi.string(sk.bones[i].name).decode() for i in range(sk.boneCount)]
        if sorted(names) != sorted(meta['bones']) or self.model.meshCount != meta['mesh_count']:
            rl.unload_model(self.model)
            raise ValueError(f'braços {key}: esqueleto/malhas diferentes do JSON')
        self.index = {n: i for i, n in enumerate(names)}
        self.bind = [(sk.bindPose[i].rotation.x, sk.bindPose[i].rotation.y, sk.bindPose[i].rotation.z,
                      sk.bindPose[i].rotation.w) for i in range(sk.boneCount)]
        self.poses = ffi.new('Transform[]', sk.boneCount)
        for i in range(sk.boneCount):
            self.poses[i] = sk.bindPose[i]
        self.frames = ffi.new('Transform *[1]', [self.poses])
        self.anim = ffi.new('ModelAnimation *')
        self.anim.boneCount, self.anim.keyframeCount, self.anim.keyframePoses = sk.boneCount, 1, self.frames
        self.material = rl.load_material_default()
        self.identity = ffi.new('Matrix *', (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0,
                                             0.0, 0.0, 0.0, 1.0))
        self.hands = {s: HandRig(meta, s) for s in ('R', 'L')}
        self.draw_mesh = raw.DrawMesh

    def set_pose(self, bones):
        poses, index, bind = self.poses, self.index, self.bind
        for name, head, rot in bones:
            i = index[name]
            p = poses[i]
            p.translation.x, p.translation.y, p.translation.z = head
            q = qmul(quat(rot), bind[i])
            p.rotation.x, p.rotation.y, p.rotation.z, p.rotation.w = q
        self.rl.update_model_animation(self.model, self.anim[0], 0)

    def draw(self, shader):
        material = self.material
        material.shader = shader
        c = material.maps[0].color
        c.r = c.g = c.b = c.a = 255
        for i in range(self.model.meshCount):
            self.draw_mesh(self.model.meshes[i], material, self.identity[0])

    def unload(self):
        rl = self.rl
        self.material.shader = rl.Shader(rl.rl_get_shader_id_default(), rl.rl_get_shader_locs_default())
        rl.unload_material(self.material)
        rl.unload_model(self.model)


_ASSETS = {}


def asset(key):
    """Braços do herói (carregados no primeiro uso; precisa de contexto OpenGL). None se não houver."""
    a = _ASSETS.get(key, False)
    if a is False:
        a = None
        if key in HEROES and config(key) is not None and (ASSET_DIR / f'{key}_arms.glb').exists():
            try:
                a = ArmsAsset(key)
            except (OSError, KeyError, ValueError) as exc:
                print(f'[fp_arms] não foi possível carregar {key}: {exc}', flush=True)
        _ASSETS[key] = a
    return a


def release_assets():
    for a in _ASSETS.values():
        if a is not None:
            a.unload()
    _ASSETS.clear()


class Arms:
    """Pose dos dois braços para um quadro, dada a função ``space(part)`` (matriz peça -> vista).
    ``cfg`` fixa uma configuração (editor); sem ela, usa a do arquivo (relida quando muda)."""

    def __init__(self, hero, cfg=None):
        self.hero, self._cfg = hero, cfg
        self.shell = None  # (base, eixo) do cartucho na mão, no espaço da vista
        self.wrist = {}  # último quadro, por mão: (pulso usado, pulso que o IK pedia), (flexão, desvio) em graus

    @property
    def cfg(self):
        return self._cfg or config(self.hero)

    def pose(self, hands, space, reload_p=None):
        """Lista de (osso, cabeça, rotação) para os dois braços. ``reload_p`` = progresso da recarga
        (None = parado: cada mão na primeira chave da sua trilha)."""
        cfg = self.cfg
        grips = cfg['grips']
        out = []
        self.shell = None
        self.wrist = {}
        for side, rig in hands.items():
            a, b, k = track(cfg['tracks'][side], reload_p)
            wrist, rot, angles = key_pose(rig, grips, b, space)
            moving = a is not b and not a.same_pose(b)
            if moving:
                wa, ra, fa = key_pose(rig, grips, a, space)
                wrist = lerp(wa, wrist, k)
                if b.arc is not None:
                    wrist = add(wrist, mul(m_dir(space(None), b.arc), math.sin(math.pi * k)))
                rot = qmat(slerp(quat(ra), quat(rot), k))
                angles = blend_angles(fa, angles, k)
                relax = b.open if b.open is not None else (.7 if a.grip != b.grip else 0.0)
                if relax:
                    angles = blend_angles(angles, RELAXED, relax * math.sin(math.pi * k))
            if side == 'L' and held_shell(self.hero, reload_p, cfg):
                ga, gb = grips[a.grip], grips[b.grip]
                r = ga.r[0] + (gb.r[0] - ga.r[0]) * k
                center = add(add(wrist, mv(rot, sub(rig.palm, rig.W))), mul(mv(rot, rig.n), r))
                axis = mv(rot, rig.s)
                self.shell = (sub(center, mul(axis, .032)), axis)
            shoulder, pole = cfg['shoulders'][side], cfg['poles'][side]
            # Pulso: o da chave, ou automático (segue o IK até o limite, tirando o cotovelo da tela). No
            # caminho entre duas chaves, mistura o da saída e o da chegada (o automático é o deste quadro).
            need = rig.ik_wrist(wrist, rot, shoulder, pole)
            auto = rig.auto_wrist(wrist, rot, need) if a.wrist is None or b.wrist is None else None
            wa_, wb_ = ((e.wrist if e.wrist is not None else auto) for e in (a, b))
            bend = tuple(x + (y - x) * k for x, y in zip(wa_, wb_)) if moving else wb_
            self.wrist[side] = (bend, need)
            out += rig.bones(wrist, rot, angles, shoulder, pole, bend)
        return out
