"""Braços de primeira pessoa com esqueleto: mão modelada (palma, quatro dedos de três falanges e
polegar) presa a um esqueleto de 2 x 18 ossos. Exporta ``Assets/Weapons/<herói>_arms.glb`` + JSON.

Uso (a partir da raiz do repositório):

    & 'C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe' --background --factory-startup `
        --python referencias\\scripts\\personagens\\build_fp_arms.py -- [--only macrophage,b_cell]

A pose não é gravada aqui: o jogo (``UserComponents/cells/fp_arms.py``) resolve a cada quadro um IK de
dois ossos até a empunhadura da arma e fecha os dedos, falange por falange, em volta do cabo, do
guarda-mão ou do que a mão estiver segurando.

Pose de repouso (Blender, mesmo espaço "view" das armas: frente em -Y, esquerda em +X, Z para cima):
braços esticados para a frente, palmas para baixo e polegares para dentro. O JSON guarda, em
coordenadas glTF/raylib, cabeça e ponta de cada osso, o raio de cada dedo e a base de cada mão
(direção dos dedos, normal da palma, lado do polegar e o centro da palma).
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_characters as bc  # noqa: E402
from build_characters import V, tube, ellipsoid, lathe, orient, hexc  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'Assets' / 'Weapons'
C = Matrix(((1, 0, 0), (0, 0, 1), (0, -1, 0)))  # Blender -> glTF
CONVENTION = ('glTF/raylib, espaço do viewmodel: câmera na origem olhando +Z, +X à esquerda da tela, Y para '
              'cima. "rest" = cabeça e ponta de cada osso na pose de repouso (braços à frente, palmas para '
              'baixo). "hands": base de cada mão (forward = dedos, normal = para onde a palma olha, thumb = '
              'lado do polegar, palm = centro da superfície da palma). "radius" = raio de cada falange.')

# Proporções (m). Braços de viewmodel são um pouco mais longos que os reais: o ombro fica fora da tela.
UPPER, FORE, PALM = 0.30, 0.30, 0.088
FINGERS = (  # nome, lado (+ = polegar), recuo da junta, falanges, raio, abertura (graus, + = para o mínimo)
    ('index', 0.0265, 0.004, (0.037, 0.025, 0.021), 0.0089, -3.0),
    ('middle', 0.0088, 0.0, (0.041, 0.027, 0.022), 0.0093, 0.0),
    ('ring', -0.0092, 0.003, (0.038, 0.025, 0.021), 0.0087, 3.5),
    ('pinky', -0.0262, 0.011, (0.030, 0.020, 0.018), 0.0077, 8.0),
)
THUMB = ((0.040, 0.031, 0.026), (0.0128, 0.0114, 0.0104))

STYLES = {
    # Macrófaga: manga longa creme até o punho, babado de renda e mão nua.
    'macrophage': dict(sleeve='#ece2d4', skin='#f6dccb', hand='#f6dccb', nail='#f9e6db', sleeve_to=0.86,
                       cuff='frill', cuff_col='#fbf7f1', girth=0.82, hand_scale=0.9),
    # Célula B: manga azul dobrada até o meio do antebraço, braçadeira clara e luvas cinza.
    'b_cell': dict(sleeve='#7097bf', skin='#f2d2b6', hand='#bfc2c6', nail=None, sleeve_to=0.5, cuff='band',
                   cuff_col='#8fb2d6', glove_cuff='#aeb3b9', girth=0.94, hand_scale=1.0),
    # Neutrófilo: macacão branco até o punho, punho cinza-claro e luvas brancas.
    'neutrophil': dict(sleeve='#eef2f4', skin='#f2d2b6', hand='#fafcfc', nail=None, sleeve_to=0.93, cuff='band',
                       cuff_col='#d3dbe0', glove_cuff='#e6eaed', girth=0.9, hand_scale=0.96),
    # Killer T: manga preta arregaçada, braço forte e mão nua.
    'killer_t': dict(sleeve='#2d3136', skin='#e0aa80', hand='#e0aa80', nail='#eab994', sleeve_to=0.35, cuff='band',
                     cuff_col='#3b4046', girth=1.08, hand_scale=1.05),
    # Bactérias: braço na cor do corpo com anéis, três dedos e polegar com garras.
    'pneumococcus': dict(sleeve='#8b90e8', skin='#8b90e8', hand='#8b90e8', nail=None, sleeve_to=0.3, cuff='band',
                         cuff_col='#7277d4', bands=(0.62,), skip=('pinky',), claws='#24242c', girth=1.1,
                         hand_scale=1.05),
    'staphylococcus': dict(sleeve='#e8d84e', skin='#e8d84e', hand='#e8d84e', nail=None, sleeve_to=0.3, cuff='band',
                           cuff_col='#d2c02a', bands=(0.62,), skip=('pinky',), claws='#24242a', girth=1.0),
    'pseudomonas': dict(sleeve='#c3d76e', skin='#c3d76e', hand='#c3d76e', nail=None, sleeve_to=0.3, cuff='band',
                        cuff_col='#8da044', bands=(0.5, 0.72), skip=('pinky',), claws='#8da044', girth=1.12),
    'streptococcus': dict(sleeve='#d84f84', skin='#d84f84', hand='#d84f84', nail=None, sleeve_to=0.3, cuff='band',
                          cuff_col='#a83565', bands=(0.62,), skip=('pinky',), claws='#232329', girth=1.0),
}


# ---------------------------------------------------------------------------------------
# Malha com pesos
# ---------------------------------------------------------------------------------------

class SkinMesh:
    def __init__(self):
        self.verts, self.faces, self.fcol, self.weights = [], [], [], []

    def add(self, geo, color, weigh):
        """geo = (verts, faces); weigh(v) -> {osso: peso}."""
        v, f = orient(geo)
        base = len(self.verts)
        self.verts.extend(v)
        self.weights.extend(weigh(p) for p in v)
        col = hexc(color)
        for face in f:
            self.faces.append(tuple(base + i for i in face))
            self.fcol.append(col)


def rigid(bone):
    return lambda p: {bone: 1.0}


def chain(points, bones, blends):
    """Pesos ao longo de uma cadeia: points = juntas (len(bones)+1), blends = meia largura da transição
    em cada junta interna. A posição do vértice é projetada na polilinha."""
    points = [V(p) for p in points]
    segs = list(zip(points, points[1:]))
    lens = [(b - a).length for a, b in segs]
    acc = [0.0]
    for ln in lens:
        acc.append(acc[-1] + ln)

    def weigh(p):
        best, s = None, 0.0
        for i, (a, b) in enumerate(segs):
            d = b - a
            t = max(0.0, min(1.0, (p - a).dot(d) / d.length_squared))
            dist = (a + d * t - p).length
            if best is None or dist < best - 1e-9:
                best, s = dist, acc[i] + t * lens[i]
        for j, h in enumerate(blends, start=1):
            if abs(s - acc[j]) < h:
                k = (s - (acc[j] - h)) / (2 * h)
                k = k * k * (3 - 2 * k)
                return {bones[j - 1]: 1 - k, bones[j]: k}
        for j in range(len(bones)):
            if s <= acc[j + 1] or j == len(bones) - 1:
                return {bones[j]: 1.0}
    return weigh


def squircle(p=2.6):
    def f(_i, a):
        c, s = abs(math.cos(a)), abs(math.sin(a))
        return 1.0 / ((c ** p + s ** p) ** (1.0 / p))
    return f


# ---------------------------------------------------------------------------------------
# Um braço (direito); o esquerdo é o espelho em X
# ---------------------------------------------------------------------------------------

def build_arm(style, side):
    """Braço direito com os nomes de ossos do lado pedido (o esquerdo é espelhado depois).
    Devolve (malha, ossos {nome: (cabeça, ponta, pai)}, base da mão, raios)."""
    F, N, T = V(0, -1, 0), V(0, 0, -1), V(1, 0, 0)  # dedos, normal da palma, lado do polegar
    W = V(-0.20, 0.0, -0.20)
    E = W - F * FORE
    S = E - F * UPPER
    K = W + F * PALM
    n = lambda b: f'{b}.{side}'  # noqa: E731
    bones = {n('upperarm'): (S, E, None), n('forearm'): (E, W, n('upperarm')), n('hand'): (W, K, n('forearm'))}
    radius = {}
    mesh = SkinMesh()
    st = style
    hand_col = st['hand']
    g = st.get('girth', 1.0)  # espessura do braço
    arm_w = chain([S, E, W, K], [n('upperarm'), n('forearm'), n('hand')], [0.05, 0.022])

    # Braço: antebraço de pele (sob a manga), manga e punho.
    mesh.add(tube([S - F * 0.03, S + F * 0.15, E], [0.052 * g, 0.05 * g, 0.047 * g], 14, ('round', 'flat')), st['sleeve'], arm_w)
    # Antebraço de pele: só o trecho que sai da manga, mais uma sobra por dentro dela. Indo até o
    # cotovelo, a pele furava a manga quando o cotovelo dobra.
    t = st['sleeve_to']
    s0 = max(-0.01, FORE * t - 0.05)
    prof = [(-0.01, 0.043 * g), (0.1, 0.04 * g), (0.2, 0.035 * g), (FORE + 0.012, max(0.0285 * g, 0.025))]
    pts, rads = [], []
    for (a, ra), (b, rb) in zip(prof, prof[1:]):
        if b <= s0:
            continue
        if not pts:
            k = max(0.0, (s0 - a) / (b - a))
            pts.append(max(a, s0))
            rads.append(ra + (rb - ra) * k)
        if b - pts[-1] >= 0.01 or b == prof[-1][0]:
            pts.append(b)
            rads.append(rb)
    mesh.add(tube([E + F * s for s in pts], rads, 16, ('flat', 'round')), st['skin'], arm_w)
    end = E + F * (FORE * t)
    r_end = (0.0445 - 0.009 * t) * g
    mesh.add(tube([E - F * 0.03, E + F * 0.06, end], [0.05 * g, 0.048 * g, r_end], 18, ('flat', 'flat')), st['sleeve'], arm_w)
    if st['cuff'] == 'frill':
        # Babado de renda: dois anéis ondulados abrindo em direção à mão.
        for k, (r0, r1, ln, waves) in enumerate(((r_end - 0.003, r_end + 0.008, 0.019, 10),
                                                   (r_end - 0.005, r_end + 0.003, 0.013, 12))):
            prof = [(r0, 0.0), (r0 + (r1 - r0) * 0.35, ln * 0.45), (r1, ln), (r1 - 0.0025, ln + 0.002),
                    (r0 + (r1 - r0) * 0.3 - 0.0025, ln * 0.45), (r0 - 0.0025, 0.0)]

            def wave(i, a, waves=waves, prof=prof):
                return 1.0 + 0.07 * math.sin(a * waves) * (min(1.0, i / 2.0) if i < 3 else (5 - i) / 2.0)
            geo = lathe(prof + [prof[0]], 40, rfunc=wave)
            rot = Matrix.Rotation(math.radians(90), 4, 'X')  # +Z do torno -> -Y (frente)
            at = Matrix.Translation(end - F * (0.006 + 0.006 * k)) @ rot
            mesh.add((list(at @ p for p in geo[0]), geo[1]), st['cuff_col'], arm_w)
    else:
        rot = Matrix.Rotation(math.radians(90), 4, 'X')
        prof = [(r_end - 0.002, -0.012), (r_end + 0.004, -0.009), (r_end + 0.004, 0.011), (r_end - 0.001, 0.014)]
        geo = lathe(prof + [prof[0]], 18)
        at = Matrix.Translation(end) @ rot
        mesh.add((list(at @ p for p in geo[0]), geo[1]), st['cuff_col'], arm_w)
    for f in st.get('bands', ()):
        # Anéis extras no antebraço (bactérias).
        q = E + F * (FORE * f)
        r_b = (0.043 - 0.008 * f) * g + 0.004
        mesh.add(tube([q - F * 0.011, q + F * 0.011], [r_b, r_b], 16, ('flat', 'flat')), st['cuff_col'], arm_w)
    if st.get('glove_cuff'):
        mesh.add(tube([W - F * 0.03, W - F * 0.01, W + F * 0.008], [0.0306 * g, 0.0298 * g, 0.0286 * g], 16, ('flat', 'flat')),
                 st['glove_cuff'], arm_w)

    hand_start = len(mesh.verts)
    # Palma: caixa arredondada (squircle) do punho aos nós dos dedos.
    palm_w = chain([W - F * 0.08, W, K + F * 0.02], [n('forearm'), n('hand')], [0.012])
    pts = [W - F * 0.008, W + F * 0.024, W + F * 0.058, K - F * 0.004]
    radii = [(0.0265, 0.0148), (0.0345, 0.0158), (0.0392, 0.0152), (0.0386, 0.0128)]
    mesh.add(tube(pts, radii, 20, ('round', 'round'), hint=tuple(T), rfunc=squircle()), hand_col, palm_w)

    # Dedos.
    for name, lat, back, lens, r, spread in FINGERS:
        a = math.radians(spread)
        d = (F * math.cos(a) - T * math.sin(a)).normalized()
        j0 = K - F * back + T * lat - N * 0.0015
        joints = [j0]
        for ln in lens:
            joints.append(joints[-1] + d * ln)
        names = [n(f'{name}{i}') for i in (1, 2, 3)]
        for i, bn in enumerate(names):
            bones[bn] = (joints[i], joints[i + 1], n('hand') if i == 0 else names[i - 1])
            radius[bn] = r * (1.0 - 0.06 * i)
        pts, rr = [j0 - d * 0.014], [r * 0.95]
        for i in range(3):
            a0, a1, ri = joints[i], joints[i + 1], r * (1.0 - 0.06 * i)
            ln = (a1 - a0).length
            pts += [a0, a0 + d * (ri * 0.45), a0 + d * (ln * 0.5)]
            rr += [ri * 1.05, ri * 1.0, ri * 0.94]
            if i == 2:
                pts += [a1 - d * (ri * 0.7)]
                rr += [ri * 0.88]
            else:
                pts += [a1 - d * (ri * 0.45)]
                rr += [ri * 0.97]
        if name in st.get('skip', ()):
            continue  # osso sem malha: a mão tem menos dedos
        w = chain([j0 - d * 0.05] + joints, [n('hand')] + names, [0.008, 0.0058, 0.0048])
        mesh.add(tube(pts, rr, 12, ('round', 'round'), hint=tuple(N)), hand_col, w)
        if st.get('nail'):
            add_nail(mesh, joints[3], d, N, r * 0.94, st['nail'], names[2])
        if st.get('claws'):
            add_claw(mesh, joints[3], d, N, r * 0.8, 0.045, st['claws'], names[2])

    # Polegar: metacarpo saindo da base da palma, para a frente e para dentro.
    base = W + F * 0.016 + T * 0.021 + N * 0.006
    dirs = [(F * 0.66 + T * 0.62 + N * 0.42).normalized(), (F * 0.8 + T * 0.46 + N * 0.38).normalized(),
            (F * 0.88 + T * 0.32 + N * 0.34).normalized()]
    joints = [base]
    for d, ln in zip(dirs, THUMB[0]):
        joints.append(joints[-1] + d * ln)
    names = [n(f'thumb{i}') for i in (1, 2, 3)]
    for i, bn in enumerate(names):
        bones[bn] = (joints[i], joints[i + 1], n('hand') if i == 0 else names[i - 1])
        radius[bn] = THUMB[1][i]
    pts, rr = [base - dirs[0] * 0.01], [THUMB[1][0] * 0.95]
    for i in range(3):
        a0, a1, ri = joints[i], joints[i + 1], THUMB[1][i]
        d = dirs[i]
        pts += [a0, a0 + d * ((a1 - a0).length * 0.5)]
        rr += [ri * 1.04, ri * 0.97]
        pts += [a1 - d * (ri * (0.7 if i == 2 else 0.4))]
        rr += [ri * (0.86 if i == 2 else 0.98)]
    w = chain([base - dirs[0] * 0.04] + joints, [n('hand')] + names, [0.012, 0.007, 0.005])
    mesh.add(tube(pts, rr, 12, ('round', 'round'), hint=tuple(N)), hand_col, w)
    # Eminência tenar: o volume da palma que acompanha o polegar.
    then = ellipsoid((0.0145, 0.03, 0.0125), 12, 8)
    y = dirs[0]
    x = (T - y * T.dot(y)).normalized()
    fr = Matrix((x, y, x.cross(y))).transposed().to_4x4()
    fr.translation = base + y * 0.012 - T * 0.006 + N * 0.001
    mesh.add(([fr @ p for p in then[0]], then[1]), hand_col,
             chain([base - dirs[0] * 0.05, base + dirs[0] * 0.004, joints[1]], [n('hand'), names[0]], [0.016]))
    if st.get('nail'):
        add_nail(mesh, joints[3], dirs[2], (N - dirs[2] * N.dot(dirs[2])).normalized(), THUMB[1][2], st['nail'],
                 names[2])
    if st.get('claws'):
        add_claw(mesh, joints[3], dirs[2], (N - dirs[2] * N.dot(dirs[2])).normalized(), THUMB[1][2] * 0.8, 0.035,
                 st['claws'], names[2])

    palm_pt = W + F * (PALM * 0.8) + N * 0.0143  # onde o cabo apoia: perto da base dos dedos
    hs = st.get('hand_scale', 1.0)
    if hs != 1.0:  # mão menor/maior, escalada em volta do punho (pesos já calculados)
        mesh.verts[hand_start:] = [W + (v - W) * hs for v in mesh.verts[hand_start:]]
        arm = {n('upperarm'), n('forearm')}
        bones = {k: (h if k in arm else W + (h - W) * hs, t if k in arm else W + (t - W) * hs, p)
                 for k, (h, t, p) in bones.items()}
        radius = {k: v * hs for k, v in radius.items()}
        palm_pt = W + (palm_pt - W) * hs
    hand = dict(forward=F, normal=N, thumb=T, palm=palm_pt)
    return mesh, bones, hand, radius


def add_nail(mesh, tip, d, palm, r, color, bone):
    """Unha: lente fina no dorso da ponta do dedo (palm = normal da palma, a unha fica do outro lado)."""
    geo = ellipsoid((r * 0.66, r * 0.82, r * 0.3), 10, 5)
    side = d.cross(palm).normalized()
    frame = Matrix((side, d, -palm)).transposed().to_4x4()
    frame.translation = tip - d * (r * 0.95) - palm * (r * 0.82)
    mesh.add(([frame @ p for p in geo[0]], geo[1]), color, rigid(bone))


def add_claw(mesh, tip, d, palm, r, length, color, bone):
    """Garra curva saindo da ponta do dedo e se curvando para o lado da palma."""
    pts = [tip - d * (r * 1.2), tip + d * (length * 0.45) + palm * (length * 0.12),
           tip + d * (length * 0.85) + palm * (length * 0.38), tip + d * length + palm * (length * 0.62)]
    mesh.add(tube(pts, [r * 0.95, r * 0.62, r * 0.3, 0.0012], 8, ('round', 'round')), color, rigid(bone))


def merge(parts):
    out = SkinMesh()
    for mesh in parts:
        base = len(out.verts)
        out.verts += mesh.verts
        out.weights += mesh.weights
        out.faces += [tuple(base + i for i in f) for f in mesh.faces]
        out.fcol += mesh.fcol
    return out


def gl(v):
    q = C @ V(v)
    return [round(q.x, 6), round(q.y, 6), round(q.z, 6)]


def make_objects(key, mesh, bones):
    arm_data = bpy.data.armatures.new(f'{key}_arms')
    rig = bpy.data.objects.new(f'{key}_arms', arm_data)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for name, (head, tail, _parent) in bones.items():
        eb = arm_data.edit_bones.new(name)
        eb.head, eb.tail = head, tail
        eb.align_roll(V(0, 0, -1))
    for name, (_h, _t, parent) in bones.items():
        if parent:
            arm_data.edit_bones[name].parent = arm_data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')

    me = bpy.data.meshes.new(f'{key}_arms.mesh')
    me.from_pydata([tuple(v) for v in mesh.verts], [], mesh.faces)
    me.polygons.foreach_set('use_smooth', [True] * len(mesh.faces))
    attr = me.color_attributes.new('Color', 'BYTE_COLOR', 'CORNER')
    cols = []
    for poly, col in zip(me.polygons, mesh.fcol):
        cols.extend((col[0] / 255, col[1] / 255, col[2] / 255, 1.0) * poly.loop_total)
    attr.data.foreach_set('color_srgb', cols)
    me.color_attributes.active_color = attr
    me.color_attributes.render_color_index = me.color_attributes.active_color_index
    me.validate(clean_customdata=False)
    me.update()
    ob = bpy.data.objects.new(f'{key}_arms.mesh', me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(bc.material())
    groups = {name: ob.vertex_groups.new(name=name) for name in bones}
    for i, w in enumerate(mesh.weights):
        items = sorted(w.items(), key=lambda kv: -kv[1])[:4]
        total = sum(v for _, v in items) or 1.0
        for name, v in items:
            if v > 1e-4:
                groups[name].add([i], v / total, 'REPLACE')
    ob.parent = rig
    mod = ob.modifiers.new('arms', 'ARMATURE')
    mod.object = rig
    return rig, ob


def build(key):
    style = STYLES[key]
    parts, bones, hands, radius = [], {}, {}, {}
    for side in ('R', 'L'):
        mesh, b, hand, r = build_arm(style, side)
        if side == 'L':
            mesh.verts = [V(-p.x, p.y, p.z) for p in mesh.verts]
            mesh.faces = [tuple(reversed(f)) for f in mesh.faces]
            b = {k: (V(-h.x, h.y, h.z), V(-t.x, t.y, t.z), p) for k, (h, t, p) in b.items()}
            hand = {k: V(-v.x, v.y, v.z) for k, v in hand.items()}
        parts.append(mesh)
        bones.update(b)
        hands[side] = hand
        radius.update(r)
    mesh = merge(parts)
    rig, ob = make_objects(key, mesh, bones)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f'{key}_arms.glb'
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLB', use_selection=True,
                              export_vertex_color='ACTIVE', export_yup=True, export_apply=False,
                              export_texcoords=False, export_normals=True, export_tangents=False,
                              export_materials='EXPORT', export_animations=False, export_skins=True,
                              export_def_bones=False, export_morph=False, export_cameras=False,
                              export_lights=False, export_extras=False, export_image_format='NONE')
    gltf, _ = bc.read_glb(path)
    mapping, count = bc.raylib_mesh_indices(gltf)
    nodes = gltf['nodes']
    joints = [nodes[j]['name'] for j in gltf['skins'][0]['joints']]
    tris = sum(gltf['accessors'][p['indices']]['count'] // 3 for m in gltf['meshes'] for p in m['primitives'])
    meta = {
        'key': key, 'convention': CONVENTION, 'mesh_count': count, 'triangles': tris, 'bones': joints,
        'parents': {name: parent for name, (_h, _t, parent) in bones.items()},
        'rest': {name: [gl(h), gl(t)] for name, (h, t, _p) in bones.items()},
        'hands': {s: {k: gl(v) for k, v in h.items()} for s, h in hands.items()},
        'radius': {k: round(v, 5) for k, v in radius.items()},
    }
    path.with_suffix('.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f'{key}_arms tris={tris} meshes={count} bones={len(joints)}', flush=True)
    return rig, ob


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    keys = list(STYLES)
    if '--only' in argv:
        keys = argv[argv.index('--only') + 1].split(',')
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    for key in keys:
        for ob in list(bpy.data.objects):
            bpy.data.objects.remove(ob)
        build(key)


if __name__ == '__main__':
    main()
