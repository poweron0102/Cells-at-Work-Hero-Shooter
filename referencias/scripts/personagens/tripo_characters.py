"""Importa os personagens do Tripo (esqueleto Mixamo) e aplica as animações CC0 do Mesh2Motion.

Uso (a partir da raiz do repositório):

    & 'C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe' --background --factory-startup `
        --python referencias\\scripts\\personagens\\tripo_characters.py -- [--only red_blood_cell,platelet,b_cell]

Para cada personagem:

1. importa ``referencias/Tripo 3D assets/<arquivo>.glb`` (malha texturizada com esqueleto Mixamo em T),
   renomeia os ossos para a convenção do projeto (``hips``, ``chest``, ``upper_arm.L``, ``thigh.R``...),
   remove os ossos de ponta e escala até a altura do jogo;
2. reaproveita os clipes de ``referencias/animacoes/mesh2motion`` (esqueleto Unreal): cada osso recebe
   a rotação que o osso correspondente fez a partir da pose de repouso, com a direção de repouso alinhada,
   e o quadril desloca na proporção da altura das pernas;
3. ajustes por personagem: ciclo dos passos começando no pé esquerdo à frente (Walk e Run sincronizados),
   arma presa na mão direita com a esquerda no guarda-mão (Célula B) e caixa entre as mãos (hemácia);
4. salva a cena em ``referencias/blender/<chave>.blend`` e exporta ``Assets/Characters3D/<chave>.glb``
   + ``.json`` (clipes, passadas e camadas usadas pelo animador do jogo, ``UserComponents/cells/animation.py``).
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parents[3]
TRIPO = ROOT / 'referencias' / 'Tripo 3D assets'
CLIPS_DIR = ROOT / 'referencias' / 'animacoes' / 'mesh2motion'
OUT = ROOT / 'Assets' / 'Characters3D'
BLEND = ROOT / 'referencias' / 'blender'
FPS = 30
SOURCE_FPS = 24

FINGERS = ('Thumb', 'Index', 'Middle', 'Ring', 'Pinky')
MIXAMO = {'Hips': 'hips', 'Spine': 'spine', 'Spine1': 'spine.1', 'Spine2': 'chest', 'Neck': 'neck',
          'Head': 'head'}
for _side, _s in (('Left', 'L'), ('Right', 'R')):
    MIXAMO.update({f'{_side}Shoulder': f'shoulder.{_s}', f'{_side}Arm': f'upper_arm.{_s}',
                   f'{_side}ForeArm': f'forearm.{_s}', f'{_side}Hand': f'hand.{_s}',
                   f'{_side}UpLeg': f'thigh.{_s}', f'{_side}Leg': f'shin.{_s}', f'{_side}Foot': f'foot.{_s}',
                   f'{_side}ToeBase': f'toe.{_s}'})
    for _f in FINGERS:
        for _i in (1, 2, 3):
            MIXAMO[f'{_side}Hand{_f}{_i}'] = f'{_f.lower()}.{_i}.{_s}'

# Esqueleto Unreal do Mesh2Motion -> nomes do projeto.
UNREAL = {'pelvis': 'hips', 'spine_01': 'spine', 'spine_02': 'spine.1', 'spine_03': 'chest', 'neck_01': 'neck',
          'head': 'head'}
for _u, _s in (('l', 'L'), ('r', 'R')):
    UNREAL.update({f'clavicle_{_u}': f'shoulder.{_s}', f'upperarm_{_u}': f'upper_arm.{_s}',
                   f'lowerarm_{_u}': f'forearm.{_s}', f'hand_{_u}': f'hand.{_s}', f'thigh_{_u}': f'thigh.{_s}',
                   f'calf_{_u}': f'shin.{_s}', f'foot_{_u}': f'foot.{_s}', f'ball_{_u}': f'toe.{_s}'})
    for _f in FINGERS:
        for _i in (1, 2, 3):
            UNREAL[f'{_f.lower()}_0{_i}_{_u}'] = f'{_f.lower()}.{_i}.{_s}'


def clip(source, start=0.0, end=None, duration=None, loop=False, layer='full', close=0.0, life=0.0):
    """Trecho [start, end] s do arquivo; ``duration`` reescala o tempo; ``close`` (0..1) funde o fim no
    começo para fechar o ciclo; ``layer`` = parte do corpo que o clipe controla no jogo; ``life`` (0..1) soma
    respiração e olhar ao redor (os Idles baixados deixam cabeça e tronco parados)."""
    return dict(source=source, start=start, end=end, duration=duration, loop=loop, layer=layer, close=close,
                life=life)


CHARACTERS = {
    'red_blood_cell': dict(
        file='globulo vermelho.glb', height=1.78, prop='box',
        clips={'Idle': clip('idle-a', loop=True, life=1.0),
               'Walk': clip('walk-female', loop=True),
               'Run': clip('run-female', loop=True),
               # Pose montada em build_box sobre o Idle (só braços e caixa valem no jogo).
               'Carry': clip('idle-a', loop=True, layer='arms', life=1.0),
               'Wave': clip('greeting', 1.0, 3.4, loop=True, layer='upper', close=.25)}),
    'platelet': dict(
        file='plaqueta.glb', height=1.32,
        clips={'Idle': clip('idle-a', loop=True, life=1.2),
               'Walk': clip('walk-happy', loop=True),
               'Repair': clip('hammering', loop=True, layer='upper')}),
    'b_cell': dict(
        file='linfocito b.glb', height=1.88, weapon=True,
        clips={'Idle': clip('rifle-idle', loop=True, life=.6),
               'Walk': clip('rifle-walk', loop=True),
               'Run': clip('rifle-run', loop=True),
               'Fire': clip('rifle-fire', 0.0, .6, layer='upper'),
               'Reload': clip('rifle-reload', duration=1.6, layer='upper'),
               'Melee': clip('punch-cross', .2, .9, duration=.45, layer='upper'),
               'Jump': clip('jump-air', loop=True, layer='lower'),
               'Land': clip('jump-land', .1, .9, duration=.45, layer='lower')}),
}
LOCOMOTION = ('Walk', 'Run')


# ---------------------------------------------------------------------------------------
# Importação do modelo
# ---------------------------------------------------------------------------------------

def import_model(key, spec):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = SOURCE_FPS
    bpy.ops.import_scene.gltf(filepath=str(TRIPO / spec['file']))
    rig = next(o for o in scene.objects if o.type == 'ARMATURE')
    body = next(o for o in scene.objects if o.type == 'MESH')
    for obj in list(scene.objects):
        if obj not in (rig, body):
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    edit = rig.data.edit_bones
    for bone in list(edit):
        short = bone.name.split(':', 1)[-1]
        if short in MIXAMO:
            bone.name = MIXAMO[short]
        else:  # pontas (HeadTop_End, dedo 4, Toe_End): só marcam o comprimento
            edit.remove(bone)
    bpy.ops.object.mode_set(mode='OBJECT')
    missing = set(MIXAMO.values()) - {b.name for b in rig.data.bones}
    if missing:
        raise ValueError(f'{key}: ossos ausentes {sorted(missing)}')

    # Pés em z=0 e altura do jogo.
    top = max((body.matrix_world @ v.co).z for v in body.data.vertices)
    scale = spec['height'] / top
    rig.scale = (scale, scale, scale)
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    body.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    low = min((body.matrix_world @ v.co).z for v in body.data.vertices)
    if abs(low) > .01:
        raise ValueError(f'{key}: pés em z={low:.3f}')

    rig.name = rig.data.name = f'{key}.rig'
    body.name = body.data.name = f'{key}.body'
    for mod in body.modifiers:
        if mod.type == 'ARMATURE':
            mod.object = rig
    for material in body.data.materials:
        material.name = f'{key}_pele'
    # O jogo multiplica a textura pela cor do vértice (COLOR_0): branco neutro.
    colors = body.data.color_attributes.new('Base', 'BYTE_COLOR', 'CORNER')
    for item in colors.data:
        item.color = (1, 1, 1, 1)
    body.data.color_attributes.active_color = colors
    collection = bpy.data.collections.new(key)
    scene.collection.children.link(collection)
    for obj in (rig, body):
        for owner in obj.users_collection:
            owner.objects.unlink(obj)
        collection.objects.link(obj)
    for pb in rig.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    return rig, body


def add_bone(rig, name, parent, matrix, length=.08):
    """Osso extra (soquete/caixa) com repouso exatamente em ``matrix`` (espaço da armadura)."""
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    bone = rig.data.edit_bones.new(name)
    bone.head = (0, 0, 0)
    bone.tail = (0, length, 0)
    bone.matrix = matrix
    bone.parent = rig.data.edit_bones[parent]
    bone.use_deform = name != 'socket_weapon'
    bpy.ops.object.mode_set(mode='OBJECT')
    rig.pose.bones[name].rotation_mode = 'QUATERNION'


# ---------------------------------------------------------------------------------------
# Retarget
# ---------------------------------------------------------------------------------------

def hierarchy(rig):
    """Ossos com os pais antes dos filhos."""
    out = []

    def walk(bone):
        out.append(bone)
        for child in bone.children:
            walk(child)
    for bone in rig.data.bones:
        if bone.parent is None:
            walk(bone)
    return out


def rotation(m):
    return m.to_3x3().normalized()


def load_source(name):
    """Importa o clipe; devolve (armadura, ação). A armadura fica na cena para ser avaliada."""
    before = set(bpy.data.objects)
    actions = set(bpy.data.actions)
    bpy.ops.import_scene.gltf(filepath=str(CLIPS_DIR / f'{name}.glb'))
    new = [o for o in bpy.data.objects if o not in before]
    arm = next(o for o in new if o.type == 'ARMATURE')
    for obj in new:
        if obj is not arm:
            bpy.data.objects.remove(obj, do_unlink=True)
    action = next(a for a in bpy.data.actions if a not in actions)
    arm.animation_data_create().action = action
    if getattr(action, 'slots', None):
        arm.animation_data.action_slot = action.slots[0]
    return arm, action


def retarget(rig, spec):
    """Lista de quadros {osso: matriz no espaço da armadura} do clipe ``spec`` no esqueleto ``rig``."""
    scene = bpy.context.scene
    src, action = load_source(spec['source'])
    length = (action.frame_range[1] - action.frame_range[0]) / SOURCE_FPS
    start = spec['start']
    end = spec['end'] if spec['end'] is not None else length
    duration = spec['duration'] or (end - start)
    count = max(2, round(duration * FPS))
    bones = hierarchy(rig)
    rest = {b.name: b.matrix_local.copy() for b in bones}
    to_src = {t: s for s, t in UNREAL.items()}
    src_world = src.matrix_world
    src_rest = {b.name: src_world @ b.matrix_local for b in src.data.bones}
    # Alinha a direção de repouso de cada osso do alvo com a do osso de origem.
    align = {}
    for bone in bones:
        s = to_src.get(bone.name)
        if s is None:
            continue
        dt = (rotation(rest[bone.name]) @ Vector((0, 1, 0))).normalized()
        ds = (rotation(src_rest[s]) @ Vector((0, 1, 0))).normalized()
        align[bone.name] = dt.rotation_difference(ds).to_matrix()
    hip_ratio = rest['hips'].translation.z / src_rest['pelvis'].translation.z
    frames = []
    for i in range(count + 1):
        t = start + (end - start) * i / count
        f = action.frame_range[0] + t * SOURCE_FPS
        scene.frame_set(int(math.floor(f)), subframe=f - math.floor(f))
        posed = {pb.name: src_world @ pb.matrix for pb in src.pose.bones}
        world = {}
        for bone in bones:
            name = bone.name
            parent = bone.parent.name if bone.parent else None
            if parent is None:
                origin = rest[name].translation + (posed['pelvis'].translation - src_rest['pelvis'].translation) \
                    * hip_ratio
            else:
                origin = (world[parent] @ rest[parent].inverted() @ rest[name]).translation
            s = to_src.get(name)
            if s is None:
                world[name] = world[parent] @ rest[parent].inverted() @ rest[name]
                continue
            delta = rotation(posed[s]) @ rotation(src_rest[s]).transposed()
            rot = delta @ align[name] @ rotation(rest[name])
            world[name] = Matrix.Translation(origin) @ rot.to_4x4()
        frames.append(world)
    bpy.data.objects.remove(src, do_unlink=True)
    bpy.data.actions.remove(action)
    if spec['close']:
        close_loop(frames, spec['close'])
    if spec['life']:
        add_life(rig, frames, spec['life'])
    if spec['loop']:
        frames[-1] = {k: m.copy() for k, m in frames[0].items()}
    return frames


def turn(rig, frame, name, axis, angle):
    """Gira o osso em torno da própria cabeça num eixo do espaço da armadura (filhos acompanham)."""
    head = frame[name].translation
    r = Matrix.Rotation(angle, 4, Vector(axis))
    set_world(rig, frame, name, Matrix.Translation(head) @ r @ Matrix.Translation(-head) @ frame[name])


def add_life(rig, frames, amount):
    """Respiração (peito sobe e abre) e um olhar lento para os lados, em ciclo fechado com o clipe."""
    n = len(frames) - 1
    for i, frame in enumerate(frames):
        p = math.tau * i / n
        breath = math.sin(p)
        turn(rig, frame, 'spine.1', (1, 0, 0), -.018 * amount * breath)
        turn(rig, frame, 'chest', (1, 0, 0), -.022 * amount * breath)
        turn(rig, frame, 'neck', (1, 0, 0), .025 * amount * breath)
        turn(rig, frame, 'head', (0, 0, 1), .16 * amount * math.sin(p + .9))
        turn(rig, frame, 'head', (1, 0, 0), .05 * amount * math.sin(2 * p + .4))
        for side, s in (('L', 1), ('R', -1)):
            turn(rig, frame, f'shoulder.{side}', (0, 1, 0), s * .02 * amount * breath)


def blend_matrix(a, b, k):
    qa, qb = a.to_quaternion(), b.to_quaternion()
    return Matrix.Translation(a.translation.lerp(b.translation, k)) @ qa.slerp(qb, k).to_matrix().to_4x4()


def close_loop(frames, fraction):
    """Funde o último trecho no começo do clipe para o ciclo não pular."""
    n = len(frames)
    span = max(2, int(n * fraction))
    for j in range(span):
        i = n - span + j
        k = (j + 1) / span
        k = k * k * (3 - 2 * k)
        frames[i] = {name: blend_matrix(m, frames[0][name], k) for name, m in frames[i].items()}


def set_world(rig, frame, name, matrix):
    """Move o osso e leva junto toda a sub-árvore (filhos acompanham rigidamente)."""
    delta = matrix @ frame[name].inverted()

    def walk(bone):
        frame[bone.name] = delta @ frame[bone.name]
        for child in bone.children:
            walk(child)
    walk(rig.data.bones[name])


def rotate_to(m, head, target):
    """Gira a matriz do osso (sem trocar a cabeça) para o eixo Y apontar para ``target``."""
    rot = rotation(m)
    y = rot @ Vector((0, 1, 0))
    q = y.rotation_difference((target - head).normalized()).to_matrix()
    return Matrix.Translation(head) @ (q @ rot).to_4x4()


def arm_ik(rig, frame, side, hand_matrix):
    """IK de dois ossos: punho no alvo, cotovelo no plano do cotovelo atual; mão com a rotação dada."""
    upper, lower, hand = f'upper_arm.{side}', f'forearm.{side}', f'hand.{side}'
    a = rig.data.bones[upper].length
    b = rig.data.bones[lower].length
    shoulder = frame[upper].translation.copy()
    elbow_hint = frame[lower].translation.copy()
    wrist = hand_matrix.translation.copy()
    d = wrist - shoulder
    reach = min(d.length, a + b - 1e-4)
    axis = d.normalized()
    pole = elbow_hint - shoulder
    pole = (pole - axis * axis.dot(pole))
    pole = pole.normalized() if pole.length > 1e-6 else Vector((0, 1, -.2)).normalized()
    along = (a * a - b * b + reach * reach) / (2 * reach)
    elbow = shoulder + axis * along + pole * math.sqrt(max(0.0, a * a - along * along))
    set_world(rig, frame, upper, rotate_to(frame[upper], shoulder, elbow))
    set_world(rig, frame, lower, rotate_to(frame[lower], elbow, shoulder + axis * reach))
    set_world(rig, frame, hand, Matrix.Translation(shoulder + axis * reach) @ rotation(hand_matrix).to_4x4())
    return (wrist - (shoulder + axis * reach)).length


def palm(frame, side):
    """Centro da palma: entre o punho e a base do dedo médio."""
    return frame[f'hand.{side}'].translation.lerp(frame[f'middle.1.{side}'].translation, .6)


# ---------------------------------------------------------------------------------------
# Ciclo dos passos
# ---------------------------------------------------------------------------------------

def foot_forward(frame, side):
    """Quanto o pé está à frente do quadril (frente = -Y)."""
    return frame['hips'].translation.y - frame[f'foot.{side}'].translation.y


def align_cycle(frames):
    """Começa o ciclo no quadro em que o pé esquerdo está mais à frente (contato) e mede a passada."""
    body = frames[:-1]
    reach = [foot_forward(f, 'L') for f in body]
    first = max(range(len(body)), key=reach.__getitem__)
    body = body[first:] + body[:first]
    stride = 2 * (max(reach) - min(reach))
    return body + [{k: m.copy() for k, m in body[0].items()}], stride


# ---------------------------------------------------------------------------------------
# Adereços: arma da Célula B e caixa da hemácia
# ---------------------------------------------------------------------------------------

def gun_frame(grip, fore):
    """Matriz da arma no espaço da armadura: origem na mão direita, cano de ``grip`` para ``fore``.
    Eixos locais (Blender): +X esquerda da arma, -Y cano, +Z cima (o glTF vira +X, +Z cano, +Y cima)."""
    barrel = (fore - grip).normalized()
    up = Vector((0, 0, 1))
    up = (up - barrel * barrel.dot(up)).normalized()
    left = up.cross(barrel)
    return Matrix.Translation(grip) @ Matrix((left, -barrel, up)).transposed().to_4x4()


def rig_weapon(rig, clips, legs_only=()):
    """Soquete da arma preso à mão direita (pose do Rifle Idle) e mão esquerda no guarda-mão em todos
    os clipes, menos no meio da recarga, quando ela busca o carregador. Os clipes ``legs_only`` só
    comandam quadril e pernas no jogo: os braços deles não importam."""
    idle = clips['Idle'][0]
    gun = gun_frame(palm(idle, 'R'), palm(idle, 'L'))
    offset = idle['hand.R'].inverted() @ gun
    left = gun.inverted() @ idle['hand.L']
    rest = rig.data.bones['hand.R'].matrix_local @ offset
    add_bone(rig, 'socket_weapon', 'hand.R', Matrix.Translation(rest.translation))
    worst = {}
    for name, frames in clips.items():
        n = len(frames) - 1
        for i, frame in enumerate(frames):
            u = i / max(1, n)
            socket = frame['hand.R'] @ offset
            frame['socket_weapon'] = Matrix.Translation(socket.translation) @ rotation(socket).to_4x4()
            hold = 0.0 if name in legs_only else 1.0
            if name == 'Reload':
                hold = 1 - smooth(.12, .22, u) * (1 - smooth(.78, .9, u))
            elif name == 'Melee':
                hold = 1 - smooth(.15, .35, u) * (1 - smooth(.7, .95, u))
            if hold > 0:
                target = blend_matrix(frame['hand.L'], socket @ left, hold)
                gap = arm_ik(rig, frame, 'L', target) * hold
                worst[name] = max(worst.get(name, 0.0), gap)
    fore = (gun.inverted() @ palm(idle, 'L'))
    gaps = ', '.join(f'{k} {v:.3f}' for k, v in worst.items())
    print(f'    arma: guarda-mão a {fore.length:.3f} m do cabo; folga da mão esquerda (m): {gaps}', flush=True)
    return rest


BOX_SIZE = Vector((.30, .22, .20))   # largura, profundidade, altura (m)
# Centro da caixa no quadro 0 do Carry (espaço da armadura; Y medido a partir do quadril): na cintura,
# encostada na barriga e um pouco para a direita da hemácia (-X), levemente inclinada, como no key
# visual (caixa leve).
BOX_CENTER = Vector((-.035, -.205, 1.045))
BOX_TILT = (math.radians(7), math.radians(-10))   # rolagem (eixo da frente) e guinada


def build_box(rig, collection, clips, key):
    """Caixa de oxigênio presa ao osso ``box`` (filho do peito) no Carry.

    O Carry baixado (``walk-carry``) é de carga pesada: tronco para trás, joelhos dobrados, braços
    esticados. Aqui só aproveitamos a pegada das mãos dele (palmas nas laterais da caixa) e montamos uma
    pose leve: caixa na cintura, rente ao corpo, cotovelos soltos. No jogo o Carry é uma camada ``arms``
    (ombros, braços e caixa relativos ao peito), então tronco, cabeça e pernas seguem a caminhada."""
    frames = clips['Carry']
    ref = retarget(rig, clip('walk-carry'))[0]

    def between_palms(frame):
        lp, rp = palm(frame, 'L'), palm(frame, 'R')
        x = (lp - rp).normalized()
        z = Vector((0, 0, 1))
        z = (z - x * x.dot(z)).normalized()
        y = z.cross(x)
        return Matrix.Translation((lp + rp) / 2) @ Matrix((x, y, z)).transposed().to_4x4()

    # Mãos relativas à caixa na pegada de referência, abertas/fechadas para a largura da nossa caixa.
    ref_box = between_palms(ref)
    ref_half = (palm(ref, 'L') - palm(ref, 'R')).length / 2
    grip = {}
    for side, sign in (('L', 1), ('R', -1)):
        local = ref_box.inverted() @ ref[f'hand.{side}']
        local.translation.x += sign * (BOX_SIZE.x / 2 + .012 - ref_half)
        grip[side] = local

    first = frames[0]
    chest0 = first['chest']
    roll, yaw = BOX_TILT
    tilt = Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(roll, 4, 'Y')
    center = BOX_CENTER + Vector((0, first['hips'].translation.y, 0))
    box0 = Matrix.Translation(center) @ tilt
    box_on_chest = chest0.inverted() @ box0
    worst = 0.0
    for frame in frames:
        box = frame['chest'] @ box_on_chest
        frame['box'] = box
        for side in ('L', 'R'):
            worst = max(worst, arm_ik(rig, frame, side, box @ grip[side]))
    print(f'    caixa: folga das mãos {worst:.3f} m', flush=True)

    rest = box0
    add_bone(rig, 'box', 'chest', rest)
    rest_on_chest = rig.data.bones['chest'].matrix_local.inverted() @ rest
    for name, clip_frames in clips.items():
        if name != 'Carry':
            for frame in clip_frames:
                frame['box'] = frame['chest'] @ rest_on_chest
    size = BOX_SIZE
    mesh = bpy.data.meshes.new(f'{key}.box')
    hx, hy, hz = size / 2
    verts = [rest @ Vector((sx * hx, sy * hy, sz * hz)) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    mesh.from_pydata([tuple(v) for v in verts], [], faces)
    mesh.update()
    colors = mesh.color_attributes.new('Base', 'BYTE_COLOR', 'CORNER')
    # Branco com uma faixa azul na frente e etiqueta vermelha em cima (caixa de oxigênio do anime).
    white, blue, red = (0.86, 0.9, 0.93, 1), (0.22, 0.52, 0.79, 1), (0.8, 0.18, 0.15, 1)
    for poly in mesh.polygons:
        n = (rest.to_3x3().inverted() @ poly.normal)
        tint = blue if n.y < -.5 else red if n.z > .5 else white
        for li in poly.loop_indices:
            colors.data[li].color = tint
    material = bpy.data.materials.new(f'{key}_caixa')
    mesh.materials.append(material)
    box = bpy.data.objects.new(f'{key}.box', mesh)
    collection.objects.link(box)
    box.parent = rig
    box.vertex_groups.new(name='box').add(range(len(verts)), 1.0, 'REPLACE')
    box.modifiers.new('Armature', 'ARMATURE').object = rig
    return box


def smooth(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------------------------------
# Ações
# ---------------------------------------------------------------------------------------

def bake(rig, name, frames):
    bones = hierarchy(rig)
    rest = {b.name: b.matrix_local for b in bones}
    anim = rig.animation_data_create()
    old = bpy.data.actions.get(name)
    if old is not None:
        bpy.data.actions.remove(old)
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    anim.action = action
    previous = {}
    for index, world in enumerate(frames):
        for bone in bones:
            pb = rig.pose.bones[bone.name]
            if bone.parent is None:
                basis = rest[bone.name].inverted() @ world[bone.name]
            else:
                p = bone.parent.name
                basis = (rest[p].inverted() @ rest[bone.name]).inverted() @ world[p].inverted() @ world[bone.name]
            loc, rot, _ = basis.decompose()
            if bone.name in previous and rot.dot(previous[bone.name]) < 0:
                rot.negate()
            previous[bone.name] = rot
            pb.location, pb.rotation_quaternion = loc, rot
            pb.keyframe_insert('location', frame=index, group=bone.name)
            pb.keyframe_insert('rotation_quaternion', frame=index, group=bone.name)
    anim.action = None
    return action


def export(key, spec, rig, meshes, strides, socket_rest):
    from build_characters import CONVENTION, read_glb, raylib_mesh_indices, to_gltf

    bpy.ops.object.select_all(action='DESELECT')
    for obj in [rig, *meshes]:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = rig
    path = OUT / f'{key}.glb'
    scene = bpy.context.scene
    scene.render.fps = FPS
    bpy.ops.export_scene.gltf(
        filepath=str(path), export_format='GLB', use_selection=True,
        export_vertex_color='ACTIVE', export_animation_mode='ACTIONS',
        export_anim_single_armature=True, export_anim_slide_to_zero=True,
        export_frame_range=False, export_animations=True, export_skins=True, export_morph=False,
    )
    gltf, _ = read_glb(path)
    mapping, count = raylib_mesh_indices(gltf)
    clips = [a['name'] for a in gltf['animations']]
    if set(clips) != set(spec['clips']):
        raise ValueError(f'{key}: clipes exportados {clips}')
    primitives = [p for m in gltf['meshes'] for p in m['primitives']]
    for p in primitives:
        if gltf['accessors'][p['attributes']['POSITION']]['count'] > 65535:
            raise ValueError(f'{key}: malha com mais de 65535 vértices')
    meta = {
        'key': key, 'height': spec['height'], 'convention': CONVENTION, 'mesh_count': count,
        'triangles': sum(gltf['accessors'][p['indices']]['count'] // 3 for p in primitives),
        'clips': clips,
        'loops': sorted(n for n, c in spec['clips'].items() if c['loop']),
        'layers': {n: c['layer'] for n, c in spec['clips'].items() if c['layer'] != 'full'},
        'strides': {n: round(s, 3) for n, s in strides.items()},
        'source': 'Tripo + Mesh2Motion (CC0), referencias/scripts/personagens/tripo_characters.py',
        'parts': [{'name': obj.name.split('.', 1)[1], 'mesh': mapping[obj.name][0], 'pivot': [0, 0, 0],
                   'parent': 'body', 'swing': 'static'} for obj in meshes],
    }
    if socket_rest is not None:
        x, y, z = to_gltf(socket_rest.translation)
        meta['mount'] = {'part': 'body', 'bone': 'socket_weapon',
                         'matrix': [[1, 0, 0, x], [0, 1, 0, y], [0, 0, 1, z]]}
    path.with_suffix('.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f'{key:15s} tris={meta["triangles"]} meshes={count} clips={clips} strides={meta["strides"]}',
          flush=True)


def build(key):
    spec = CHARACTERS[key]
    print(f'== {key}', flush=True)
    rig, body = import_model(key, spec)
    clips = {}
    for name, c in spec['clips'].items():
        clips[name] = retarget(rig, c)
    strides = {}
    for name in LOCOMOTION:
        if name in clips:
            clips[name], strides[name] = align_cycle(clips[name])
    meshes = [body]
    socket_rest = None
    if spec.get('weapon'):
        socket_rest = rig_weapon(rig, clips, {n for n, c in spec['clips'].items() if c['layer'] == 'lower'})
    if spec.get('prop') == 'box':
        meshes.append(build_box(rig, body.users_collection[0], clips, key))
    for name, frames in clips.items():
        bake(rig, name, frames)
    rig.animation_data.action = bpy.data.actions['Idle']
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 0, len(clips['Idle']) - 1
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND / f'{key}.blend'))
    export(key, spec, rig, meshes, strides, socket_rest)


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    keys = list(CHARACTERS)
    if '--only' in argv:
        keys = argv[argv.index('--only') + 1].split(',')
    for key in keys:
        build(key)


if __name__ == '__main__':
    main()
