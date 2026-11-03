"""Gera as armas dos oito heróis no Blender (modo headless) e exporta GLB + JSON.

Uso (a partir da raiz do repositório):

    & 'C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe' --background --factory-startup `
        --python scripts\\build_weapons.py -- [--only neutrophil,b_cell] [--no-preview]

Mesma linguagem visual dos personagens (scripts/build_characters.py, de onde vêm os geradores
de geometria): primitivas procedurais, Bevel/Subsurf do Blender aplicados, cor por face e uma
malha por parte animável.

Espaços (no Blender: Z para cima, frente em -Y, esquerda em +X; no GLB: Y para cima, frente +Z):

* ``gun``  — origem no centro da mão direita sobre o cabo; o cano aponta para a frente. É o espaço
  das peças da arma, desenhadas tanto em primeira pessoa quanto na mão do personagem (3ª pessoa).
* ``view`` — câmera do viewmodel na origem olhando para a frente (só primeira pessoa). Usado pelo
  braço de golpe (faca/garra), que gira em torno do cotovelo.

O JSON registra a pose de repouso em primeira pessoa (``fp``: matriz gun->view), o cano
(``muzzle``), a janela de ejeção (``eject``) e, por parte, a animação (``anim``) com pivô/eixo.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_characters as bc  # noqa: E402  (geradores de geometria compartilhados)
from build_characters import V, xform, tube, slab, lathe, ellipsoid, modifiers, claw  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'Assets' / 'Weapons'
PREVIEW = ROOT / '.scratch' / 'weapons'
TAU = math.tau
CONVENTION = ('glTF/raylib: Y para cima, cano para +Z, esquerda da arma em +X. Espaço "gun": origem na mão '
              'direita sobre o cabo. Espaço "view": câmera do viewmodel na origem olhando +Z. "fp" = matriz '
              '3x4 gun->view da pose de repouso. "anim": static|bolt|mag|pulse|spin|melee. "pivot"/"axis" no '
              'espaço da parte; "amount" em metros (bolt/mag), escala (pulse) ou radianos (spin).')
BORE = 0.095
INKC = '#141518'


def P(x, f, z):
    """(lateral +esquerda, frente, cima) -> Blender."""
    return V(x, -f, z)


SIDE = Matrix(((0, 0, 1), (-1, 0, 0), (0, 1, 0)))


class WPart(bc.Part):
    def __init__(self, name, anim='static', pivot=(0, 0, 0), axis=(0, 1, 0), amount=0.0, fp_only=False,
                 space='gun'):
        super().__init__(name)
        self.anim, self.pivot, self.axis, self.amount = anim, V(pivot), V(axis), amount
        self.fp_only, self.space = fp_only, space
        self.tip = None  # ponta da lâmina/garra (rastro do golpe)

    # --- atalhos no espaço da arma (x, f, z) -------------------------------------------
    def profile(self, outline, width, color, x=0.0, bevel=0.004, smooth=False, roll=0.0, roll_z=BORE):
        """Silhueta lateral [(frente, cima)] extrudada na largura (eixo X). roll (graus) gira a peça em
        torno do eixo do cano (altura roll_z), positivo inclinando a face para a esquerda/câmera."""
        geo = slab(outline, width)
        if bevel:
            geo = modifiers(geo, [('BEVEL', {'width': bevel, 'segments': 2})])
        m = SIDE.to_4x4()
        m.translation = V(x, 0, 0)
        if roll:
            m = (Matrix.Translation(V(0, 0, roll_z)) @ Matrix.Rotation(math.radians(-roll), 4, 'Y')
                 @ Matrix.Translation(V(0, 0, -roll_z)) @ m)
        return self.add(geo, color, m, smooth=smooth)

    def cyl(self, f0, f1, r0, color, r1=None, x=0.0, z=BORE, seg=16, caps=('flat', 'flat'), smooth=True):
        return self.tube([P(x, f0, z), P(x, f1, z)], [r0, r0 if r1 is None else r1], color, seg, caps,
                         smooth=smooth, hint=(1, 0, 0))

    def bx(self, x, f, z, sx, sf, sz, color, bevel=0.0, rot=(0, 0, 0)):
        return self.box(P(x, f, z), (sx, sf, sz), color, rot=rot, bevel=bevel)

    def ball(self, x, f, z, r, color, seg=10, rings=7):
        return self.ell(P(x, f, z), r, color, seg, rings)

    def bore(self, f, r, x=0.0, z=BORE):
        """Boca do cano: disco escuro levemente à frente da face."""
        self.cyl(f - 0.004, f + 0.0015, r, INKC, x=x, z=z, seg=12)

    def lathe_fwd(self, profile, color, x=0.0, z=BORE, seg=18, rfunc=None, smooth=True, sx=1.0, sy=1.0):
        """Superfície de revolução em torno do eixo do cano. profile = [(raio, frente)]."""
        geo = lathe(profile, seg, sx, sy, rfunc)
        return self.add(geo, color, xform(P(x, 0, z), (90, 0, 0)), smooth)


# ---------------------------------------------------------------------------------------
# Mãos e braços de primeira pessoa
# ---------------------------------------------------------------------------------------

def _basis(p, w, a):
    m = Matrix((p, w, a)).transposed().to_4x4()
    return m


def grip_hand(part, c, a, p, w, R, color, *, fingers=4, fr=0.0105, spacing=None, wrap=200, thumb=True,
              palm=True, thumb_at=0, thumb_wrap=-150, claws=None, claw_len=0.05):
    """Mão fechada em volta de um cabo: c = centro do cabo na altura da mão, a = eixo do cabo
    (de baixo para cima, sentido do dedo indicador ao mínimo invertido), p = lado da palma,
    w = direção em que os dedos começam a envolver. R = raio do cabo (ou (Rp, Rw))."""
    c, a, p, w = V(c), V(a).normalized(), V(p).normalized(), V(w).normalized()
    Rp, Rw = (R, R) if isinstance(R, (int, float)) else R
    spacing = spacing or fr * 2.15
    tips = []
    for i in range(fingers):
        level = c + a * ((fingers - 1) / 2 - i) * spacing
        r = fr * (1.0 - 0.08 * max(0, i - 1))
        pts = []
        steps = 7
        for k in range(steps + 1):
            th = math.radians(-15 + (wrap + 15) * k / steps)
            pts.append(level + p * math.cos(th) * (Rp + r * .95) + w * math.sin(th) * (Rw + r * .95))
        radii = [r * 1.08] + [r] * (steps - 1) + [r * .85]
        part.tube(pts, radii, color, 8, ('round', 'round'))
        tips.append((pts[-1], (pts[-1] - pts[-2]).normalized()))
    if claws:
        for tip, d in tips:
            claw(part, tip, d, claw_len, fr * .85, claws, curl=-(p), seg=6)
    if palm:
        span = fingers * spacing
        pc = c + p * (Rp + fr * 2.2) - w * (Rw * .35)
        part.add(ellipsoid((fr * 2.0, max(Rw, 0.02) * 1.15 + fr, span * .62), 12, 8), color, _basis_at(pc, p, w, a))
        # Calcanhar da mão (volume que liga ao punho).
        part.ell(pc - w * (Rw * .9 + fr) - a * span * .25, (fr * 2.3, fr * 2.3, fr * 2.6), color, 10, 7)
    if thumb:
        top = c + a * ((fingers - 1) / 2 + .55) * spacing + a * thumb_at
        pts = []
        for k in range(6):
            th = math.radians(-20 + (thumb_wrap + 20) * k / 5)
            pts.append(top + p * math.cos(th) * (Rp + fr) + w * math.sin(th) * (Rw + fr))
        part.tube(pts, [fr * 1.25, fr * 1.15, fr * 1.05, fr * .95, fr * .9, fr * .8], color, 8)
        if claws:
            claw(part, pts[-1], (pts[-1] - pts[-2]).normalized(), claw_len * .7, fr * .8, claws, curl=-(p), seg=6)
    return c + p * (Rp + fr * 2.2) - w * (Rw * .9 + fr * 2.5) - a * fingers * spacing * .25


def _basis_at(c, p, w, a):
    m = _basis(p, w, a)
    m.translation = V(c)
    return m


def forearm(part, wrist, elbow, sleeve, skin=None, cuff=None, r=0.032, sleeve_from=0.0, cuff_col=None):
    """Antebraço do punho até o cotovelo (fora da tela). sleeve_from: fração a partir do punho em
    que começa a manga (0 = manga cobre tudo)."""
    wrist, elbow = V(wrist), V(elbow)
    d = (elbow - wrist).normalized()
    if skin and sleeve_from > 0:
        mid = wrist.lerp(elbow, sleeve_from)
        part.tube([wrist - d * 0.01, mid + d * 0.02], [r * .85, r * 1.15], skin, 12, ('round', 'flat'))
        part.tube([mid, elbow], [r * 1.35, r * 1.5], sleeve, 14, ('flat', 'flat'))
        if cuff:
            part.add(tube([mid - d * 0.012, mid + d * 0.03], [r * 1.48, r * 1.5], 14, ('flat', 'flat')), cuff)
    else:
        part.tube([wrist + d * 0.01, elbow], [r * 1.05, r * 1.4], sleeve, 14, ('round', 'flat'))
        if cuff:
            part.add(tube([wrist + d * 0.012, wrist + d * 0.05], [r * 1.25, r * 1.28], 14, ('flat', 'flat')), cuff)


# ---------------------------------------------------------------------------------------
# Pose de primeira pessoa
# ---------------------------------------------------------------------------------------

def fp_matrix(pos, rot):
    """gun -> view (Blender). pos em (lateral+esq, frente, cima) da câmera; rot em graus (pitch, yaw, roll)."""
    pitch, yaw, roll = [math.radians(a) for a in rot]
    r = (Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(pitch, 4, 'X') @ Matrix.Rotation(roll, 4, 'Y'))
    m = Matrix.Translation(P(*pos)) @ r
    return m


def to_gun(fp, view_point):
    """Ponto no espaço da câmera -> espaço da arma (para levar braços até fora da tela)."""
    return fp.inverted() @ P(*view_point)


# ---------------------------------------------------------------------------------------
# Armas
# ---------------------------------------------------------------------------------------

def human_arms(fp, *, sleeve, hand_col, cuff=None, skin=None, sleeve_from=0.0, r_grip, l_grip,
               r_elbow=(-0.2, -0.12, -0.33), l_elbow=(0.24, -0.06, -0.36), l_under=False, l_R=0.022,
               r_R=(0.019, 0.028), r_axis=(0, 0.22, 1), arm_r_extra=None):
    """Braço direito (no cabo) e esquerdo (guarda-mão), cotovelos fora da tela."""
    arm_r = WPart('arm_r', fp_only=True)
    c = P(*r_grip)
    a = P(*r_axis).normalized()
    wrist = grip_hand(arm_r, c, a, V(-1, 0, 0), P(0, 1, 0), r_R, hand_col, wrap=205)
    forearm(arm_r, wrist, to_gun(fp, r_elbow), sleeve, skin, cuff, r=0.03, sleeve_from=sleeve_from)
    arm_l = WPart('arm_l', 'support', pivot=to_gun(fp, l_elbow), fp_only=True)
    c = P(*l_grip)
    if l_under:
        wrist = grip_hand(arm_l, c, P(0, 1, 0), V(0, 0, -1), V(-1, 0, 0), l_R, hand_col, wrap=170,
                          thumb_wrap=-120)
    else:
        wrist = grip_hand(arm_l, c, V(0, 0, 1), V(1, 0, 0), P(0, 1, 0), l_R, hand_col, wrap=200)
    forearm(arm_l, wrist, to_gun(fp, l_elbow), sleeve, skin, cuff, r=0.03, sleeve_from=sleeve_from)
    return arm_r, arm_l


def knife_arm(sleeve, hand_col, blade, grip_col, cuff=None, skin=None, sleeve_from=0.0, length=0.2):
    """Braço esquerdo com faca, no espaço da câmera (pose no meio do golpe), girando no cotovelo."""
    elbow = P(0.30, 0.02, -0.34)
    hc = P(0.06, 0.34, -0.12)
    part = WPart('melee', 'melee', pivot=elbow, axis=P(0, 1, 0.35).normalized(), fp_only=True, space='view')
    d = (hc - elbow).normalized()
    grip_axis = P(-0.55, 0.35, 0.75).normalized()
    wrist = grip_hand(part, hc, grip_axis, (d.cross(grip_axis)).normalized(), d, 0.016, hand_col, wrap=200)
    forearm(part, wrist, elbow, sleeve, skin, cuff, r=0.03, sleeve_from=sleeve_from)
    g0, g1 = hc - grip_axis * 0.06, hc + grip_axis * 0.05
    part.tube([g0, g1], [0.017, 0.018], grip_col, 10)
    part.add(tube([g1, g1 + grip_axis * 0.012], [(0.042, 0.013), (0.042, 0.013)], 10, ('flat', 'flat'),
                  hint=tuple(d)), '#59616a')
    w = 0.036
    outline = [(-w / 2, 0), (w / 2, 0), (w * .6, length * .6), (0, length), (-w * .55, length * .5)]
    geo = modifiers(slab(outline, 0.008), [('BEVEL', {'width': 0.002, 'segments': 1})])
    y_axis = grip_axis
    z_axis = (d - grip_axis * d.dot(grip_axis)).normalized()  # espessura para longe da câmera: a face aparece
    x_axis = y_axis.cross(z_axis).normalized()
    m = Matrix((x_axis, y_axis, z_axis)).transposed().to_4x4()
    m.translation = g1 + grip_axis * 0.012
    part.add(geo, blade, m, smooth=False)
    part.add(tube([g1 + grip_axis * 0.014, g1 + grip_axis * length * .92], [0.0032, 0.002], 6), '#f2f5f7')
    part.tip = g1 + grip_axis * (0.012 + length)
    return part


def claw_arm(arm_col, band, claw_col, length=0.26):
    """Braço esquerdo de garra longa (golpe do Streptococcus), no espaço da câmera."""
    elbow = P(0.32, 0.0, -0.36)
    wr = P(0.07, 0.3, -0.13)
    part = WPart('melee', 'melee', pivot=elbow, axis=P(0, 1, 0.35).normalized(), fp_only=True, space='view')
    d = (wr - elbow).normalized()
    part.add(tube([elbow, wr], [(0.05, 0.042), (0.034, 0.03)], 10, ('flat', 'round')), arm_col, smooth=False)
    part.add(tube([elbow.lerp(wr, .45), elbow.lerp(wr, .52)], [0.05, 0.05], 12), band)
    part.ell(wr + d * 0.03, (0.04, 0.045, 0.04), arm_col, 10, 7)
    for k in range(3):
        base = wr + d * 0.05 + P((k - 1) * 0.022, 0, 0.006 * k)
        claw(part, base, d + P((k - 1) * 0.15, 0, 0.1), length * (1 - abs(k - 1) * 0.25), 0.017, claw_col,
             curl=P(0, 0, -1), seg=6)
    part.tip = wr + d * (0.05 + length * .9)
    return part


def build_neutrophil():
    """SMG citotóxica: compacta, polímero branco, detalhes grafite e janela vermelha no carregador."""
    W, W2, DK, DK2, RED = '#eef2f4', '#d3dbe0', '#3d444c', '#2a2f35', '#d8505a'
    fp = fp_matrix((-0.145, 0.40, -0.178), (-1.5, 4.0, -3))
    body = WPart('body')
    body.profile([(-0.11, 0.045), (0.17, 0.045), (0.19, 0.07), (0.19, 0.125), (0.15, 0.14), (-0.07, 0.14),
                  (-0.11, 0.12)], 0.05, W, bevel=0.007)
    body.profile([(-0.05, 0.012), (0.125, 0.012), (0.135, 0.046), (-0.06, 0.046)], 0.042, DK)
    body.profile([(-0.03, 0.02), (0.032, 0.02), (0.016, -0.06), (-0.044, -0.072), (-0.052, -0.05)], 0.036, DK,
                 bevel=0.008)
    for k in range(4):
        body.bx(0, -0.012 - k * 0.004, -0.02 - k * 0.012, 0.038, 0.012, 0.004, DK2)
    body.tube([P(0, 0.032, 0.012), P(0, 0.07, -0.006), P(0, 0.098, 0.004), P(0, 0.104, 0.02)],
              [0.0045, 0.005, 0.005, 0.0045], DK, 8)
    body.tube([P(0, 0.048, 0.012), P(0, 0.054, -0.01)], [0.0042, 0.0032], DK2, 6)
    body.bx(0.0, 0.08, 0.087, 0.0515, 0.12, 0.009, RED)
    body.bx(-0.0255, 0.07, 0.112, 0.004, 0.045, 0.017, DK2)
    # Cano com capa ventilada e quebra-chamas.
    body.cyl(0.18, 0.335, 0.025, W)
    for k in range(4):
        body.bx(0, 0.212 + k * 0.03, BORE, 0.053, 0.012, 0.011, DK2, bevel=0.002)
    body.cyl(0.335, 0.375, 0.019, DK)
    body.cyl(0.36, 0.368, 0.021, DK2)
    body.bore(0.375, 0.009)
    # Trilho superior e miras.
    body.bx(0, 0.045, 0.147, 0.022, 0.21, 0.012, DK, bevel=0.002)
    for k in range(9):
        body.bx(0, -0.05 + k * 0.024, 0.155, 0.024, 0.008, 0.005, DK2)
    body.profile([(-0.055, 0.15), (-0.025, 0.15), (-0.025, 0.17), (-0.034, 0.17), (-0.04, 0.163), (-0.046, 0.17),
                  (-0.055, 0.17)], 0.028, DK, bevel=0.0015)
    body.profile([(0.14, 0.15), (0.158, 0.15), (0.152, 0.176), (0.146, 0.176)], 0.008, DK, bevel=0.0)
    body.ball(0, 0.149, 0.178, 0.0045, RED, 8, 5)
    # Coronha rebatida e empunhadura vertical.
    body.profile([(-0.112, 0.05), (-0.112, 0.125), (-0.125, 0.118), (-0.125, 0.06)], 0.044, DK, bevel=0.003)
    body.tube([P(0, 0.255, 0.075), P(0, 0.26, -0.03)], [0.0165, 0.0175], DK, 12, ('flat', 'round'))
    bolt = WPart('bolt', 'bolt', axis=P(0, -1, 0), amount=0.032)
    bolt.bx(0.031, 0.05, 0.122, 0.014, 0.02, 0.012, DK, bevel=0.002)
    bolt.ball(0.042, 0.05, 0.122, 0.0085, DK2, 8, 6)
    mag = WPart('mag', 'mag', axis=P(0, 0.15, -1), amount=0.2)
    mag.profile([(0.104, 0.05), (0.146, 0.05), (0.168, -0.112), (0.124, -0.118)], 0.03, DK2, bevel=0.004)
    mag.profile([(0.117, 0.0), (0.136, 0.0), (0.147, -0.08), (0.128, -0.082)], 0.032, RED, bevel=0.0)
    mag.profile([(0.12, -0.112), (0.172, -0.106), (0.174, -0.124), (0.12, -0.13)], 0.036, DK, bevel=0.003)
    arm_r, arm_l = human_arms(fp, sleeve=W, hand_col='#fafcfc', cuff=W2, r_grip=(0, -0.01, -0.022),
                              l_grip=(0, 0.258, 0.022), l_R=0.017)
    melee = knife_arm(W, '#fafcfc', '#d6dee4', '#3a3f46', cuff=W2)
    return dict(parts=[body, bolt, mag, arm_r, arm_l, melee], fp=fp, muzzle=P(0, 0.38, BORE),
                eject=P(-0.03, 0.07, 0.112), kind='smg')


def build_macrophage():
    """Shotgun/machado híbrido: cano duplo sobre um cutelo enorme, cabo de madeira e anéis de latão."""
    BLADE, EDGE, WOOD, WOOD2, MET, BRASS, SHELL = '#4b5563', '#d5dbe2', '#9a6532', '#7d4f26', '#2a2c30', '#c9a25a', '#b8433f'
    fp = fp_matrix((-0.15, 0.38, -0.19), (-1.0, 4.0, -4))
    body = WPart('body')
    body.tube([P(0, -0.035, -0.075), P(0, -0.01, 0.0), P(0, 0.01, 0.05)], [0.02, 0.019, 0.021], WOOD, 12)
    body.ball(0, -0.04, -0.085, 0.024, MET, 10, 7)
    for f, z in ((-0.03, -0.055), (0.006, 0.035)):
        body.add(tube([P(0, f - 0.006, z - 0.012), P(0, f + 0.006, z + 0.012)], [0.024, 0.024], 12, ('flat', 'flat')),
                 BRASS)
    body.profile([(-0.045, 0.045), (0.13, 0.045), (0.14, 0.06), (0.14, 0.12), (-0.03, 0.12), (-0.045, 0.1)], 0.052, MET,
                 bevel=0.008)
    body.bx(0, 0.05, 0.083, 0.054, 0.15, 0.008, BRASS)
    body.profile([(-0.04, 0.06), (-0.035, 0.115), (-0.2, 0.095), (-0.25, 0.06), (-0.24, 0.02), (-0.2, 0.025)], 0.044,
                 WOOD, bevel=0.008)
    for x in (0.0145, -0.0145):
        body.cyl(0.13, 0.56, 0.0145, MET, x=x)
        body.cyl(0.54, 0.565, 0.017, '#3a3d42', x=x)
        body.bore(0.565, 0.0095, x=x)
    body.bx(0, 0.35, 0.112, 0.012, 0.44, 0.006, '#3a3d42')
    body.ball(0, 0.55, 0.118, 0.0045, BRASS, 8, 5)
    # Cutelo pendurado sob os canos, com fio claro e rebites de latão.
    blade = [(0.3, 0.085), (0.6, 0.085), (0.63, 0.03), (0.6, -0.17), (0.38, -0.15), (0.31, -0.03)]
    tilt = dict(roll=38, roll_z=0.08)
    body.profile(blade, 0.016, BLADE, bevel=0.003, **tilt)
    body.profile([(0.38, -0.14), (0.6, -0.162), (0.603, -0.178), (0.375, -0.156)], 0.0175, EDGE, bevel=0.0, **tilt)
    body.profile([(0.6, -0.162), (0.62, 0.02), (0.633, 0.03), (0.613, -0.172)], 0.0175, EDGE, bevel=0.0, **tilt)
    body.profile([(0.33, 0.0), (0.58, 0.0), (0.575, -0.09), (0.36, -0.08)], 0.018, '#5a6472', bevel=0.002, **tilt)
    for k in range(5):
        for side in (1, -1):
            q = Matrix.Rotation(math.radians(-38), 4, 'Y') @ (P(side * 0.0085, 0.33 + k * 0.06, 0.06 - 0.08))
            body.ell(q + V(0, 0, 0.08), 0.0055, BRASS, 8, 5)
    pump = WPart('pump', 'bolt', axis=P(0, -1, 0), amount=0.06)
    pump.tube([P(0, 0.16, 0.08), P(0, 0.285, 0.08)], [(0.036, 0.027), (0.036, 0.027)], WOOD, 16, ('round', 'round'))
    for k in range(5):
        pump.add(tube([P(0, 0.18 + k * 0.022, 0.08), P(0, 0.186 + k * 0.022, 0.08)], [(0.0375, 0.0285)] * 2, 16,
                      ('flat', 'flat')), WOOD2)
    mag = WPart('mag', 'mag', axis=P(0.4, 0, -1), amount=0.16)
    for k in range(4):
        f = 0.0 + k * 0.026
        mag.tube([P(0.03, f, 0.07), P(0.03, f, 0.115)], [0.0105, 0.0105], SHELL, 10, ('flat', 'flat'))
        mag.tube([P(0.03, f, 0.062), P(0.03, f, 0.074)], [0.011, 0.011], BRASS, 10, ('flat', 'flat'))
    mag.bx(0.028, 0.04, 0.09, 0.006, 0.11, 0.05, MET, bevel=0.002)
    arm_r, arm_l = human_arms(fp, sleeve='#efe2cf', hand_col='#f6dccb', cuff='#fbf7f1', r_grip=(0, -0.012, -0.02),
                              l_grip=(0, 0.222, 0.08), l_under=True, l_R=(0.03, 0.04), r_R=(0.021, 0.022),
                              r_axis=(0, 0.3, 1))
    return dict(parts=[body, pump, mag, arm_r, arm_l], fp=fp, muzzle=P(0, 0.57, BORE), eject=P(-0.03, 0.08, 0.1),
                kind='shotgun')


def build_b_cell():
    """Rifle de anticorpos: corpo branco de laboratório, câmara de vidro com anticorpos em Y e luneta."""
    WH, WH2, DK, BL, GLASS, YCOL = '#e9edf0', '#cfd7de', '#41505e', '#4f8fd6', '#a8d8f8', '#f6f8fa'
    fp = fp_matrix((-0.14, 0.40, -0.17), (-1.5, 3.5, -3))
    body = WPart('body')
    body.profile([(-0.16, 0.05), (0.24, 0.05), (0.26, 0.075), (0.26, 0.12), (0.2, 0.135), (-0.12, 0.135),
                  (-0.16, 0.115)], 0.05, WH, bevel=0.008)
    body.profile([(-0.03, 0.02), (0.035, 0.02), (0.018, -0.062), (-0.044, -0.074), (-0.052, -0.05)], 0.036, DK,
                 bevel=0.008)
    body.profile([(-0.05, 0.012), (0.15, 0.012), (0.16, 0.05), (-0.06, 0.05)], 0.044, DK)
    body.tube([P(0, 0.032, 0.014), P(0, 0.07, -0.004), P(0, 0.1, 0.006), P(0, 0.106, 0.02)], [0.0045] * 4, DK, 8)
    body.tube([P(0, 0.048, 0.014), P(0, 0.054, -0.008)], [0.0042, 0.0032], WH2, 6)
    body.bx(0, 0.1, 0.092, 0.0515, 0.26, 0.012, BL)
    body.profile([(-0.16, 0.06), (-0.16, 0.125), (-0.3, 0.11), (-0.33, 0.04), (-0.3, 0.03), (-0.2, 0.05)], 0.042, WH2,
                 bevel=0.008)
    # Guarda-mão, cano longo e freio de boca.
    body.tube([P(0, 0.24, 0.09), P(0, 0.42, 0.09)], [(0.028, 0.03), (0.026, 0.028)], WH, 16, ('flat', 'flat'))
    for k in range(5):
        body.bx(0, 0.27 + k * 0.03, 0.09, 0.058, 0.01, 0.02, BL, bevel=0.002)
    body.cyl(0.42, 0.6, 0.012, DK, z=0.092)
    body.cyl(0.58, 0.63, 0.019, DK, z=0.092)
    for k in range(2):
        body.bx(0, 0.594 + k * 0.02, 0.092, 0.044, 0.008, 0.012, '#2c3640')
    body.bore(0.63, 0.008, z=0.092)
    # Câmara de anticorpos (vidro azul com "Y" brancos) sobre o receptor.
    CX, CZ = 0.044, 0.1
    body.cyl(0.07, 0.21, 0.022, GLASS, x=CX, z=CZ, seg=18)
    body.cyl(0.058, 0.074, 0.025, DK, x=CX, z=CZ, seg=18)
    body.cyl(0.206, 0.222, 0.025, DK, x=CX, z=CZ, seg=18)
    for k in range(4):
        f = 0.09 + k * 0.032
        q = P(CX + 0.021, f, CZ - 0.01)
        body.tube([q, q + V(0, 0, 0.012), q + V(0, 0.007, 0.021)], [0.003] * 3, YCOL, 5)
        body.tube([q + V(0, 0, 0.012), q + V(0, -0.007, 0.021)], [0.003] * 2, YCOL, 5)
    # Luneta compacta sobre o trilho.
    body.bx(0, 0.06, 0.14, 0.02, 0.2, 0.01, DK)
    body.cyl(-0.04, 0.12, 0.016, DK, z=0.172)
    body.cyl(-0.055, -0.035, 0.02, DK, z=0.172)
    body.cyl(0.115, 0.14, 0.02, DK, z=0.172)
    body.cyl(0.137, 0.142, 0.016, '#7fc4ff', z=0.172)
    body.bx(0, 0.0, 0.153, 0.014, 0.02, 0.02, DK)
    body.bx(0, 0.09, 0.153, 0.014, 0.02, 0.02, DK)
    bolt = WPart('bolt', 'bolt', axis=P(0, -1, 0), amount=0.04)
    bolt.bx(0.031, 0.02, 0.11, 0.016, 0.03, 0.014, DK, bevel=0.002)
    bolt.ball(0.044, 0.02, 0.11, 0.009, BL, 8, 6)
    mag = WPart('mag', 'mag', axis=P(0, 0.1, -1), amount=0.2)
    mag.profile([(0.112, 0.05), (0.152, 0.05), (0.158, -0.09), (0.118, -0.092)], 0.032, DK, bevel=0.004)
    mag.profile([(0.114, -0.02), (0.154, -0.02), (0.156, -0.05), (0.116, -0.05)], 0.034, BL, bevel=0.0)
    arm_r, arm_l = human_arms(fp, sleeve='#7097bf', hand_col='#bfc2c6', cuff='#8fb2d6', skin='#f2d2b6',
                              sleeve_from=0.45, r_grip=(0, -0.012, -0.022), l_grip=(0, 0.33, 0.09), l_under=True,
                              l_R=(0.03, 0.034))
    return dict(parts=[body, bolt, mag, arm_r, arm_l], fp=fp, muzzle=P(0, 0.635, 0.092),
                eject=P(-0.03, 0.06, 0.11), kind='rifle')


def build_killer_t():
    """Fuzil de rajada: preto tático, pesado, freio de boca grande e mira holográfica âmbar."""
    BK, BK2, MET, GOLD, LENS = '#25282c', '#363b41', '#5f6872', '#e6c35c', '#ffb347'
    fp = fp_matrix((-0.165, 0.43, -0.188), (-1.5, 4.5, -3))
    body = WPart('body')
    body.profile([(-0.15, 0.045), (0.22, 0.045), (0.24, 0.07), (0.24, 0.13), (0.2, 0.145), (-0.12, 0.145),
                  (-0.15, 0.125)], 0.056, BK2, bevel=0.008)
    body.profile([(-0.035, 0.02), (0.035, 0.02), (0.02, -0.065), (-0.046, -0.078), (-0.055, -0.052)], 0.038, BK,
                 bevel=0.008)
    body.profile([(-0.05, 0.012), (0.16, 0.012), (0.17, 0.046), (-0.06, 0.046)], 0.046, BK)
    body.tube([P(0, 0.032, 0.014), P(0, 0.07, -0.004), P(0, 0.1, 0.006), P(0, 0.106, 0.02)], [0.005] * 4, BK, 8)
    body.bx(0, 0.06, 0.1, 0.0575, 0.18, 0.006, GOLD)
    body.profile([(-0.15, 0.05), (-0.15, 0.13), (-0.3, 0.12), (-0.33, 0.035), (-0.29, 0.03), (-0.19, 0.06)], 0.048, BK,
                 bevel=0.008)
    # Guarda-mão quadrado com trilhos, cano e freio de boca.
    body.profile([(0.22, 0.05), (0.44, 0.05), (0.45, 0.06), (0.45, 0.13), (0.22, 0.13)], 0.054, BK2, bevel=0.006)
    for k in range(6):
        body.bx(0, 0.25 + k * 0.032, 0.09, 0.058, 0.014, 0.05, BK, bevel=0.002)
    body.cyl(0.45, 0.53, 0.013, MET, z=0.092)
    body.profile([(0.53, 0.07), (0.6, 0.07), (0.6, 0.114), (0.53, 0.114)], 0.04, BK, bevel=0.006)
    for k in range(3):
        body.bx(0, 0.545 + k * 0.018, 0.092, 0.042, 0.007, 0.034, '#101114')
    body.bore(0.6, 0.008, z=0.092)
    # Trilho superior, mira holográfica.
    body.bx(0, 0.15, 0.152, 0.024, 0.58, 0.012, BK, bevel=0.002)
    for k in range(20):
        body.bx(0, -0.12 + k * 0.03, 0.161, 0.026, 0.01, 0.005, BK2)
    body.profile([(-0.02, 0.158), (0.06, 0.158), (0.06, 0.172), (0.05, 0.215), (0.0, 0.215), (-0.02, 0.18)], 0.04, BK,
                 bevel=0.004)
    body.profile([(0.0, 0.17), (0.044, 0.17), (0.038, 0.207), (0.006, 0.207)], 0.032, LENS, bevel=0.0)
    body.ball(0, 0.0, 0.19, 0.0035, '#ff4d2e', 8, 5)
    body.tube([P(0, 0.33, 0.05), P(0, 0.345, -0.02)], [(0.016, 0.022), (0.014, 0.02)], BK, 12, ('flat', 'round'))
    bolt = WPart('bolt', 'bolt', axis=P(0, -1, 0), amount=0.035)
    bolt.bx(-0.034, 0.03, 0.118, 0.016, 0.03, 0.014, MET, bevel=0.002)
    bolt.bx(-0.043, 0.03, 0.118, 0.008, 0.014, 0.02, BK)
    mag = WPart('mag', 'mag', axis=P(0, 0.2, -1), amount=0.22)
    mag.profile([(0.11, 0.05), (0.155, 0.05), (0.185, -0.1), (0.135, -0.108)], 0.034, BK, bevel=0.005)
    for k in range(3):
        mag.profile([(0.115 + k * 0.006, 0.0 - k * 0.03), (0.16 + k * 0.006, 0.0 - k * 0.03),
                     (0.162 + k * 0.006, -0.008 - k * 0.03), (0.117 + k * 0.006, -0.008 - k * 0.03)], 0.036, BK2,
                    bevel=0.0)
    arm_r, arm_l = human_arms(fp, sleeve='#2d3136', hand_col='#e0aa80', cuff='#3b4046', skin='#e0aa80',
                              sleeve_from=0.65, r_grip=(0, -0.012, -0.024), l_grip=(0, 0.338, 0.012), l_R=0.02,
                              r_R=(0.021, 0.03))
    melee = knife_arm('#2d3136', '#e0aa80', '#7c858e', '#15171a', cuff='#3b4046', skin='#e0aa80', sleeve_from=0.65,
                      length=0.25)
    return dict(parts=[body, bolt, mag, arm_r, arm_l, melee], fp=fp, muzzle=P(0, 0.605, 0.092),
                eject=P(-0.032, 0.05, 0.115), kind='burst')


# ---------------------------------- bactérias (armas orgânicas) ---------------------------

def organic_arm(fp, part, wrist, elbow, col, band=None, r=0.042, segments=2):
    forearm(part, wrist, to_gun(fp, elbow) if not isinstance(elbow, Vector) else elbow, col, r=r)
    if band:
        e = to_gun(fp, elbow) if not isinstance(elbow, Vector) else elbow
        for k in range(segments):
            q = V(wrist).lerp(e, 0.25 + 0.3 * k)
            d = (e - V(wrist)).normalized()
            part.add(tube([q - d * 0.012, q + d * 0.012], [r * 1.5, r * 1.55], 14, ('flat', 'flat')), band)


def build_pneumococcus():
    """Canhão de cápsula: casca lavanda em gomos fundida ao antebraço, bexiga pálida e boca brilhante."""
    LAV, DARK, PALE, CLAW, RING, GLOW = '#8b90e8', '#666bc6', '#e9ebf6', '#24242c', '#7277d4', '#f2c6ff'
    fp = fp_matrix((-0.19, 0.5, -0.215), (-1.5, 5.0, -5))
    body = WPart('body')
    prof = [(0.0, -0.07), (0.05, -0.07), (0.062, -0.02), (0.076, 0.06), (0.074, 0.15), (0.06, 0.24), (0.045, 0.3),
            (0.036, 0.33), (0.0, 0.33)]
    body.lathe_fwd(prof, LAV, z=0.03, seg=22, rfunc=lambda i, a: 1 + 0.06 * math.cos(a * 6) * (0 < i < 7))
    for k, f in enumerate((0.0, 0.08, 0.16, 0.24)):
        r = {0: 0.066, 1: 0.079, 2: 0.077, 3: 0.063}[k]
        body.lathe_fwd([(r - 0.004, f - 0.009), (r + 0.006, f - 0.005), (r + 0.006, f + 0.005), (r - 0.004, f + 0.009),
                        (r - 0.004, f - 0.009)], DARK, z=0.03, seg=22)
    # Boca: lábio em anel, garganta escura e núcleo brilhante.
    body.lathe_fwd([(0.03, 0.32), (0.05, 0.325), (0.052, 0.345), (0.04, 0.355), (0.024, 0.35), (0.022, 0.33)], RING,
                   z=0.03, seg=20)
    body.cyl(0.33, 0.352, 0.022, '#2b1d3d', z=0.03, seg=16)
    body.ball(0, 0.338, 0.03, 0.013, GLOW, 10, 7)
    for k in range(6):
        a = TAU * k / 6
        body.cone(P(math.cos(a) * 0.045, 0.34, 0.03 + math.sin(a) * 0.045),
                  P(math.cos(a) * 0.05, 0.37, 0.03 + math.sin(a) * 0.05), 0.007, PALE, 6)
    # Garras saindo por baixo da casca.
    for k in range(3):
        base = P((k - 1) * 0.022, 0.1, -0.035)
        claw(body, base, P((k - 1) * 0.12, 1, -0.25), 0.11, 0.012, CLAW, curl=P(0, 0, -1), seg=6)
    sac = WPart('sac', 'pulse', pivot=P(0, 0.1, 0.12), amount=0.22)
    sac.ell(P(0, 0.1, 0.11), (0.042, 0.075, 0.035), '#e7d6ff', 16, 10)
    sac.ell(P(0, 0.1, 0.122), (0.024, 0.048, 0.02), '#c8a6f2', 12, 8)
    for k in range(3):
        sac.ell(P(0.012 * (k - 1), 0.07 + k * 0.03, 0.141), (0.006, 0.006, 0.004), '#a77fe0', 8, 5)
    arm_r = WPart('arm_r', fp_only=True)
    organic_arm(fp, arm_r, P(0, -0.06, 0.03), (-0.22, -0.12, -0.34), LAV, RING, r=0.04)
    arm_l = WPart('arm_l', 'support', pivot=to_gun(fp, (0.22, -0.08, -0.36)), fp_only=True)
    wrist = grip_hand(arm_l, P(0, 0.14, 0.03), P(0, 1, 0), V(0, 0, -1), V(-1, 0, 0), (0.078, 0.07), LAV,
                      fingers=3, fr=0.013, wrap=120, thumb_wrap=-80, claws=CLAW, claw_len=0.06)
    organic_arm(fp, arm_l, wrist, (0.22, -0.08, -0.36), LAV, RING, r=0.036)
    return dict(parts=[body, sac, arm_r, arm_l], fp=fp, muzzle=P(0, 0.36, 0.03), eject=None, kind='organic')


def build_staphylococcus():
    """Lançador de cachos: tambor de esferas amarelas (gira a cada disparo) sobre um cano orgânico."""
    Y, Y2, Y3, PALE, CLAW = '#e8d84e', '#d2c02a', '#b9a51c', '#f4f1e4', '#24242a'
    fp = fp_matrix((-0.185, 0.48, -0.21), (-1.5, 5.0, -4))
    body = WPart('body')
    body.lathe_fwd([(0.0, -0.07), (0.045, -0.07), (0.05, 0.0), (0.045, 0.1), (0.034, 0.2), (0.03, 0.3),
                    (0.036, 0.33), (0.0, 0.33)], Y2, z=0.04, seg=18,
                   rfunc=lambda i, a: 1 + 0.08 * math.sin(a * 5 + i))
    for k in range(5):
        a = k * 2.1
        body.ball(math.cos(a) * 0.03, 0.17 + k * 0.03, 0.04 + math.sin(a) * 0.03, 0.013, Y3, 8, 6)
    body.lathe_fwd([(0.024, 0.32), (0.042, 0.322), (0.044, 0.345), (0.03, 0.352), (0.02, 0.345)], PALE, z=0.04)
    body.cyl(0.33, 0.35, 0.02, '#3a2a10', z=0.04, seg=14)
    body.ball(0, 0.34, 0.04, 0.011, '#fff2a0', 10, 7)
    for k in range(3):
        base = P((k - 1) * 0.02, 0.02, -0.0)
        claw(body, base, P((k - 1) * 0.1, 1, -0.3), 0.09, 0.011, CLAW, curl=P(0, 0, -1), seg=6)
    drum = WPart('drum', 'spin', pivot=P(0, 0.08, 0.11), axis=P(0, 1, 0), amount=TAU / 7)
    centers = [(0, 0, 0)] + [(math.cos(TAU * k / 7) * 0.032, 0, math.sin(TAU * k / 7) * 0.032) for k in range(7)]
    for i, (x, f, z) in enumerate(centers):
        for row in (-0.03, 0.0, 0.03):
            r = 0.02 if i else 0.024
            col = (Y, Y2, Y)[int(row / 0.03) + 1] if i % 2 else Y
            body_c = P(x, 0.08 + row + (0.006 if i % 2 else 0), 0.11 + z)
            drum.ell(body_c, r * (0.85 if row else 1.0), col, 12, 8)
    for k in range(7):
        a = TAU * k / 7 + 0.4
        drum.ball(math.cos(a) * 0.05, 0.08, 0.11 + math.sin(a) * 0.05, 0.005, PALE, 6, 4)
    arm_r = WPart('arm_r', fp_only=True)
    organic_arm(fp, arm_r, P(0, -0.06, 0.04), (-0.22, -0.12, -0.34), Y, Y2, r=0.034)
    arm_l = WPart('arm_l', 'support', pivot=to_gun(fp, (0.22, -0.08, -0.36)), fp_only=True)
    wrist = grip_hand(arm_l, P(0, 0.22, 0.04), P(0, 1, 0), V(0, 0, -1), V(-1, 0, 0), 0.04, Y, fingers=3,
                      fr=0.011, wrap=150, thumb_wrap=-110, claws=CLAW, claw_len=0.05)
    organic_arm(fp, arm_l, wrist, (0.22, -0.08, -0.36), Y, Y2, r=0.03)
    return dict(parts=[body, drum, arm_r, arm_l], fp=fp, muzzle=P(0, 0.355, 0.04), eject=None, kind='organic')


def build_pseudomonas():
    """Fuzil de ácido: tentáculo verde que vira um cano segmentado, bolsa de ácido e boca com dentes."""
    G, G2, G3, ACID, TEETH, MOUTH = '#c3d76e', '#a6bc55', '#8da044', '#b6ff4a', '#f6f7f2', '#2e4680'
    fp = fp_matrix((-0.18, 0.47, -0.205), (-1.5, 4.5, -4))
    body = WPart('body')
    body.lathe_fwd([(0.0, -0.08), (0.055, -0.08), (0.06, 0.02), (0.05, 0.12), (0.034, 0.26), (0.03, 0.4),
                    (0.0, 0.4)], G, z=0.03, seg=20)
    for k in range(7):
        f = 0.05 + k * 0.05
        r = 0.058 - k * 0.0045
        body.lathe_fwd([(r - 0.004, f - 0.007), (r + 0.004, f - 0.003), (r + 0.004, f + 0.003),
                        (r - 0.004, f + 0.007), (r - 0.004, f - 0.007)], G3, z=0.03, seg=20)
    # Flagelo enrolado ao longo do cano.
    pts = []
    for k in range(40):
        t = k / 39
        a = t * TAU * 3.2
        f = 0.02 + t * 0.36
        r = 0.06 - t * 0.022
        pts.append(P(math.cos(a) * r, f, 0.03 + math.sin(a) * r))
    body.tube(pts, [0.006] * 40, G2, 6)
    # Boca com dentes.
    body.lathe_fwd([(0.028, 0.39), (0.048, 0.395), (0.05, 0.42), (0.036, 0.43), (0.022, 0.42)], MOUTH, z=0.03, seg=20)
    body.cyl(0.4, 0.425, 0.021, '#142010', z=0.03, seg=14)
    body.ball(0, 0.41, 0.03, 0.012, ACID, 10, 7)
    for k in range(10):
        a = TAU * k / 10
        b = P(math.cos(a) * 0.04, 0.42, 0.03 + math.sin(a) * 0.04)
        body.cone(b, b + P(-math.cos(a) * 0.012, 0.022, -math.sin(a) * 0.012), 0.006, TEETH, 5)
    sac = WPart('sac', 'pulse', pivot=P(0, 0.06, 0.1), amount=0.25)
    sac.ell(P(0, 0.06, 0.1), (0.045, 0.085, 0.042), ACID, 16, 10)
    sac.ell(P(0, 0.06, 0.1), (0.047, 0.04, 0.03), '#8fe03a', 14, 8)
    for k, (x, f, z) in enumerate(((0.02, 0.02, 0.13), (-0.018, 0.08, 0.128), (0.01, 0.11, 0.12),
                                   (-0.025, 0.03, 0.115))):
        sac.ell(P(x, f, z), 0.008, '#e8ffb0', 8, 5)
    arm_r = WPart('arm_r', fp_only=True)
    organic_arm(fp, arm_r, P(0, -0.07, 0.03), (-0.2, -0.12, -0.36), G, G3, r=0.048, segments=3)
    # Bigode-tentáculo esquerdo enrolado por baixo do cano.
    arm_l = WPart('arm_l', 'support', pivot=to_gun(fp, (0.2, -0.05, -0.36)), fp_only=True)
    elbow = to_gun(fp, (0.2, -0.05, -0.36))
    pts = bc.bezier(elbow, elbow.lerp(P(0, 0.2, -0.05), 0.6) + V(0, 0, -0.05), P(-0.05, 0.22, -0.03),
                    P(-0.06, 0.24, 0.04), 14)
    arm_l.tube(pts, [0.03 - 0.022 * i / 14 for i in range(15)], G, 10)
    return dict(parts=[body, sac, arm_r, arm_l], fp=fp, muzzle=P(0, 0.43, 0.03), eject=None, kind='organic')


def build_streptococcus():
    """SMG rápida: canos duplos em contas, fita de contas (cadeia de estreptococos) e espinhos."""
    PK, PK2, PALE, CLAW, EYE = '#d84f84', '#a83565', '#eef0f5', '#232329', '#e6c843'
    fp = fp_matrix((-0.175, 0.46, -0.2), (-1.5, 4.5, -4))
    body = WPart('body')
    body.lathe_fwd([(0.0, -0.07), (0.046, -0.07), (0.052, 0.0), (0.05, 0.1), (0.04, 0.16), (0.0, 0.16)], PK, z=0.04,
                   seg=18)
    for k in range(3):
        f = 0.0 + k * 0.05
        body.lathe_fwd([(0.046, f - 0.008), (0.056, f - 0.004), (0.056, f + 0.004), (0.046, f + 0.008),
                        (0.046, f - 0.008)], PK2, z=0.04, seg=18)
    for x in (0.018, -0.018):
        for k in range(7):
            body.ball(x, 0.17 + k * 0.026, 0.045, 0.0145, PK if k % 2 else PK2, 10, 7)
        body.cyl(0.34, 0.36, 0.012, PALE, x=x, z=0.045, seg=12)
        body.bore(0.36, 0.007, x=x, z=0.045)
    for k in range(4):
        b = P(0, 0.0 + k * 0.045, 0.085)
        body.cone(b, b + P(0, 0.02, 0.035), 0.009, CLAW, 6)
    body.ball(0, 0.12, 0.072, 0.012, EYE, 10, 7)
    body.ball(0, 0.128, 0.073, 0.005, '#1b1b1f', 8, 5)
    belt = WPart('belt', 'bolt', axis=P(0, -1, 0.3), amount=0.012)
    pts = bc.bezier(P(0, 0.08, -0.01), P(0.0, 0.1, -0.08), P(0.04, 0.0, -0.12), P(0.06, -0.08, -0.08), 9)
    for i, q in enumerate(pts):
        belt.ell(q, 0.016 - i * 0.0006, PK2 if i % 2 else PK, 10, 7)
    arm_r = WPart('arm_r', fp_only=True)
    organic_arm(fp, arm_r, P(0, -0.06, 0.04), (-0.22, -0.12, -0.34), PK, PK2, r=0.038)
    arm_l = WPart('arm_l', 'support', pivot=to_gun(fp, (0.22, -0.08, -0.36)), fp_only=True)
    wrist = grip_hand(arm_l, P(0, 0.24, 0.045), P(0, 1, 0), V(0, 0, -1), V(-1, 0, 0), 0.03, PK, fingers=3,
                      fr=0.011, wrap=150, thumb_wrap=-110, claws=CLAW, claw_len=0.07)
    organic_arm(fp, arm_l, wrist, (0.22, -0.08, -0.36), PK, PK2, r=0.03)
    melee = claw_arm(PK, PK2, CLAW)
    return dict(parts=[body, belt, arm_r, arm_l, melee], fp=fp, muzzle=P(0, 0.365, 0.045), eject=None,
                kind='organic')


BUILDERS = {
    'neutrophil': build_neutrophil,
    'macrophage': build_macrophage,
    'b_cell': build_b_cell,
    'killer_t': build_killer_t,
    'pneumococcus': build_pneumococcus,
    'staphylococcus': build_staphylococcus,
    'pseudomonas': build_pseudomonas,
    'streptococcus': build_streptococcus,
}


# ---------------------------------------------------------------------------------------
# Exportação
# ---------------------------------------------------------------------------------------

C = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0)))  # Blender -> glTF


def gl_vec(v):
    q = C @ V(v)
    return [round(q.x, 5), round(q.y, 5), round(q.z, 5)]


def gl_matrix(m):
    c4 = C.to_4x4()
    g = c4 @ m @ c4.inverted()
    return [[round(g[i][j], 6) for j in range(4)] for i in range(3)]


def build(key):
    spec = BUILDERS[key]()
    parts = [p for p in spec['parts'] if p.faces]
    coll = bpy.data.collections.new(f'w_{key}')
    bpy.context.scene.collection.children.link(coll)
    objs = [bc.make_object(f'w_{key}', p, coll) for p in parts]
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
    gltf, _ = bc.read_glb(glb)
    mapping, count = bc.raylib_mesh_indices(gltf)
    tris = sum(gltf['accessors'][prim['indices']]['count'] // 3 for m in gltf['meshes'] for prim in m['primitives'])
    meta = {'key': key, 'kind': spec['kind'], 'convention': CONVENTION, 'mesh_count': count, 'triangles': tris,
            'fp': gl_matrix(spec['fp']), 'muzzle': gl_vec(spec['muzzle']),
            'eject': gl_vec(spec['eject']) if spec.get('eject') is not None else None, 'parts': []}
    for p in parts:
        ids = mapping[f'w_{key}.{p.name}']
        assert len(ids) == 1, (key, p.name, ids)
        entry = {'name': p.name, 'mesh': ids[0], 'anim': p.anim, 'space': p.space, 'fp_only': p.fp_only}
        if p.anim != 'static':
            entry.update(pivot=gl_vec(p.pivot), axis=gl_vec(p.axis), amount=round(p.amount, 5))
        if p.tip is not None:
            entry['tip'] = gl_vec(p.tip)
        meta['parts'].append(entry)
    (OUT / f'{key}.json').write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding='utf-8')
    print(f'{key:15s} tris={tris:5d} meshes={count} parts={[p.name for p in parts]}', flush=True)
    return objs, spec, parts


def render_fp_preview(key, objs, spec, parts, fov_deg=50.0):
    """Renderiza a pose de primeira pessoa (Workbench) para conferir enquadramento e forma."""
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    sh = scene.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'VERTEX'
    sh.show_object_outline = True
    sh.object_outline_color = (0.08, 0.08, 0.1)
    sh.show_shadows = False
    scene.view_settings.view_transform = 'Standard'
    scene.render.resolution_x, scene.render.resolution_y = 1280, 720
    for o in scene.objects:
        if o.type == 'MESH':
            o.hide_render = o not in objs
    for o, p in zip(objs, parts):
        o.matrix_world = Matrix.Identity(4) if p.space == 'view' else spec['fp']
        o.hide_render = o.hide_render or p.space == 'view'
    cam_data = bpy.data.cameras.new('fpcam')
    cam_data.sensor_fit = 'VERTICAL'
    cam_data.angle_y = math.radians(fov_deg)
    cam_data.clip_start = 0.01
    cam = bpy.data.objects.new('fpcam', cam_data)
    scene.collection.objects.link(cam)
    cam.rotation_euler = (math.radians(90), 0, math.radians(180))
    scene.camera = cam
    PREVIEW.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(PREVIEW / f'fp_{key}.png')
    bpy.ops.render.render(write_still=True)
    # Golpe (parte no espaço da câmera), se houver.
    melee = [o for o, p in zip(objs, parts) if p.space == 'view']
    if melee:
        for o, p in zip(objs, parts):
            o.hide_render = o not in objs or (p.space != 'view' and p.name not in ('body',))
            if p.space == 'view':
                o.hide_render = False
        scene.render.filepath = str(PREVIEW / f'fp_{key}_melee.png')
        bpy.ops.render.render(write_still=True)
    for o in objs:
        o.matrix_world = Matrix.Identity(4)
    bpy.data.objects.remove(cam)


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    keys = list(BUILDERS)
    if '--only' in argv:
        keys = argv[argv.index('--only') + 1].split(',')
    preview = '--no-preview' not in argv
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    built = {k: build(k) for k in keys}
    if preview:
        for k, (objs, spec, parts) in built.items():
            render_fp_preview(k, objs, spec, parts)


if __name__ == '__main__':
    main()
