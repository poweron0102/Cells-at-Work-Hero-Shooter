"""Anima a Macrófaga (terceira pessoa) na cena de autoria e regrava as ações do esqueleto.

Uso (a partir da raiz do repositório; depois rode export_macrophage.py para gerar os GLBs):

    & 'C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe' --background `
        referencias\\blender\\macrophage.blend --python referencias\\scripts\\personagens\\animate_macrophage.py

O que faz, sobre ``referencias/blender/macrophage.blend``:

* adiciona os ossos dos dedos (``macrophage_fingers.py``) se ainda não existirem;
* refaz as oito ações (Idle, Walk, Run, Jump, Land, Fire, Reload, Melee) quadro a quadro: corpo,
  saia e trança como antes; as mãos agora seguram de verdade — a direita fecha em volta do cabo com
  o indicador no gatilho, a esquerda por baixo da bomba;
* recarga nova (1,6 s, mesma coreografia da primeira pessoa): a arma desce para a cintura, a mão
  esquerda pega um cartucho na cintura, empurra na janela de carga sob a caixa, repete e bombeia.
  A mão nunca passa na frente do rosto;
* remove os braços rígidos antigos da coleção da arma (a primeira pessoa usa ``fp_arms``);
* regrava as ações de prévia da bomba e salva o arquivo.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import macrophage_fingers as fingers  # noqa: E402

FPS = 30
DURATIONS = {'Idle': 3.0, 'Walk': 1.0, 'Run': .73, 'Jump': .57, 'Land': .28,
             'Fire': .5, 'Reload': 1.6, 'Melee': .42}
LOOPS = {'Idle', 'Walk', 'Run'}

# Espaço da arma (Blender: +X esquerda, -Y frente, Z cima; origem = mão direita no cabo).
GRIP_C, GRIP_AXIS, GRIP_PALM, GRIP_R = (0.0, -0.008, -0.028), (0.0, -0.215, 0.977), (-0.93, 0.36, 0.0), 0.03
PUMP_C, PUMP_R = (0.004, -0.34, 0.071), 0.042  # metade de trás da bomba (o braço dela é curto)
PORT, PORT_IN, SHELL_R = (0.006, -0.14, -0.03), (0.004, -0.17, 0.0), 0.012
PUMP_TRAVEL = 0.075
# Onde o cabo encosta na palma, no espaço do osso da mão (o osso corre pela borda do dedo mínimo):
# ao longo da mão, para o lado do polegar e profundidade da palma (o dorso é +Z).
WRIST_TO_PALM, PALM_SIDE, PALM_DEPTH = 0.072, 0.026, 0.034

# Fechamento dos dedos (rad, negativo = para a palma): (base, ponta) por dedo e polegar.
CURL = {
    'grip': {'index': (-.6, -.55), 'middle': (-1.0, -1.05), 'ring': (-1.05, -1.1), 'pinky': (-1.05, -1.1),
             'thumb': (-.4, -.55)},
    'pump': {'index': (-.8, -.85), 'middle': (-.85, -.9), 'ring': (-.9, -.95), 'pinky': (-.9, -.95),
             'thumb': (-.25, -.35)},
    'shell': {'index': (-1.2, -1.25), 'middle': (-1.45, -1.4), 'ring': (-1.5, -1.45), 'pinky': (-1.5, -1.45),
              'thumb': (-.55, -.75)},
    'open': {'index': (-.2, -.25), 'middle': (-.3, -.3), 'ring': (-.35, -.35), 'pinky': (-.4, -.4),
             'thumb': (-.1, -.15)},
}
# Mão esquerda na recarga: (tempo 0..1, alvo). Igual à primeira pessoa (UserComponents/cells/fp_arms.py).
RELOAD_LEFT = [(0.0, 'pump'), (0.08, 'pump'), (0.19, 'pouch'), (0.31, 'port'), (0.34, 'port'),
               (0.40, 'port_in'), (0.42, 'port_in'), (0.51, 'pouch'), (0.62, 'port'), (0.65, 'port'),
               (0.71, 'port_in'), (0.73, 'port_in'), (0.82, 'pump')]


def v(*c):
    return Vector(c)


def smooth(a, b, x):
    if b == a:
        return 1.0 if x >= b else 0.0
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def bell(a, b, c, d, x):
    return smooth(a, b, x) * (1 - smooth(c, d, x))


def pump_travel(fire, reload):
    """Curso da bomba (0..1): depois do disparo e no fim da recarga. Igual a weapons.shotgun_state."""
    k = bell(.16, .26, .30, .42, fire)
    return k if reload is None else max(k, bell(.84, .89, .92, .98, reload))


def hand_frame(palm_dir, axis, tilt, right):
    """(dedos, dorso) de uma mão segurando um cilindro de eixo ``axis``, com a palma do lado
    ``palm_dir``. tilt (rad) gira os dedos sobre o dorso."""
    z = palm_dir.normalized()
    a = (axis - z * axis.dot(z)).normalized()
    y = a.cross(z) if right else z.cross(a)
    y = Quaternion(z, tilt) @ y
    return y.normalized(), z


def hand_at(center, palm_dir, radius, y, z, right):
    """Punho para a palma encostar no cilindro (centro, raio) com a mão orientada (y, z)."""
    x = y.cross(z)
    side = -PALM_SIDE if right else PALM_SIDE  # X aponta para o polegar na esquerda e para longe na direita
    return center + palm_dir.normalized() * radius + z * PALM_DEPTH - y * WRIST_TO_PALM - x * side


def reach_clavicle(rig, upper, lower, target):
    """Se o punho não alcança o alvo, a clavícula gira para a frente (até ~25°) para ganhar alcance."""
    bones = rig.pose.bones
    clav = bones[upper].parent
    length = bones[upper].length + bones[lower].length - .008
    for _ in range(3):
        to = target - bones[upper].head
        deficit = to.length - length
        if deficit <= 0.002 or clav is None:
            return
        d = (clav.tail - clav.head).normalized()
        axis = d.cross((target - clav.head).normalized())
        if axis.length < 1e-6:
            return
        angle = min(.45, deficit / clav.length * 1.1)
        rot = Quaternion(axis.normalized(), angle)
        m = clav.matrix.copy()
        clav.matrix = Matrix.Translation(m.to_translation()) @ (rot @ m.to_quaternion()).to_matrix().to_4x4()
        bpy.context.view_layer.update()


def arm_position(rig, upper, lower, hand, target, pole, finger_dir, dorsal):
    """IK de dois ossos no plano ombro-punho-polo; a mão fica com Y = dedos e Z = dorso."""
    reach_clavicle(rig, upper, lower, target)
    bones = rig.pose.bones
    upper, lower, hand = bones[upper], bones[lower], bones[hand]
    shoulder = upper.head.copy()
    direction = target - shoulder
    length = min(direction.length, upper.length + lower.length - .008)
    axis = direction.normalized()
    off_axis = pole - shoulder
    off_axis = (off_axis - axis * axis.dot(off_axis)).normalized()
    along = (upper.length ** 2 - lower.length ** 2 + length ** 2) / (2 * length)
    elbow = shoulder + axis * along + off_axis * math.sqrt(max(0, upper.length ** 2 - along ** 2))
    wrist = shoulder + length * axis
    for bone, pos, aim in ((upper, shoulder, elbow), (lower, elbow, wrist)):
        rotation = bone.matrix.to_quaternion()
        rotation = (rotation @ v(0, 1, 0)).rotation_difference((aim - pos).normalized()) @ rotation
        bone.matrix = Matrix.Translation(pos) @ rotation.to_matrix().to_4x4()
        bpy.context.view_layer.update()
    y = finger_dir.normalized()
    z = (dorsal - y * dorsal.dot(y)).normalized()
    hand.matrix = Matrix.Translation(wrist) @ Matrix((y.cross(z), y, z)).transposed().to_4x4()
    bpy.context.view_layer.update()


def leg_position(rig, side, target, pitch):
    a, b, foot = (rig.pose.bones[f'{part}.{side}'] for part in ('thigh', 'shin', 'foot'))
    hip = a.head.copy()
    d = target - hip
    length = min(d.length, a.length + b.length - .002)
    axis = d.normalized()
    forward = v(0, -1, 0)
    pole = (forward - axis * axis.dot(forward)).normalized()
    along = (a.length ** 2 - b.length ** 2 + length ** 2) / (2 * length)
    knee = hip + axis * along + pole * math.sqrt(max(0, a.length ** 2 - along ** 2))
    ankle = hip + axis * length
    for bone, pos, aim in ((a, hip, knee), (b, knee, ankle)):
        rest = bone.bone.matrix_local.to_quaternion()
        rotation = (rest @ v(0, 1, 0)).rotation_difference((aim - pos).normalized()) @ rest
        bone.matrix = Matrix.Translation(pos) @ rotation.to_matrix().to_4x4()
        bpy.context.view_layer.update()
    rotation = Matrix.Rotation(pitch, 4, 'X') @ foot.bone.matrix_local.to_quaternion().to_matrix().to_4x4()
    foot.matrix = Matrix.Translation(ankle) @ rotation
    bpy.context.view_layer.update()


def rotate_world(pose_bone, angles):
    q = pose_bone.bone.matrix_local.to_quaternion()
    pose_bone.rotation_quaternion = q.inverted() @ Euler(angles).to_quaternion() @ q


def curl(rig, side, pose):
    for name in fingers.FINGERS + ('thumb',):
        base, tip = pose[name]
        rig.pose.bones[f'{name}.1.{side}'].rotation_quaternion = Quaternion((1, 0, 0), base)
        rig.pose.bones[f'{name}.2.{side}'].rotation_quaternion = Quaternion((1, 0, 0), tip)


def mix_curl(a, b, k, open_k=0.0):
    out = {}
    for name in a:
        pair = tuple(x + (y - x) * k for x, y in zip(a[name], b[name]))
        out[name] = tuple(x + (o - x) * open_k for x, o in zip(pair, CURL['open'][name]))
    return out


def left_track(p):
    keys = RELOAD_LEFT
    if p is None or p <= keys[0][0]:
        return keys[0][1], keys[0][1], 1.0
    for (t0, g0), (t1, g1) in zip(keys, keys[1:]):
        if p < t1:
            return g0, g1, smooth(t0, t1, p)
    return keys[-1][1], keys[-1][1], 1.0


def apply_pose(rig, clip, seconds, duration):
    b = rig.pose.bones
    for bone in b:
        bone.matrix_basis.identity()
    u = seconds / duration
    p = math.tau * u
    moving = clip in ('Walk', 'Run')
    run = clip == 'Run'
    stride = (.35 if run else .255) if moving else 0
    w = math.sin(p) if moving else 0
    counter = math.cos(p) if moving else 0
    vertical = (.027 if run else .018) * (1 - math.cos(2 * p)) / 2 if moving else .005 * math.sin(p)
    kick = bell(0, .06, .085, .23, seconds) if clip == 'Fire' else 0
    reload = u if clip == 'Reload' else None
    # Recarga: arma desce para a cintura e inclina mostrando a janela de carga; cabeça olha para ela.
    lower = bell(.0, .12, .86, 1.0, u) if reload is not None else 0
    wind = bell(0, .26, .30, .58, u) if clip == 'Melee' else 0
    chop = bell(.29, .59, .68, 1, u) if clip == 'Melee' else 0
    tuck = smooth(0, .30, u) * (1 - .68 * smooth(.40, .95, u)) if clip == 'Jump' else 0
    land = bell(0, .28, .31, 1, u) if clip == 'Land' else 0

    hip_offset = v(.017 * w + .016 * wind - .018 * chop, .028 * wind - .036 * chop,
                   -.023 + vertical - .012 * lower - .095 * land + .02 * tuck)
    b['hips'].location = b['hips'].bone.matrix_local.to_quaternion().inverted() @ hip_offset
    rotate_world(b['hips'], (-.04 * counter + .10 * land, .04 * w, -.065 * w))
    rotate_world(b['spine'], (.085 if run else .015, -.037 * w, .075 * w))
    rotate_world(b['chest'], (-.07 * kick + .12 * land + .12 * chop + .06 * lower, .034 * counter,
                              .13 * w - .31 * wind + .40 * chop + .12 * lower))
    rotate_world(b['neck'], (.036 * counter + .1 * lower, .023 * w, -.10 * w))
    rotate_world(b['head'], (.027 * math.sin(p) + .2 * lower - .07 * kick, -.04 * w - .11 * wind + .1 * lower,
                             -.03 * w))
    for sector in range(8):
        f = sector * math.pi / 4
        flare = .075 * w * math.cos(f) + .055 * tuck + .08 * land
        rotate_world(b[f'skirt{sector}.0'], (math.cos(f) * flare, math.sin(f) * flare, 0))
        drag = .072 * math.sin(p - .6) * math.cos(f) if moving else .045 * kick * math.cos(f)
        rotate_world(b[f'skirt{sector}.1'], (math.cos(f) * drag, math.sin(f) * drag, .036 * counter))
    bpy.context.view_layer.update()

    for side, s in (('L', 1), ('R', -1)):
        q = (u + (0 if s > 0 else .5)) % 1
        if q < .53:
            travel = -.5 + q / .53
            lift = 0
            toe = .07 * bell(.30, .43, .48, .53, q)
        else:
            f = (q - .53) / .47
            travel = .5 - smooth(0, 1, f)
            lift = math.sin(math.pi * f) ** 1.4
            toe = -.17 * lift
        foot = b[f'foot.{side}'].bone.head_local.copy()
        foot.x += s * (.023 + .025 * land)
        foot.y += stride * travel + (.065 if s > 0 else -.01) * tuck - .075 * chop * (s > 0)
        foot.z += (.16 if run else .105) * lift * moving + (.18 if s > 0 else .10) * tuck
        leg_position(rig, side, foot, toe * moving + .22 * tuck)

    # Arma no soquete (espaço do esqueleto).
    yaw = .72 + .035 * w - .18 * kick - .1 * lower - .75 * wind + .67 * chop
    pitch = -.13 + .04 * counter + .23 * kick + .22 * lower + 1.1 * wind - .63 * chop
    roll = .05 * w - .09 * tuck + .38 * lower - .33 * wind + .50 * chop
    rotation = Euler((pitch, roll, yaw), 'YZX').to_matrix()
    grip = v(-.17 + .019 * w + .06 * lower - .06 * wind + .12 * chop,
             -.1 - .022 * counter + .035 * kick + .01 * lower + .07 * wind - .11 * chop,
             1.19 + vertical - .08 * run + .035 * kick - .13 * lower + .24 * wind - .16 * chop + .07 * tuck
             - .065 * land)
    b['socket_weapon'].matrix = Matrix.Translation(grip) @ rotation.to_4x4()
    bpy.context.view_layer.update()

    def gun(point):
        return grip + rotation @ v(*point)

    def gdir(d):
        return rotation @ v(*d)

    # Mão direita: palma do lado direito do cabo, dedos contornando a frente, indicador no gatilho.
    palm = gdir(GRIP_PALM)
    y, z = hand_frame(palm, gdir(GRIP_AXIS), 0.0, right=True)
    arm_position(rig, 'upper_arm.R', 'forearm.R', 'hand.R', hand_at(gun(GRIP_C), palm, GRIP_R, y, z, True),
                 v(-.48, .06, 1.06), y, z)
    curl(rig, 'R', CURL['grip'])

    # Mão esquerda: bomba, cintura (cartucho) ou janela de carga.
    bolt = pump_travel(seconds if clip == 'Fire' else 9, reload)
    pump_c = v(*PUMP_C) + v(0, PUMP_TRAVEL * bolt, 0)
    under = v(.3, 0, -1)
    pouch_c = b['hips'].head + v(.16, -.05, .14)

    def target(name):
        if name == 'pump':
            palm = gdir(under)
            y, z = hand_frame(palm, gdir((0, -1, 0)), .45, right=False)
            return hand_at(grip + rotation @ pump_c, palm, PUMP_R, y, z, False), y, z, CURL['pump']
        if name in ('port', 'port_in'):
            palm = gdir(under)
            y, z = hand_frame(palm, gdir((0, -1, 0)), .3, right=False)
            return hand_at(gun(PORT if name == 'port' else PORT_IN), palm, SHELL_R, y, z, False), y, z, CURL['shell']
        # Cintura: mão para baixo, dorso para fora, fechada no cartucho.
        y, z = v(.1, -.35, -1).normalized(), v(1, .1, .1).normalized()
        return hand_at(pouch_c, -z, SHELL_R, y, z, False), y, z, CURL['shell']

    g0, g1, k = left_track(reload)
    w0, y0, z0, c0 = target(g0)
    w1, y1, z1, c1 = target(g1)
    left = w0.lerp(w1, k)
    if g0 != g1:
        left += v(.03, -.02, -.05) * math.sin(math.pi * k) if 'pouch' in (g0, g1) else v(0, 0, 0)
    q = Matrix((y0.cross(z0), y0, z0)).transposed().to_quaternion().slerp(
        Matrix((y1.cross(z1), y1, z1)).transposed().to_quaternion(), k)
    ly, lz = q @ v(0, 1, 0), q @ v(0, 0, 1)
    pose_l = mix_curl(c0, c1, k, .6 * math.sin(math.pi * k) if g0 != g1 else 0.0)
    release = max(wind, chop)
    if release:
        left = left.lerp(v(.345, -.26, 1.23) + v(.1, .02, .07) * wind - ly * WRIST_TO_PALM, release)
        ly = ly.lerp(v(-.14, -1, .02), release).normalized()
        pose_l = mix_curl(pose_l, CURL['open'], release)
    arm_position(rig, 'upper_arm.L', 'forearm.L', 'hand.L', left, v(.37, .015, .99), ly, lz)
    curl(rig, 'L', pose_l)
    return b['braid.0'].head.copy(), v(w * .047 + .13 * chop - .15 * wind, .07 * counter + .12 * kick + .12 * land, 0)


def bake_clip(rig, name, duration):
    anim = rig.animation_data_create()
    anim.action = None
    count = round(duration * FPS)
    substeps = 4
    dt = duration / count / substeps
    # A aceleração da cabeça passa da raiz à ponta da trança, cada vez mais mole e atrasada.
    angular = [v(0, 0, 0) for _ in range(4)]
    vel = [v(0, 0, 0) for _ in angular]
    last_head = None
    last_speed = v(0, 0, 0)
    loop = name in LOOPS
    keys = []
    warmup = count * substeps * 3 if loop else 0
    drive = v(0, 0, 0)
    for sample in range(-warmup, count * substeps + 1):
        seconds = sample * dt
        if sample % substeps == 0:
            playhead = seconds % duration if sample < 0 else seconds
            head, bias = apply_pose(rig, name, playhead, duration)
            speed = (head - last_head) / (dt * substeps) if last_head is not None else v(0, 0, 0)
            accel = (speed - last_speed) / (dt * substeps) if last_head is not None else v(0, 0, 0)
            last_head, last_speed = head, speed
            drive = v(-.010 * accel.y + bias.y, -.012 * accel.x + bias.x, .007 * accel.x)
            drive.x = max(-.09, min(.22, drive.x))
            drive.y = max(-.17, min(.17, drive.y))
        for i in range(4):
            goal = drive if i == 0 else angular[i - 1] * 1.16
            stiffness = 188 - i * 27
            vel[i] += ((goal - angular[i]) * stiffness - (22 - i * 2) * vel[i]) * dt
            angular[i] += vel[i] * dt
        if sample >= 0 and sample % substeps == 0:
            for i, angles in enumerate(angular):
                rotate_world(rig.pose.bones[f'braid.{i}'], (angles.x + .025, angles.y, angles.z))
            keys.append([(bn.location.copy(), bn.rotation_quaternion.copy()) for bn in rig.pose.bones])
    if loop:
        keys[-1] = keys[0]
    old = bpy.data.actions.get(name)
    if old is not None:
        bpy.data.actions.remove(old)
    anim.action = bpy.data.actions.new(name)
    anim.action.use_fake_user = True
    prev = {}
    for frame, pose in enumerate(keys):
        for bone, (location, rotation) in zip(rig.pose.bones, pose):
            if bone.name in prev and rotation.dot(prev[bone.name]) < 0:
                rotation.negate()
            prev[bone.name] = rotation
            bone.location, bone.rotation_quaternion = location, rotation
            bone.keyframe_insert('location', frame=frame, group=bone.name)
            bone.keyframe_insert('rotation_quaternion', frame=frame, group=bone.name)
    return anim.action


def preview_parts(actions):
    """Ações de prévia da bomba (coleção macrophage.weapon_preview) no mesmo tempo das do corpo."""
    preview = bpy.data.collections.get('macrophage.weapon_preview')
    if preview is None:
        return
    for obj in preview.objects:
        if obj.name not in ('pump', 'mag'):
            continue
        for name in actions:
            old = bpy.data.actions.get(f'Weapon {obj.name} · {name}')
            if old is not None:
                bpy.data.actions.remove(old)
            anim = obj.animation_data_create()
            anim.action = bpy.data.actions.new(f'Weapon {obj.name} · {name}')
            anim.action.use_fake_user = True
            for frame in range(round(DURATIONS[name] * FPS) + 1):
                t = frame / FPS
                k = pump_travel(t if name == 'Fire' else 9, t / 1.6 if name == 'Reload' else None)
                obj.location = v(0, PUMP_TRAVEL * k, 0) if obj.name == 'pump' else v(0, 0, 0)
                obj.keyframe_insert('location', frame=frame)
        anim.action = bpy.data.actions[f'Weapon {obj.name} · Idle']


def main():
    rig = bpy.data.objects['macrophage.rig']
    body = bpy.data.objects['macrophage.body']
    if fingers.add_fingers(rig, body):
        print('dedos adicionados', flush=True)
    for pb in rig.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    weapon = bpy.data.collections.get('macrophage.weapon')
    if weapon is not None:
        for obj in list(weapon.objects):
            if obj.name.startswith('w_macrophage.arm_'):
                bpy.data.objects.remove(obj, do_unlink=True)
    scene = bpy.context.scene
    scene.render.fps = FPS
    actions = {name: bake_clip(rig, name, duration) for name, duration in DURATIONS.items()}
    preview_parts(actions)
    rig.animation_data.action = actions['Idle']
    scene.frame_start, scene.frame_end = 0, 90
    scene.frame_set(0)
    bpy.ops.wm.save_mainfile()
    print('ações:', ', '.join(actions), flush=True)


if __name__ == '__main__':
    main()
