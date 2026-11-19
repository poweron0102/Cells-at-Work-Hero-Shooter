"""Esqueleto, pesos, adereços e ações dos modelos Tripo (hemácia, macrófago e plaqueta).

Uso (a partir da raiz do repositório):

    & 'C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe' --background --factory-startup `
        --python referencias\\scripts\\personagens\\rig_tripo.py -- [--only platelet,macrophage]

Lê os GLB exportados do Tripo em ``referencias/Tripo 3D assets/`` (malha única em T-pose com
textura) e grava as cenas de autoria ``referencias/blender/<key>.blend``. Cada cena tem uma
coleção ``<key>`` com o esqueleto ``<key>.rig``, a malha ``<key>.body`` e o adereço
(``<key>.box`` = caixa de oxigênio da hemácia, ``<key>.bag`` = sacolinha de fibrina da
plaqueta). ``build_characters.py`` exporta essas cenas para ``Assets/Characters3D``.

Passos:

1. Importa, solda as costuras de UV, escala para a altura do jogo e reduz a textura para 2048².
2. Cria o esqueleto a partir das juntas medidas nas vistas ortográficas (coordenadas
   normalizadas pela altura; Blender: Z para cima, frente em -Y, esquerda do personagem em +X).
3. Pesos: distância aos ossos com máscaras por região (lado, faixa dos braços, pernas) e
   suavização pela malha. Regiões secundárias (cabelo, trança, saia, jaqueta, camiseta) são
   reconhecidas pela cor da textura e pela posição e vão para cadeias próprias de ossos.
4. Converte a pose de repouso de T para A (braços a 55°), o que deixa a caixa delimitadora
   compacta no menu e reduz a deformação dos ombros nas animações.
5. Modela o adereço e cria as ações. As poses são escritas como rotações no espaço do
   personagem; mãos que seguram algo usam IK, gravado quadro a quadro nas próprias ações.
"""
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / 'referencias' / 'Tripo 3D assets'
OUT = ROOT / 'referencias' / 'blender'
FONT = ROOT / 'Assets' / 'fonts' / 'MPLUSRounded1c-Bold.ttf'
FPS = 30
TEX = 2048
TAU = math.tau
A_POSE = math.radians(55)


# ---------------------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------------------

def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def rot(x=0.0, y=0.0, z=0.0):
    """Rotação no espaço do personagem (X = esquerda, Y = trás, Z = cima), X depois Y depois Z.
    +X inclina o topo do osso para a frente (a ponta de um osso que aponta para baixo vai para trás)."""
    return Euler((x, y, z), 'XYZ').to_matrix()


def axis_rot(axis, angle):
    return Matrix.Rotation(angle, 3, Vector(axis).normalized())


def seg_dist(P, a, b):
    ab = b - a
    t = np.clip(((P - a) @ ab) / max(float(ab @ ab), 1e-12), 0.0, 1.0)
    return np.linalg.norm(P - (a + t[:, None] * ab), axis=1)


def rgb_to_hsv(c):
    r, g, b = c[:, 0], c[:, 1], c[:, 2]
    mx, mn = c.max(1), c.min(1)
    d = mx - mn + 1e-9
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    s = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0)
    return h, s, mx


def link(obj, coll):
    coll.objects.link(obj)
    return obj


def set_active(obj):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)


# ---------------------------------------------------------------------------------------
# Importação
# ---------------------------------------------------------------------------------------

def import_tripo(filename, key, height, coll):
    bpy.ops.import_scene.gltf(filepath=str(SRC / filename))
    mesh = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
    mw = mesh.matrix_world.copy()
    mesh.parent = None
    for o in list(bpy.context.scene.objects):
        if o is not mesh:
            bpy.data.objects.remove(o)
    for c in mesh.users_collection:
        c.objects.unlink(mesh)
    coll.objects.link(mesh)
    me = mesh.data
    me.transform(mw)
    mesh.matrix_world = Matrix.Identity(4)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bm.to_mesh(me)
    bm.free()
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    zmin, zmax = co[:, 2].min(), co[:, 2].max()
    s = height / (zmax - zmin)
    me.transform(Matrix.Scale(s, 4) @ Matrix.Translation((0, 0, -zmin)))
    if me.has_custom_normals:
        bpy.context.view_layer.objects.active = mesh
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    me.shade_smooth()
    me.update()
    mesh.name = me.name = f'{key}.body'
    mat = me.materials[0]
    mat.name = f'{key}_pele'
    img = next(n.image for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image)
    img.name = f'{key}_basecolor'
    if img.size[0] > TEX:
        img.scale(TEX, TEX)
    img.pack()
    return mesh, img


def vertex_colors(me, img):
    """Cor média da textura (sRGB 0..1) em cada vértice."""
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    uv = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers.active.data.foreach_get('uv', uv)
    uv = uv.reshape(-1, 2)
    vi = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get('vertex_index', vi)
    x = np.clip((uv[:, 0] % 1.0) * (w - 1), 0, w - 1).astype(np.int32)
    y = np.clip((uv[:, 1] % 1.0) * (h - 1), 0, h - 1).astype(np.int32)
    col = px[y, x, :3]
    acc = np.zeros((len(me.vertices), 3), np.float32)
    cnt = np.zeros(len(me.vertices), np.float32)
    np.add.at(acc, vi, col)
    np.add.at(cnt, vi, 1)
    return acc / np.maximum(cnt, 1)[:, None]


# ---------------------------------------------------------------------------------------
# Esqueleto
# ---------------------------------------------------------------------------------------

def humanoid(j):
    """Ossos do corpo a partir das juntas normalizadas ``j``. Lado esquerdo (+X); o direito é
    espelhado. Cada osso: (nome, cabeça, cauda, pai, deforma)."""
    bones = [
        ('hips', j['hips'], j['spine'], None, True),
        ('spine', j['spine'], j['chest'], 'hips', True),
        ('chest', j['chest'], j['neck'], 'spine', True),
        ('neck', j['neck'], j['head'], 'chest', True),
        ('head', j['head'], j['head_top'], 'neck', True),
    ]
    for side, sx in (('L', 1), ('R', -1)):
        def m(p):
            return (p[0] * sx, p[1], p[2])
        bones += [
            (f'shoulder.{side}', m(j['clavicle']), m(j['shoulder']), 'chest', True),
            (f'upper_arm.{side}', m(j['shoulder']), m(j['elbow']), f'shoulder.{side}', True),
            (f'forearm.{side}', m(j['elbow']), m(j['wrist']), f'upper_arm.{side}', True),
            (f'hand.{side}', m(j['wrist']), m(j['fingers']), f'forearm.{side}', True),
            (f'thigh.{side}', m(j['hip']), m(j['knee']), 'hips', True),
            (f'shin.{side}', m(j['knee']), m(j['ankle']), f'thigh.{side}', True),
            (f'foot.{side}', m(j['ankle']), m(j['toe']), f'shin.{side}', True),
        ]
    return bones


def chain(name, points, parent):
    return [(f'{name}.{i}', points[i], points[i + 1], parent if i == 0 else f'{name}.{i - 1}', True)
            for i in range(len(points) - 1)]


def make_armature(key, bones, H, coll):
    arm = bpy.data.armatures.new(f'{key}_rig')
    rig = link(bpy.data.objects.new(f'{key}.rig', arm), coll)
    arm.display_type = 'STICK'
    set_active(rig)
    bpy.ops.object.mode_set(mode='EDIT')
    for name, head, tail, parent, deform in bones:
        eb = arm.edit_bones.new(name)
        eb.head = Vector(head) * H
        eb.tail = Vector(tail) * H
        d = (eb.tail - eb.head).normalized()
        eb.align_roll(Vector((0, 0, 1)) if abs(d.z) < 0.7 else Vector((0, -1, 0)))
        eb.use_deform = deform
        eb.use_connect = False
        if parent:
            eb.parent = arm.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    for pb in rig.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    return rig


def add_bones(rig, bones, H=1.0):
    """Ossos extras (adereços e controles) já no espaço final (metros)."""
    set_active(rig)
    bpy.ops.object.mode_set(mode='EDIT')
    for name, head, tail, parent, deform in bones:
        eb = rig.data.edit_bones.new(name)
        eb.head = Vector(head) * H
        eb.tail = Vector(tail) * H
        d = (eb.tail - eb.head).normalized()
        eb.align_roll(Vector((0, 0, 1)) if abs(d.z) < 0.7 else Vector((0, -1, 0)))
        eb.use_deform = deform
        eb.parent = rig.data.edit_bones[parent] if parent else None
    bpy.ops.object.mode_set(mode='OBJECT')
    for pb in rig.pose.bones:
        pb.rotation_mode = 'QUATERNION'


# ---------------------------------------------------------------------------------------
# Pesos
# ---------------------------------------------------------------------------------------

class Weights:
    def __init__(self, mesh, rig, H, colors):
        me = mesh.data
        n = len(me.vertices)
        co = np.empty(n * 3, np.float32)
        me.vertices.foreach_get('co', co)
        self.P = co.reshape(-1, 3) / H  # coordenadas normalizadas
        e = np.empty(len(me.edges) * 2, np.int32)
        me.edges.foreach_get('vertices', e)
        self.edges = e.reshape(-1, 2)
        self.n = n
        self.H = H
        self.mesh, self.rig = mesh, rig
        self.h, self.s, self.v = rgb_to_hsv(colors)
        self.seg = {b.name: (np.array(b.head_local, np.float32) / H, np.array(b.tail_local, np.float32) / H)
                    for b in rig.data.bones}

    def smooth(self, W, iters, lam=0.5):
        n = self.n
        deg = np.bincount(self.edges.ravel(), minlength=n).astype(np.float32)
        deg[deg == 0] = 1
        a, b = self.edges[:, 0], self.edges[:, 1]
        for _ in range(iters):
            acc = np.zeros_like(W)
            np.add.at(acc, a, W[b])
            np.add.at(acc, b, W[a])
            W = (1 - lam) * W + lam * acc / (deg[:, None] if W.ndim == 2 else deg)
        return W

    def by_distance(self, names, masks=None, power=5.0, eps=0.008):
        W = np.zeros((self.n, len(names)), np.float32)
        for i, name in enumerate(names):
            a, b = self.seg[name]
            d = seg_dist(self.P, a, b)
            w = 1.0 / (d + eps) ** power
            if masks and name in masks:
                w = w * masks[name]
            W[:, i] = w
        W /= np.maximum(W.sum(1, keepdims=True), 1e-20)
        return W

    def body(self, sx, arm_z, arm_band, hip_z):
        """Pesos do corpo. ``sx`` = x do ombro, ``arm_z``/``arm_band`` = faixa dos braços em T,
        ``hip_z`` = altura das juntas do quadril."""
        P = self.P
        x, z = P[:, 0], P[:, 2]
        ax = np.abs(x)
        in_band = smooth(arm_z - arm_band, arm_z - arm_band + 0.025, z)
        arm_zone = smooth(sx - 0.04, sx + 0.015, ax) * in_band
        left, right = smooth(-0.012, 0.012, x), smooth(0.012, -0.012, x)
        leg_zone = smooth(hip_z + 0.05, hip_z - 0.02, z)
        names = [b.name for b in self.rig.data.bones if b.use_deform and b.name.split('.')[0] in {
            'hips', 'spine', 'chest', 'neck', 'head', 'shoulder', 'upper_arm', 'forearm', 'hand',
            'thigh', 'shin', 'foot'}]
        masks = {}
        for name in names:
            base, _, side = name.partition('.')
            m = np.ones(self.n, np.float32)
            if side == 'L':
                m *= left
            elif side == 'R':
                m *= right
            if base in ('upper_arm', 'forearm', 'hand'):
                m *= arm_zone
            elif base == 'shoulder':
                m *= in_band * smooth(sx + 0.01, sx - 0.03, ax)
            elif base in ('thigh', 'shin', 'foot'):
                m *= leg_zone
            else:
                m *= 1 - 0.97 * smooth(sx, sx + 0.04, ax) * in_band
                if base in ('spine', 'chest', 'neck', 'head'):
                    m *= smooth(hip_z - 0.06, hip_z + 0.02, z)
            masks[name] = m
        W = self.by_distance(names, masks)
        return names, self.smooth(W, 10)

    @staticmethod
    def blend(names_a, Wa, names_b, Wb, k):
        names = list(dict.fromkeys(names_a + names_b))
        k = np.asarray(k, np.float32).reshape(-1)
        W = np.zeros((Wa.shape[0], len(names)), np.float32)
        for i, nm in enumerate(names_a):
            W[:, names.index(nm)] += Wa[:, i] * (1 - k)
        for i, nm in enumerate(names_b):
            W[:, names.index(nm)] += Wb[:, i] * k
        return names, W

    def write(self, names, W, top=4, floor=0.03):
        W = W.copy()
        order = np.argsort(-W, axis=1)
        keep = np.zeros_like(W, dtype=bool)
        rows = np.arange(W.shape[0])[:, None]
        keep[rows, order[:, :top]] = True
        W[~keep] = 0
        W[W < floor] = 0
        W /= np.maximum(W.sum(1, keepdims=True), 1e-9)
        mesh = self.mesh
        mesh.vertex_groups.clear()
        for j, name in enumerate(names):
            vg = mesh.vertex_groups.new(name=name)
            idx = np.nonzero(W[:, j])[0]
            for i in idx:
                vg.add([int(i)], float(W[i, j]), 'REPLACE')


def bind(mesh, rig):
    mesh.parent = rig
    mesh.matrix_parent_inverse = Matrix.Identity(4)
    mod = mesh.modifiers.new('Armature', 'ARMATURE')
    mod.object = rig


def set_rest_pose(rig, mesh_objs, rotations):
    """Aplica ``rotations`` (osso -> rotação no espaço do personagem) como nova pose de repouso,
    deformando as malhas junto."""
    poser = Poser(rig)
    for name, R in rotations.items():
        rig.pose.bones[name].rotation_quaternion = poser.local(name, R)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    for obj in mesh_objs:
        ev = obj.evaluated_get(dg)
        co = np.empty(len(ev.data.vertices) * 3, np.float32)
        ev.data.vertices.foreach_get('co', co)
        obj.data.vertices.foreach_set('co', co)
        obj.data.update()
    mats = {pb.name: pb.matrix.copy() for pb in rig.pose.bones}
    for pb in rig.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
    set_active(rig)
    bpy.ops.object.mode_set(mode='EDIT')
    for eb in rig.data.edit_bones:
        eb.matrix = mats[eb.name]
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.view_layer.update()


def a_pose(rig, mesh):
    """T -> A: a clavícula leva uma parte da descida para o ombro não murchar."""
    share = 0.16
    set_rest_pose(rig, [mesh], {'shoulder.L': rot(y=share), 'shoulder.R': rot(y=-share),
                                'upper_arm.L': rot(y=A_POSE - share), 'upper_arm.R': rot(y=-(A_POSE - share))})


# ---------------------------------------------------------------------------------------
# Poses e ações
# ---------------------------------------------------------------------------------------

class Poser:
    def __init__(self, rig):
        self.rig = rig
        self.rest = {b.name: b.matrix_local.to_3x3() for b in rig.data.bones}

    def local(self, name, R):
        B = self.rest[name]
        return (B.inverted() @ R @ B).to_quaternion()

    def local_loc(self, name, d):
        return self.rest[name].inverted() @ Vector(d)


class Pose(dict):
    """Pose de um quadro: osso -> rotação 3x3 no espaço do personagem; ``loc`` = deslocamentos;
    ``ik`` = influência das restrições IK."""

    def __init__(self):
        super().__init__()
        self.loc = {}
        self.ik = {}

    def r(self, name, x=0.0, y=0.0, z=0.0):
        R = rot(x, y, z)
        self[name] = R @ self[name] if name in self else R
        return self

    def m(self, name, R):
        self[name] = R @ self[name] if name in self else R
        return self


def add_ik(rig, bone, target, chain_count=2, pole=None):
    pb = rig.pose.bones[bone]
    c = pb.constraints.new('IK')
    c.name = f'IK {target}'
    c.target = rig
    c.subtarget = target
    c.chain_count = chain_count
    c.use_tail = True
    if pole:
        c.pole_target = rig
        c.pole_subtarget = pole
    return c


def bake_action(rig, name, frames, pose_fn, ik_bones):
    """Grava a ação ``name`` com ``frames`` intervalos (o último quadro repete o primeiro). Ossos
    afetados por IK são gravados com a transformação visual; os demais, com a pose direta."""
    poser = Poser(rig)
    deform = [b.name for b in rig.data.bones if b.use_deform]
    constraints = [(pb, c) for pb in rig.pose.bones for c in pb.constraints]
    samples = []
    for f in range(frames + 1):
        t = (f % frames) / frames
        pose = pose_fn(t)
        for pb in rig.pose.bones:
            R = pose.get(pb.name)
            pb.rotation_quaternion = poser.local(pb.name, R) if R is not None else (1, 0, 0, 0)
            d = pose.loc.get(pb.name)
            pb.location = poser.local_loc(pb.name, d) if d is not None else (0, 0, 0)
        for pb, c in constraints:
            c.influence = pose.ik.get(c.subtarget, 0.0)
        bpy.context.view_layer.update()
        frame = {}
        for bn in deform:
            pb = rig.pose.bones[bn]
            if bn in ik_bones:
                M = rig.convert_space(pose_bone=pb, matrix=pb.matrix, from_space='POSE', to_space='LOCAL')
                frame[bn] = (M.to_quaternion(), M.to_translation())
            else:
                frame[bn] = (pb.rotation_quaternion.copy(), pb.location.copy())
        samples.append(frame)
    for pb, c in constraints:
        c.influence = 0.0
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    rig.animation_data_create()
    rig.animation_data.action = act
    moves = {bn for frame in samples for bn, (_, loc) in frame.items()
             if bn not in ik_bones and loc.length > 1e-6}
    prev = {}
    for f, frame in enumerate(samples):
        for bn, (q, loc) in frame.items():
            if bn in prev and prev[bn].dot(q) < 0:
                q = -q
            prev[bn] = q
            pb = rig.pose.bones[bn]
            pb.rotation_quaternion = q
            pb.keyframe_insert('rotation_quaternion', frame=f, group=bn)
            if bn in moves:
                pb.location = loc
                pb.keyframe_insert('location', frame=f, group=bn)
    for pb in rig.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    rig.animation_data.action = None
    return act


def remove_controls(rig, names):
    for pb in rig.pose.bones:
        for c in list(pb.constraints):
            pb.constraints.remove(c)
    set_active(rig)
    bpy.ops.object.mode_set(mode='EDIT')
    for n in names:
        rig.data.edit_bones.remove(rig.data.edit_bones[n])
    bpy.ops.object.mode_set(mode='OBJECT')


# Movimentos compartilhados ------------------------------------------------------------------

def arm_hang(p, side, down, fwd=0.0, out=0.0, elbow=0.25, wrist=0.0):
    """Braço livre a partir da pose A: ``down`` abaixa mais (rad), ``fwd`` leva à frente."""
    s = 1 if side == 'L' else -1
    p.r(f'upper_arm.{side}', y=s * down)
    p.r(f'upper_arm.{side}', x=-fwd, z=s * out)
    p.r(f'forearm.{side}', x=-elbow)
    if wrist:
        p.r(f'hand.{side}', x=-wrist)


def walk_legs(p, t, H, stride=0.42, knee=0.85, bob=0.018, lift=1.0):
    w = TAU * t
    for side, ph in (('L', 0.0), ('R', math.pi)):
        a = w + ph
        thigh = -stride * math.sin(a)
        swing = max(0.0, math.cos(a))  # perna indo à frente
        k = knee * swing ** 1.5 * lift + 0.08
        p.r(f'thigh.{side}', x=thigh - 0.12 * swing * lift)
        p.r(f'shin.{side}', x=k)
        p.r(f'foot.{side}', x=-(thigh + k) * 0.55 + 0.25 * max(0.0, -math.sin(a + 0.6)) * (1 - swing))
    p.loc['hips'] = (0, 0, H * (-bob * math.cos(2 * w) - bob * 0.6))
    p.r('hips', y=0.035 * math.sin(w), z=0.07 * math.sin(w))
    p.r('spine', z=-0.05 * math.sin(w))
    p.r('chest', z=-0.06 * math.sin(w))


def hair_chain(p, names, t_sway, amp, lag=0.6, back=0.0, side=0.0, bounce=None):
    """Mechas: cada osso atrasa ``lag`` rad em relação ao anterior."""
    for i, n in enumerate(names):
        k = 1 + 0.35 * i
        ax = back * (0.6 + 0.4 * i) + amp * k * math.sin(t_sway - lag * i)
        ay = side + amp * 0.6 * k * math.sin(t_sway * 0.5 - lag * i + 1.0)
        if bounce is not None:
            ax += bounce * k * math.sin(2 * t_sway - lag * i - 0.8)
        p.r(n, x=ax, y=ay)


# ---------------------------------------------------------------------------------------
# Adereços
# ---------------------------------------------------------------------------------------

def vc_material():
    mat = bpy.data.materials.get('prop_vertex')
    if mat is None:
        mat = bpy.data.materials.new('prop_vertex')
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        bsdf = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')
        attr = nodes.new('ShaderNodeVertexColor')
        attr.layer_name = 'Color'
        mat.node_tree.links.new(attr.outputs[0], bsdf.inputs[0])
        bsdf.inputs['Roughness'].default_value = 1.0
    return mat


def hexc(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)) + (1.0,)


class PropBuilder:
    """Junta peças (bmesh) com cor por face em um único objeto."""

    def __init__(self):
        self.bm = bmesh.new()
        self.col = self.bm.faces.layers.int.new('col')
        self.palette = []

    def color_id(self, c):
        if c not in self.palette:
            self.palette.append(c)
        return self.palette.index(c)

    def add_bm(self, other, color, matrix=None):
        me = bpy.data.meshes.new('tmp')
        other.to_mesh(me)
        other.free()
        if matrix is not None:
            me.transform(matrix)
        start = len(self.bm.faces)
        self.bm.from_mesh(me)
        bpy.data.meshes.remove(me)
        self.bm.faces.ensure_lookup_table()
        cid = self.color_id(color)
        for f in self.bm.faces[start:]:
            f[self.col] = cid

    def add_mesh(self, me, color, matrix=None):
        if matrix is not None:
            me.transform(matrix)
        start = len(self.bm.faces)
        self.bm.from_mesh(me)
        bpy.data.meshes.remove(me)
        self.bm.faces.ensure_lookup_table()
        cid = self.color_id(color)
        for f in self.bm.faces[start:]:
            f[self.col] = cid

    def finish(self, name, coll, smooth_faces=False):
        me = bpy.data.meshes.new(name)
        self.bm.to_mesh(me)
        attr = me.color_attributes.new('Color', 'BYTE_COLOR', 'CORNER')
        cols = np.array([hexc(c) for c in self.palette], np.float32)
        ids = np.empty(len(me.polygons), np.int32)
        me.attributes['col'].data.foreach_get('value', ids)
        counts = np.empty(len(me.polygons), np.int32)
        me.polygons.foreach_get('loop_total', counts)
        attr.data.foreach_set('color_srgb', np.repeat(cols[ids], counts, axis=0).ravel())
        me.attributes.remove(me.attributes['col'])
        me.color_attributes.active_color = attr
        me.color_attributes.render_color_index = me.color_attributes.active_color_index
        if smooth_faces:
            me.shade_smooth()
        else:
            me.shade_flat()
        me.materials.append(vc_material())
        self.bm.free()
        return link(bpy.data.objects.new(name, me), coll)


def rounded_box(size, radius, segments=3):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    bmesh.ops.bevel(bm, geom=bm.edges[:], offset=radius, segments=segments, affect='EDGES', profile=0.5)
    return bm


def plate(outline, depth):
    """Placa fina extrudada em Z a partir de um contorno 2D (x, y)."""
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, 0)) for x, y in outline]
    f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    for v in ext['geom']:
        if isinstance(v, bmesh.types.BMVert):
            v.co.z += depth
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    return bm


def text_mesh(text, size, depth=0.0015):
    curve = bpy.data.curves.new('txt', 'FONT')
    curve.body = text
    curve.font = bpy.data.fonts.load(str(FONT), check_existing=True)
    curve.size = size
    curve.extrude = depth / 2
    curve.align_x = 'CENTER'
    curve.align_y = 'CENTER'
    curve.resolution_u = 3
    obj = bpy.data.objects.new('txt', curve)
    bpy.context.scene.collection.objects.link(obj)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
    bpy.data.objects.remove(obj)
    bpy.data.curves.remove(curve)
    return me


def face_frame(normal, up):
    """Matriz que leva o plano XY (normal +Z) para uma face com ``normal`` e ``up``."""
    n = Vector(normal).normalized()
    u = Vector(up).normalized()
    r = u.cross(n)
    M = Matrix((r, u, n)).transposed()
    return M.to_4x4()


def oxygen_box(name, coll, center, size=(0.40, 0.34, 0.34)):
    """Caixa de oxigênio da hemácia (referencias/Tripo 3D assets/globulo vermelho caixa.png):
    papelão branco com cantos arredondados, faixas azuis e as etiquetas vermelhas 酸素/配送書."""
    W, D, Hh = size
    pb = PropBuilder()
    white, blue, red, ink, seam = '#f3f6fa', '#3b8ad9', '#de4a3e', '#1d1d24', '#c9d2dc'
    pb.add_bm(rounded_box((W, D, Hh), 0.022), white)
    eps = 0.0012
    hw, hh = W / 2 - 0.012, Hh / 2 - 0.012

    def face(normal, offset, x, z, ang=0.0):
        """Plano local XY -> face da caixa (+Z local = para fora); x à direita de quem olha."""
        n = Vector(normal)
        M = Matrix.Translation(n * offset + Vector((0, 0, z))) @ face_frame(normal, (0, 0, 1))
        return M @ Matrix.Translation((x, 0, 0)) @ Matrix.Rotation(ang, 4, 'Z')

    def label(normal, offset, x, z, text, w, h, size, ang=0.0):
        M = face(normal, offset, x, z, ang)
        pb.add_bm(plate([(-w, -h), (w, -h), (w, h), (-w, h)], 0.0012), red, M)
        txt = text_mesh(text, size)
        pb.add_mesh(txt, ink, M @ Matrix.Translation((0, 0, 0.0016)))

    front = ((0, -1, 0), D / 2 + eps)
    # Frente (vista de frente: direita = +X). Triângulo azul no canto superior esquerdo.
    pb.add_bm(plate([(-hw, hh), (-hw + 0.17, hh), (-hw, hh - 0.21)], 0.001), blue, face(*front, 0, 0))
    # Faixas diagonais azuis no canto inferior direito.
    for a, b in ((0.10, 0.16), (0.19, 0.22)):
        pb.add_bm(plate([(hw - a, -hh), (hw - a + 0.05, -hh), (hw, -hh + b - 0.05), (hw, -hh + b)], 0.001), blue,
                  face(*front, 0, 0))
    label(*front, 0.07, 0.06, '酸素', 0.07, 0.03, 0.042, math.radians(-14))
    # Lado direito do personagem (-X): etiqueta 配送書 junto à quina da frente e faixas atrás.
    right = ((-1, 0, 0), W / 2 + eps)
    label(*right, D / 2 - 0.085, -0.035, '配送書', 0.075, 0.022, 0.03)
    for a in (0.06, 0.15):
        pb.add_bm(plate([(-D / 2 + a, -hh), (-D / 2 + a - 0.045, -hh), (-D / 2 + 0.012, -hh + a + 0.02),
                         (-D / 2 + 0.012, -hh + a - 0.025)], 0.001), blue, face(*right, 0, 0))
    # Lado esquerdo (+X): faixas.
    left = ((1, 0, 0), W / 2 + eps)
    for a in (0.07, 0.16):
        pb.add_bm(plate([(D / 2 - a, -hh), (D / 2 - a + 0.045, -hh), (D / 2 - 0.012, -hh + a + 0.02),
                         (D / 2 - 0.012, -hh + a - 0.025)], 0.001), blue, face(*left, 0, 0))
    # Emenda das abas na tampa.
    M = Matrix.Translation((0, 0, Hh / 2 + eps)) @ face_frame((0, 0, 1), (0, 1, 0))
    pb.add_bm(plate([(-W / 2 + 0.02, -0.004), (W / 2 - 0.02, -0.004), (W / 2 - 0.02, 0.004), (-W / 2 + 0.02, 0.004)],
                    0.0008), seam, M)
    obj = pb.finish(name, coll)
    obj.data.transform(Matrix.Translation(center))
    return obj


def heart(cx, cy, r, n=28):
    pts = []
    for i in range(n):
        t = TAU * i / n
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x / 17 * r, cy + y / 17 * r))
    return pts


def ellipse(cx, cy, rx, ry, n=20):
    return [(cx + rx * math.cos(TAU * i / n), cy + ry * math.sin(TAU * i / n)) for i in range(n)]


def fibrin_bag(name, coll, top_center):
    """Sacolinha de fibrina da plaqueta (referencias/Tripo 3D assets/plaqueta caixa.png): corpo
    arredondado rosa em cima e branco embaixo, coração na frente, furo lateral e as fitas de
    fibrina prateadas saindo pela abertura. ``top_center`` = ponto da alça na mão."""
    W, D, Hh = 0.20, 0.12, 0.17
    pink, white, pink_dk, metal, metal_dk, inside = '#f6b9d2', '#faf5f8', '#e98fb5', '#cdd2da', '#7d838e', '#9a8f99'
    pb = PropBuilder()
    # Corpo: duas metades (branca embaixo, rosa em cima) de uma caixa arredondada.
    for z0, z1, c in ((-Hh / 2 - 0.01, -Hh * 0.08, white), (-Hh * 0.08, Hh / 2 - 0.012, pink)):
        bm = rounded_box((W, D, Hh), 0.035, 4)
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        r = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, z0), plane_no=(0, 0, -1), clear_outer=True)
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, z1), plane_no=(0, 0, 1), clear_outer=True)
        pb.add_bm(bm, c)
    # Abertura escura no topo (tampa recuada) e a borda.
    pb.add_bm(plate(ellipse(0, 0, W / 2 - 0.012, D / 2 - 0.012), 0.002), inside,
              Matrix.Translation((0, 0, Hh / 2 - 0.045)))
    eps = 0.001
    front = Matrix.Translation((0, -D / 2 - eps, -Hh * 0.27)) @ face_frame((0, -1, 0), (0, 0, 1))
    pb.add_bm(plate(heart(0, 0, 0.034), 0.001), pink_dk, front)
    pb.add_bm(plate(heart(0, 0, 0.022), 0.0016), metal_dk, front)
    for sx in (-1, 1):
        side = Matrix.Translation((sx * (W / 2 + eps), 0, Hh * 0.2)) @ face_frame((sx, 0, 0), (0, 0, 1))
        pb.add_bm(plate(ellipse(0, 0, 0.03, 0.024), 0.001), pink_dk, side)
        pb.add_bm(plate(ellipse(0, 0, 0.022, 0.017), 0.0016), metal_dk, side)
    # Fitas de fibrina: anéis prateados inclinados saindo da abertura.
    for i, (x, y, ang, tilt) in enumerate(((-0.055, 0.0, 20, 70), (-0.01, 0.015, -30, 55), (0.04, -0.01, 50, 65),
                                           (0.07, 0.02, -10, 80))):
        bm = bmesh.new()
        bmesh.ops.create_circle(bm, cap_ends=False, radius=0.032, segments=14)
        ring = bm.edges[:]
        ext = bmesh.ops.extrude_edge_only(bm, edges=ring)
        for v in ext['geom']:
            if isinstance(v, bmesh.types.BMVert):
                v.co.z += 0.018
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        # Espessura: duplica para dentro com cor escura (lado interno visível).
        M = (Matrix.Translation((x, y, Hh / 2 + 0.006)) @ Matrix.Rotation(math.radians(ang), 4, 'Z')
             @ Matrix.Rotation(math.radians(tilt), 4, 'X'))
        pb.add_bm(bm, metal if i % 2 == 0 else metal_dk, M)
    # Alça rosa em arco até a mão.
    pts = []
    n = 12
    for i in range(n + 1):
        a = math.pi * i / n
        pts.append(Vector((-math.cos(a) * (W / 2 - 0.025), 0, Hh / 2 + math.sin(a) * 0.085)))
    bm = bmesh.new()
    prev = None
    for i, c in enumerate(pts):
        d = (pts[min(i + 1, n)] - pts[max(i - 1, 0)]).normalized()
        side = d.cross(Vector((0, 1, 0))).normalized()
        ring = [bm.verts.new(c + side * 0.006 * math.cos(TAU * k / 6) + Vector((0, 1, 0)) * 0.009 * math.sin(TAU * k / 6))
                for k in range(6)]
        if prev:
            for k in range(6):
                bm.faces.new((prev[k], prev[(k + 1) % 6], ring[(k + 1) % 6], ring[k]))
        prev = ring
    pb.add_bm(bm, pink_dk)
    obj = pb.finish(name, coll)
    # A alça fica com o topo no ponto da mão; a sacola gira 90° para a frente (coração) ficar
    # para fora do corpo e a alça correr de frente para trás, como numa mão pendurada.
    obj.data.transform(Matrix.Translation(Vector(top_center) - Vector((0, 0, Hh / 2 + 0.085)))
                       @ Matrix.Rotation(math.pi / 2, 4, 'Z'))
    return obj, Hh / 2 + 0.085 + Hh / 2


# ---------------------------------------------------------------------------------------
# Personagens
# ---------------------------------------------------------------------------------------

def finish_scene(key, coll):
    OUT.mkdir(parents=True, exist_ok=True)
    for obj in list(bpy.context.scene.collection.objects):
        bpy.context.scene.collection.objects.unlink(obj)
    path = OUT / f'{key}.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True)
    print(f'[rig_tripo] {key}: {path}', flush=True)


def build_red_blood_cell():
    key, H = 'red_blood_cell', 1.70
    coll = bpy.data.collections.new(key)
    bpy.context.scene.collection.children.link(coll)
    mesh, img = import_tripo('Globulo vermelho 3d model.glb', key, H, coll)
    colors = vertex_colors(mesh.data, img)
    j = dict(hips=(0, 0.005, 0.47), spine=(0, 0.005, 0.56), chest=(0, 0.0, 0.66), neck=(0, 0.005, 0.80),
             head=(0, 0.01, 0.85), head_top=(0, 0.01, 0.98), clavicle=(0.025, 0.005, 0.79),
             shoulder=(0.10, 0.005, 0.79), elbow=(0.235, 0.008, 0.79), wrist=(0.35, 0.0, 0.79),
             fingers=(0.435, 0.0, 0.79), hip=(0.055, 0.005, 0.50), knee=(0.05, 0.0, 0.275),
             ankle=(0.045, 0.02, 0.065), toe=(0.045, -0.075, 0.015))
    bones = humanoid(j)
    bones += [('hair.B', (0, 0.05, 0.875), (0, 0.075, 0.82), 'head', True),
              ('hair.L', (0.06, -0.01, 0.875), (0.075, -0.01, 0.815), 'head', True),
              ('hair.R', (-0.06, -0.01, 0.875), (-0.075, -0.01, 0.815), 'head', True),
              ('jacket.L', (0.065, -0.055, 0.745), (0.07, -0.07, 0.625), 'chest', True),
              ('jacket.R', (-0.065, -0.055, 0.745), (-0.07, -0.07, 0.625), 'chest', True),
              ('jacket.B', (0, 0.06, 0.745), (0, 0.075, 0.625), 'chest', True)]
    rig = make_armature(key, bones, H, coll)
    w = Weights(mesh, rig, H, colors)
    names, W = w.body(sx=0.10, arm_z=0.79, arm_band=0.055, hip_z=0.50)
    P, h, s, v = w.P, w.h, w.s, w.v
    redish = ((h < 22) | (h > 340)) & (s > 0.45) & (v > 0.35)
    # Cabelo: vermelho entre o boné e o queixo, fora do eixo do pescoço (a gola também é vermelha).
    radial = np.hypot(P[:, 0], P[:, 1] - 0.01)
    hair = (redish * smooth(0.055, 0.07, radial) * smooth(0.89, 0.86, P[:, 2]) * smooth(0.80, 0.815, P[:, 2])
            * smooth(0.10, 0.085, np.abs(P[:, 0])))  # só na largura da cabeça (a manga também é vermelha)
    hair = np.clip(w.smooth(hair.astype(np.float32), 3) * smooth(0.875, 0.825, P[:, 2]) * 1.4, 0, 1)
    hn = ['hair.B', 'hair.L', 'hair.R', 'head']
    Wh = w.by_distance(hn)
    names, W = Weights.blend(names, W, hn, Wh, hair[:, None])
    # Jaqueta: barra vermelha abaixo do peito balança um pouco.
    jacket = redish * smooth(0.60, 0.625, P[:, 2]) * smooth(0.76, 0.73, P[:, 2]) * smooth(0.13, 0.11, np.abs(P[:, 0]))
    jacket = np.clip(w.smooth(jacket.astype(np.float32), 3), 0, 1) * smooth(0.75, 0.64, P[:, 2]) * 0.85
    jn = ['jacket.L', 'jacket.R', 'jacket.B']
    names, W = Weights.blend(names, W, jn, w.by_distance(jn), jacket[:, None])
    w.write(names, W)
    bind(mesh, rig)
    a_pose(rig, mesh)

    # Caixa de oxigênio carregada à frente, presa ao peito.
    box_c = Vector((0, -0.30, 1.0))
    box = oxygen_box(f'{key}.box', coll, box_c)
    add_bones(rig, [('box', box_c, box_c + Vector((0, 0, 0.17)), 'chest', True)])
    vg = box.vertex_groups.new(name='box')
    vg.add(list(range(len(box.data.vertices))), 1.0, 'REPLACE')
    bind(box, rig)
    # Controles de IK: punhos nas laterais da caixa, um pouco atrás do centro.
    ctrl = []
    for side, sx in (('L', 1), ('R', -1)):
        wrist = box_c + Vector((sx * 0.215, 0.07, -0.05))
        ctrl.append((f'ik.{side}', wrist, wrist + Vector((0, -0.05, 0)), 'box', False))
    add_bones(rig, ctrl)
    for side in 'LR':
        add_ik(rig, f'forearm.{side}', f'ik.{side}')
    ik_bones = {'upper_arm.L', 'forearm.L', 'upper_arm.R', 'forearm.R'}

    def holding(p, wave=0.0):
        for side, s in (('L', 1), ('R', -1)):
            # Palpite inicial do IK: cotovelos para fora e para trás.
            p.r(f'upper_arm.{side}', y=s * 0.25, x=-0.3, z=s * 0.25)
            p.r(f'forearm.{side}', x=-1.3)
            p.r(f'hand.{side}', z=-s * 0.15, x=0.1)
        p.ik['ik.L'] = 1.0
        p.ik['ik.R'] = 1.0 - wave

    def idle(t, wave=0.0):
        p = Pose()
        w0 = TAU * t
        holding(p, wave)
        breath = math.sin(w0 * 2)
        p.r('spine', x=0.012 * breath)
        p.r('chest', x=-0.02 * breath)
        p.r('neck', x=0.02 * math.sin(w0 + 1))
        p.r('head', z=0.08 * math.sin(w0), y=0.03 * math.sin(w0 + 0.4))
        p.r('hips', y=0.02 * math.sin(w0))
        for side in 'LR':
            p.r(f'thigh.{side}', y=-0.02 * math.sin(w0))
            p.r(f'foot.{side}', y=0.02 * math.sin(w0))
        p.loc['hips'] = (0.006 * H * math.sin(w0), 0, -0.003 * H * (1 + breath))
        p.r('box', x=0.02 * breath)
        hair_chain(p, ['hair.B'], w0 * 2, 0.03, back=0.0)
        hair_chain(p, ['hair.L'], w0 * 2 + 0.5, 0.03)
        hair_chain(p, ['hair.R'], w0 * 2 + 1.0, 0.03)
        for n, ph in (('jacket.L', 0), ('jacket.R', 1), ('jacket.B', 2)):
            p.r(n, x=0.03 * math.sin(w0 * 2 + ph))
        return p

    def walk(t):
        p = Pose()
        w0 = TAU * t
        holding(p)
        walk_legs(p, t, H, stride=0.48, knee=0.95, bob=0.016)
        p.r('spine', x=0.07)
        p.r('head', x=-0.05 + 0.03 * math.sin(2 * w0 - 0.5), z=0.04 * math.sin(w0))
        p.r('box', x=0.03 * math.sin(2 * w0 - 0.6), z=0.04 * math.sin(w0))
        hair_chain(p, ['hair.B'], w0, 0.05, back=0.18, bounce=0.08)
        hair_chain(p, ['hair.L'], w0 + 0.3, 0.06, back=0.15, bounce=0.07)
        hair_chain(p, ['hair.R'], w0 + 0.6, 0.06, back=0.15, bounce=0.07)
        p.r('jacket.L', x=0.16 + 0.12 * math.sin(2 * w0 - 0.9), y=0.06 * math.sin(w0))
        p.r('jacket.R', x=0.16 + 0.12 * math.sin(2 * w0 - 1.2), y=0.06 * math.sin(w0))
        p.r('jacket.B', x=0.22 + 0.1 * math.sin(2 * w0 - 1.0))
        return p

    def wave(t):
        p = idle(t, wave=1.0)
        w0 = TAU * t
        # Caixa vai para o braço esquerdo; o direito acena acima da cabeça.
        p.r('box', z=0.3)
        p.loc['box'] = (0.13, 0.04, 0.03)
        p['upper_arm.R'] = rot(y=1.9 + 0.06 * math.sin(2 * w0), x=-0.2)
        p['forearm.R'] = rot(y=0.35 + 0.4 * math.sin(4 * w0))
        p['hand.R'] = rot(y=0.2 * math.sin(4 * w0 - 0.6))
        p.r('chest', y=0.06, z=-0.06)
        p.r('head', y=-0.08, z=-0.12)
        return p

    bake_action(rig, 'Idle', 90, idle, ik_bones)
    bake_action(rig, 'Walk', 30, walk, ik_bones)
    bake_action(rig, 'Wave', 60, wave, ik_bones)
    remove_controls(rig, ['ik.L', 'ik.R'])
    finish_scene(key, coll)


def build_macrophage():
    key, H = 'macrophage', 1.82
    coll = bpy.data.collections.new(key)
    bpy.context.scene.collection.children.link(coll)
    mesh, img = import_tripo('Macrofago 3d model.glb', key, H, coll)
    colors = vertex_colors(mesh.data, img)
    j = dict(hips=(0, 0.01, 0.50), spine=(0, 0.01, 0.59), chest=(0, 0.01, 0.68), neck=(0, 0.01, 0.81),
             head=(0, 0.015, 0.845), head_top=(0, 0.015, 0.99), clavicle=(0.03, 0.01, 0.80),
             shoulder=(0.11, 0.01, 0.795), elbow=(0.228, 0.01, 0.795), wrist=(0.33, 0.005, 0.795),
             fingers=(0.425, 0.0, 0.795), hip=(0.055, 0.01, 0.50), knee=(0.042, 0.01, 0.27),
             ankle=(0.035, 0.0, 0.06), toe=(0.035, -0.085, 0.012))
    bones = humanoid(j)
    braid = [(-0.035, 0.045, 0.86), (-0.10, 0.075, 0.78), (-0.165, 0.105, 0.70), (-0.20, 0.13, 0.615),
             (-0.20, 0.15, 0.53)]
    bones += chain('braid', braid, 'head')
    skirt = []
    for k in range(8):
        a = TAU * k / 8
        d = (math.sin(a), -math.cos(a))  # k=0 frente
        pts = [(d[0] * r, d[1] * r, z) for r, z in ((0.075, 0.63), (0.17, 0.42), (0.27, 0.21))]
        skirt += chain(f'skirt{k}', pts, 'hips')
    bones += skirt
    rig = make_armature(key, bones, H, coll)
    w = Weights(mesh, rig, H, colors)
    names, W = w.body(sx=0.11, arm_z=0.795, arm_band=0.06, hip_z=0.50)
    P, h, s, v = w.P, w.h, w.s, w.v
    # Trança: loira (mais saturada que o vestido) e perto da cadeia de ossos da trança.
    bn = [f'braid.{i}' for i in range(4)]
    braid_d = np.minimum.reduce([seg_dist(P, *w.seg[n]) for n in bn])
    blond = (h > 25) & (h < 60) & (s > 0.33) & (v > 0.45)
    br = blond * smooth(0.075, 0.055, braid_d) * smooth(0.875, 0.85, P[:, 2])
    br = np.clip(w.smooth(br.astype(np.float32), 4) * 1.3, 0, 1) * smooth(0.87, 0.80, P[:, 2])
    # Saia: abaixo da faixa da cintura e fora das pernas; as camadas de dentro também seguem a saia
    # (só o que está colado à perna fica com a perna).
    leg_d = np.minimum.reduce([seg_dist(P, *w.seg[n]) for n in ('thigh.L', 'shin.L', 'thigh.R', 'shin.R')])
    sk = smooth(0.66, 0.57, P[:, 2]) * smooth(0.032, 0.05, leg_d) * smooth(0.165, 0.2, P[:, 2]) * (1 - br)
    sk = np.clip(w.smooth(sk.astype(np.float32), 4), 0, 1)
    sn = [b[0] for b in skirt]
    names, W = Weights.blend(names, W, sn + ['hips'], w.by_distance(sn + ['hips'], power=3), sk[:, None])
    names, W = Weights.blend(names, W, bn + ['head'], w.by_distance(bn + ['head'], power=4), br[:, None])
    w.write(names, W)
    bind(mesh, rig)
    a_pose(rig, mesh)

    # Escopeta (Assets/Weapons/macrophage.glb) na mão direita, cano para a frente, na altura do
    # quadril. Os braços do modelo são curtos demais para segurar a bomba com a outra mão.
    grip = Vector((-0.17, -0.19, 1.13))
    add_bones(rig, [('gun', grip, grip + Vector((0, -0.2, 0)), 'chest', False)])
    add_bones(rig, [('ik.R', grip + Vector((0.0, 0.045, 0.0)), grip + Vector((0, -0.05, 0.0)), 'gun', False)])
    add_ik(rig, 'forearm.R', 'ik.R')
    ik_bones = {'upper_arm.R', 'forearm.R'}
    skirt_dirs = [(math.sin(TAU * k / 8), -math.cos(TAU * k / 8)) for k in range(8)]
    braid_names = [f'braid.{i}' for i in range(4)]

    def holding(p):
        p.r('upper_arm.R', y=-0.35, x=-0.2, z=-0.1)
        p.r('forearm.R', x=-1.2)
        p.r('hand.R', x=0.2, z=-0.1)
        p.ik['ik.R'] = 1.0

    def skirt_pose(p, back, roll, flare, legs=None):
        """``back(i)``: arrasto para trás; ``roll(i)``: balanço lateral; ``flare(k, i)``: abertura."""
        for k, (dx, dy) in enumerate(skirt_dirs):
            out = Vector((dy, -dx, 0))  # eixo tangente: ângulo positivo abre a saia
            push = 0.0
            if legs:
                # A perna que avança empurra a frente da saia; a que recua, as costas.
                for side_x, ang in legs:
                    push += max(0.0, -ang) * max(0.0, -dy) * 0.3 + max(0.0, ang) * max(0.0, dy) * 0.2
                    push += abs(ang) * max(0.0, dx * side_x) * 0.08
            for i in range(2):
                R = rot(x=back(i), y=roll(i)) @ axis_rot(out, flare(k, i) + push * (1.0 if i == 0 else 0.4))
                p.m(f'skirt{k}.{i}', R)

    def idle(t):
        p = Pose()
        w0 = TAU * t
        holding(p)
        arm_hang(p, 'L', 0.42, fwd=0.06 + 0.02 * math.sin(w0), elbow=0.3, wrist=0.15)
        breath = math.sin(w0 * 2)
        p.r('spine', x=0.015 * breath)
        p.r('chest', x=-0.02 * breath)
        p.r('head', z=0.07 * math.sin(w0), x=0.02 * math.sin(w0 + 2))
        p.r('hips', y=0.025 * math.sin(w0))
        p.r('gun', x=0.02 * breath)
        p.loc['hips'] = (0.007 * H * math.sin(w0), 0, -0.002 * H * (1 + breath))
        hair_chain(p, braid_names, w0, 0.035, lag=0.7)
        skirt_pose(p, lambda i: 0.0, lambda i: -0.025 * math.sin(w0 - 0.8 - 0.5 * i),
                   lambda k, i: 0.012 * math.sin(2 * w0 - 0.6 - 0.4 * i))
        return p

    def walk(t):
        p = Pose()
        w0 = TAU * t
        holding(p)
        walk_legs(p, t, H, stride=0.5, knee=1.0, bob=0.02)
        arm_hang(p, 'L', 0.42, fwd=-0.45 * math.sin(w0), elbow=0.35 + 0.15 * math.sin(w0 + 0.5), wrist=0.1)
        p.r('spine', x=0.1)
        p.r('head', x=-0.07 + 0.03 * math.sin(2 * w0 - 0.4))
        p.r('gun', x=0.04 * math.sin(2 * w0 - 0.5), z=0.05 * math.sin(w0))
        hair_chain(p, braid_names, w0, 0.07, lag=0.8, back=0.16, bounce=0.05)
        aL = -0.5 * math.sin(w0)
        aR = 0.5 * math.sin(w0)
        skirt_pose(p, lambda i: 0.05 + 0.02 * i + 0.03 * math.sin(2 * w0 - 1.0 - 0.6 * i),
                   lambda i: -0.04 * math.sin(w0 - 0.9 - 0.6 * i),
                   lambda k, i: 0.03 + 0.025 * math.sin(2 * w0 - 0.9 - 0.5 * i), legs=((1, aL), (-1, aR)))
        return p

    def attack(t):
        """Machadada com a escopeta: prepara, ergue acima da cabeça e desce em arco (0..1)."""
        p = Pose()
        holding(p)
        if t < 0.15:
            k = ease(t / 0.15)
            lift, twist, lean = -0.3 * k, 0.15 * k, -0.04 * k
        elif t < 0.45:
            k = ease((t - 0.15) / 0.3)
            lift, twist, lean = -0.3 - 1.9 * k, 0.15 + 0.2 * k, -0.04 - 0.1 * k
        elif t < 0.65:
            k = ((t - 0.45) / 0.2) ** 1.6
            lift, twist, lean = -2.2 + 2.75 * k, 0.35 - 0.6 * k, -0.14 + 0.36 * k
        else:
            k = ease((t - 0.65) / 0.35)
            lift, twist, lean = 0.55 * (1 - k), -0.25 * (1 - k), 0.22 * (1 - k)
        up = max(0.0, -lift) / 2.2
        p.r('gun', x=lift)
        p.loc['gun'] = (0.1 * up, 0.05 * up, 0.5 * up)
        arm_hang(p, 'L', 0.35 - 0.3 * up, fwd=0.3 + 0.4 * up, elbow=0.6, wrist=0.2)
        p.r('spine', x=lean, z=twist * 0.5)
        p.r('chest', x=lean * 0.6, z=twist * 0.5)
        p.r('head', x=-lean * 0.5)
        crouch = max(0.0, lean) / 0.22
        for side in 'LR':
            p.r(f'thigh.{side}', x=-0.25 * crouch)
            p.r(f'shin.{side}', x=0.4 * crouch)
            p.r(f'foot.{side}', x=-0.15 * crouch)
        p.loc['hips'] = (0, 0, -0.02 * H * crouch)
        hair_chain(p, braid_names, TAU * t, 0.04, back=-lean * 1.2)
        skirt_pose(p, lambda i: -lean * (0.25 + 0.2 * i), lambda i: twist * 0.15 * (1 + i),
                   lambda k, i: 0.02 + 0.05 * abs(lean))
        return p

    bake_action(rig, 'Idle', 90, idle, ik_bones)
    bake_action(rig, 'Walk', 30, walk, ik_bones)
    bake_action(rig, 'Attack', 18, attack, ik_bones)
    # Montagem da arma: matriz arma->osso da mão direita na pose de repouso, a partir do
    # primeiro quadro do Idle (arma reta para a frente com a origem na palma).
    idle_pose = idle(0.0)
    poser = Poser(rig)
    for pb in rig.pose.bones:
        R = idle_pose.get(pb.name)
        pb.rotation_quaternion = poser.local(pb.name, R) if R is not None else (1, 0, 0, 0)
        d = idle_pose.loc.get(pb.name)
        pb.location = poser.local_loc(pb.name, d) if d is not None else (0, 0, 0)
    for pb in rig.pose.bones:
        for c in pb.constraints:
            c.influence = 1.0
    bpy.context.view_layer.update()
    hand = rig.pose.bones['hand.R']
    palm = hand.matrix @ Vector((0, hand.length * 0.38, 0))
    skin = hand.matrix @ rig.data.bones['hand.R'].matrix_local.inverted()
    mount = skin.inverted() @ Matrix.Translation(palm)
    rig['weapon_mount'] = [list(r) for r in mount]
    for pb in rig.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    remove_controls(rig, ['ik.R', 'gun'])
    finish_scene(key, coll)


def build_platelet():
    key, H = 'platelet', 1.30
    coll = bpy.data.collections.new(key)
    bpy.context.scene.collection.children.link(coll)
    mesh, img = import_tripo('Plaqueta 3d model.glb', key, H, coll)
    colors = vertex_colors(mesh.data, img)
    j = dict(hips=(0, 0.0, 0.42), spine=(0, 0.0, 0.52), chest=(0, 0.0, 0.62), neck=(0, 0.0, 0.775),
             head=(0, 0.0, 0.80), head_top=(0, 0.0, 0.96), clavicle=(0.03, 0.0, 0.77),
             shoulder=(0.125, 0.0, 0.765), elbow=(0.245, 0.0, 0.762), wrist=(0.355, 0.0, 0.755),
             fingers=(0.42, 0.0, 0.745), hip=(0.065, 0.0, 0.43), knee=(0.09, -0.03, 0.235),
             ankle=(0.125, -0.03, 0.06), toe=(0.13, -0.11, 0.015))
    bones = humanoid(j)
    hair = {
        'hairB': [(0, 0.075, 0.82), (0, 0.10, 0.72), (0, 0.12, 0.63), (0, 0.14, 0.54)],
        'hairBL': [(0.10, 0.06, 0.82), (0.13, 0.08, 0.72), (0.15, 0.10, 0.63), (0.16, 0.12, 0.55)],
        'hairBR': [(-0.10, 0.06, 0.82), (-0.13, 0.08, 0.72), (-0.15, 0.10, 0.63), (-0.16, 0.12, 0.55)],
        'hairFL': [(0.085, -0.05, 0.84), (0.095, -0.065, 0.78), (0.10, -0.07, 0.72)],
        'hairFR': [(-0.085, -0.05, 0.84), (-0.095, -0.065, 0.78), (-0.10, -0.07, 0.72)],
    }
    for name, pts in hair.items():
        bones += chain(name, pts, 'head')
    bones += [('shirt.F', (0, -0.06, 0.58), (0, -0.075, 0.47), 'spine', True),
              ('shirt.B', (0, 0.06, 0.58), (0, 0.07, 0.47), 'spine', True)]
    rig = make_armature(key, bones, H, coll)
    w = Weights(mesh, rig, H, colors)
    names, W = w.body(sx=0.125, arm_z=0.765, arm_band=0.07, hip_z=0.43)
    P, h, s, v = w.P, w.h, w.s, w.v
    # Cabelo: laranja-dourado saturado abaixo da aba do boné.
    hairc = (h > 18) & (h < 48) & (s > 0.38) & (v > 0.3) & (P[:, 2] < 0.9)
    hz = smooth(0.85, 0.79, P[:, 2])
    hz_front = smooth(0.87, 0.82, P[:, 2])
    hz = np.where(P[:, 1] < -0.02, hz_front, hz)
    hm = np.clip(w.smooth(hairc.astype(np.float32), 3) * 1.4, 0, 1) * hz
    hn = [f'{c}.{i}' for c, pts in hair.items() for i in range(len(pts) - 1)] + ['head']
    names, W = Weights.blend(names, W, hn, w.by_distance(hn, power=4), hm[:, None])
    # Barra da camiseta azul-clara balança um pouco.
    blue = (h > 165) & (h < 215) & (s > 0.12)
    sm = np.clip(w.smooth(blue.astype(np.float32), 3), 0, 1) * smooth(0.56, 0.46, P[:, 2]) * 0.75
    sn = ['shirt.F', 'shirt.B', 'spine', 'hips']
    names, W = Weights.blend(names, W, sn, w.by_distance(sn), sm[:, None])
    w.write(names, W)
    bind(mesh, rig)
    a_pose(rig, mesh)

    # Sacolinha de fibrina pendurada na mão esquerda pela alça.
    hand = rig.data.bones['hand.L']
    grip = hand.head_local + (hand.tail_local - hand.head_local) * 0.45
    bag, drop = fibrin_bag(f'{key}.bag', coll, grip)
    add_bones(rig, [('bag', grip, grip - Vector((0, 0, drop * 0.6)), 'hand.L', True)])
    rig.data.bones['bag'].use_inherit_rotation = False
    vg = bag.vertex_groups.new(name='bag')
    vg.add(list(range(len(bag.data.vertices))), 1.0, 'REPLACE')
    bind(bag, rig)
    # IK das pernas para o agachamento do Repair (pés fixos no chão).
    feet = []
    for side in 'LR':
        foot = rig.data.bones[f'foot.{side}']
        feet.append((f'ik.foot.{side}', foot.head_local, foot.tail_local, None, False))
    add_bones(rig, feet)
    for side in 'LR':
        add_ik(rig, f'shin.{side}', f'ik.foot.{side}')
        c = rig.pose.bones[f'foot.{side}'].constraints.new('COPY_ROTATION')
        c.target, c.subtarget = rig, f'ik.foot.{side}'
    ik_bones = {'thigh.L', 'shin.L', 'thigh.R', 'shin.R', 'foot.L', 'foot.R'}
    hair_names = {c: [f'{c}.{i}' for i in range(len(pts) - 1)] for c, pts in hair.items()}

    def all_hair(p, ph, amp, back=0.0, bounce=None, side=0.0):
        for i, (c, ns) in enumerate(hair_names.items()):
            front = c.startswith('hairF')
            hair_chain(p, ns, ph + 0.4 * i, amp * (0.6 if front else 1.0), lag=0.55,
                       back=back * (0.4 if front else 1.0), bounce=bounce, side=side)

    def bag_swing(p, ang_x, ang_y=0.0):
        p.r('bag', x=ang_x, y=ang_y)

    def idle(t):
        p = Pose()
        w0 = TAU * t
        arm_hang(p, 'L', 0.5, fwd=0.05, elbow=0.12)
        arm_hang(p, 'R', 0.62, fwd=0.08, elbow=0.3, wrist=0.1)
        breath = math.sin(w0 * 2)
        p.r('spine', x=0.015 * breath)
        p.r('chest', x=-0.02 * breath)
        p.r('upper_arm.R', y=-0.03 * breath)
        p.r('head', y=0.1 * math.sin(w0), z=0.06 * math.sin(w0 + 1), x=0.03)
        p.r('hips', y=0.03 * math.sin(w0))
        p.loc['hips'] = (0.008 * H * math.sin(w0), 0, -0.003 * H * (1 + breath))
        all_hair(p, w0, 0.03)
        bag_swing(p, 0.06 * math.sin(w0 - 0.6), 0.04 * math.sin(w0 * 2 - 0.3))
        p.r('shirt.F', x=0.02 * math.sin(w0 * 2))
        p.r('shirt.B', x=0.02 * math.sin(w0 * 2 + 1))
        return p

    def walk(t):
        p = Pose()
        w0 = TAU * t
        walk_legs(p, t, H, stride=0.5, knee=1.0, bob=0.022)
        # Braços balançam ao contrário das pernas; o esquerdo, com a sacola, balança menos.
        arm_hang(p, 'L', 0.5, fwd=-0.25 * math.sin(w0), elbow=0.15)
        arm_hang(p, 'R', 0.62, fwd=-0.5 * math.sin(w0 + math.pi) + 0.05, elbow=0.35 + 0.15 * math.sin(w0))
        p.r('spine', x=0.05)
        p.r('head', x=-0.03 + 0.04 * math.sin(2 * w0 - 0.5), y=0.05 * math.sin(w0))
        all_hair(p, w0, 0.06, back=0.16, bounce=0.07)
        bag_swing(p, 0.25 * math.sin(w0 - 1.0) + 0.1, 0.06 * math.sin(2 * w0 - 0.4))
        p.r('shirt.F', x=0.08 + 0.06 * math.sin(2 * w0 - 0.8))
        p.r('shirt.B', x=0.1 + 0.06 * math.sin(2 * w0 - 1.1))
        return p

    def repair(t):
        """Agachada sobre a ferida: a mão direita bate duas vezes o remendo de fibrina."""
        p = Pose()
        w0 = TAU * t
        p.ik['ik.foot.L'] = p.ik['ik.foot.R'] = 1.0
        squat = 0.13 * H
        p.loc['hips'] = (0, 0.03 * H, -squat + 0.006 * H * math.sin(2 * w0))
        for side in 'LR':
            p.r(f'thigh.{side}', x=-0.9)
            p.r(f'shin.{side}', x=1.6)
            p.r(f'foot.{side}', x=-0.55)
        p.r('hips', x=0.15)
        p.r('spine', x=0.3)
        p.r('chest', x=0.15)
        p.r('head', x=-0.25 + 0.06 * math.sin(2 * w0), z=0.05 * math.sin(w0))
        # Duas batidas por ciclo: sobe devagar, desce rápido e fica um instante no remendo.
        k = (2 * t) % 1.0
        if k < 0.55:
            hit = ease(k / 0.55)
        elif k < 0.65:
            hit = 1 - ((k - 0.55) / 0.1) ** 2
        else:
            hit = 0.0
        arm_hang(p, 'R', 0.72, fwd=0.45 + 1.2 * hit, elbow=0.2 + 0.9 * hit, wrist=-0.3 + 0.6 * hit)
        arm_hang(p, 'L', 0.55, fwd=0.35, elbow=0.55)
        all_hair(p, 2 * w0, 0.035, back=-0.3)
        bag_swing(p, -0.35 + 0.05 * math.sin(2 * w0 - 1.0))
        p.r('shirt.F', x=-0.3)
        p.r('shirt.B', x=0.05 * math.sin(2 * w0))
        return p

    bake_action(rig, 'Idle', 90, idle, ik_bones)
    bake_action(rig, 'Walk', 30, walk, ik_bones)
    bake_action(rig, 'Repair', 48, repair, ik_bones)
    remove_controls(rig, ['ik.foot.L', 'ik.foot.R'])
    finish_scene(key, coll)


BUILDERS = {
    'red_blood_cell': build_red_blood_cell,
    'macrophage': build_macrophage,
    'platelet': build_platelet,
}


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    keys = list(BUILDERS)
    if '--only' in argv:
        keys = argv[argv.index('--only') + 1].split(',')
    for key in keys:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.context.scene.render.fps = FPS
        BUILDERS[key]()


if __name__ == '__main__':
    main()
