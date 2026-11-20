"""Animador de esqueleto (UserComponents/cells/animation.py) sem GPU: esqueleto e clipes sintéticos."""
import math
import types
import unittest
from unittest import mock

import numpy as np

from UserComponents.cells import animation
from UserComponents.cells.animation import Animator, RigAnimation

ffi = animation._ffi
# Ossos: quadril (raiz), coluna -> cabeça, coxa, peito -> braço. A coluna é o tronco ("upper"); quadril e
# coxa, "lower"; o braço (filho do peito), "arms".
NAMES = ('hips', 'spine', 'head', 'thigh.L', 'chest', 'arm.L')
PARENTS = (-1, 0, 1, 0, 1, 4)
POSITIONS = ((0, 1, 0), (0, 1.2, 0), (0, 1.6, 0), (.1, .9, 0), (0, 1.4, 0), (.2, 1.45, 0))


def axis_angle(axis, angle):
    s = math.sin(angle / 2)
    return (axis[0] * s, axis[1] * s, axis[2] * s, math.cos(angle / 2))


class SyntheticRig:
    def __init__(self):
        self.keep = []
        model = ffi.new('Model *')
        bones = ffi.new('BoneInfo[]', len(NAMES))
        for i, (name, parent) in enumerate(zip(NAMES, PARENTS)):
            bones[i].name = name.encode()
            bones[i].parent = parent
        model.skeleton.boneCount = len(NAMES)
        model.skeleton.bones = bones
        self.keep += [model, bones]
        clips = {
            'Idle': self.clip(lambda f, n: {}, 61),
            # Coxa balança no ciclo; coluna levemente girada.
            'Walk': self.clip(lambda f, n: {3: ((1, 0, 0), .5 * math.sin(math.tau * f / (n - 1))),
                                            1: ((0, 1, 0), .2), 4: ((0, 1, 0), .2), 5: ((0, 1, 0), .2)}, 61),
            # Disparo: tronco gira; a coxa do clipe também (deve ser ignorada pela camada "upper").
            'Fire': self.clip(lambda f, n: {1: ((0, 1, 0), .5), 3: ((1, 0, 0), .9)}, 31),
            # Carregar: braço erguido; o tronco do clipe fica reto (não deve endireitar o da caminhada).
            'Carry': self.clip(lambda f, n: {5: ((1, 0, 0), .7)}, 31),
        }
        self.anim = RigAnimation(model, clips, {'loops': ['Idle', 'Walk', 'Carry'], 'strides': {'Walk': 1.2},
                                                'layers': {'Carry': 'arms'}})

    def clip(self, rotations, frames):
        anim = ffi.new('ModelAnimation *')
        poses = ffi.new('Transform *[]', frames)
        for f in range(frames):
            pose = ffi.new('Transform[]', len(NAMES))
            rot = rotations(f, frames)
            for i, p in enumerate(POSITIONS):
                pose[i].translation.x, pose[i].translation.y, pose[i].translation.z = p
                q = axis_angle(*rot[i]) if i in rot else (0, 0, 0, 1)
                pose[i].rotation.x, pose[i].rotation.y, pose[i].rotation.z, pose[i].rotation.w = q
                pose[i].scale.x = pose[i].scale.y = pose[i].scale.z = 1
            poses[f] = pose
            self.keep.append(pose)
        anim.boneCount, anim.keyframeCount, anim.keyframePoses = len(NAMES), frames, poses
        self.keep += [anim, poses]
        return anim[0]

    def pose(self, animator):
        with mock.patch.object(animation, '_raw', types.SimpleNamespace(UpdateModelAnimation=lambda *a: None)):
            animator.apply(self)
        return self.anim._out[:, 3:7].copy()


def angle(q):
    return 2 * math.acos(min(1.0, abs(float(q[3]))))


class AnimatorTests(unittest.TestCase):
    def setUp(self):
        self.rig = SyntheticRig()

    def test_upper_layer_keeps_locomotion_legs(self):
        an = Animator()
        for i in range(30):
            an.update(self.rig, i / 60, 0.0, events={'Fire': .25})
        q = self.rig.pose(an)
        self.assertAlmostEqual(angle(q[1]), .5, places=2)  # tronco do disparo
        self.assertAlmostEqual(angle(q[3]), 0.0, places=3)  # coxa continua no Idle

    def test_start_and_stop_blend_without_pops(self):
        """Andar/parar alternando a cada 4 quadros: a coxa nunca salta de um quadro para o outro."""
        an = Animator()
        previous, worst = None, 0.0
        for i in range(240):
            an.update(self.rig, i / 60, 3.0 if (i // 4) % 2 else 0.0)
            q = self.rig.pose(an)[3]
            if previous is not None:
                worst = max(worst, abs(angle(q) - angle(previous)))
            previous = q
        # A troca seca Idle<->Walk saltava até 0,5 rad; o próprio balanço da coxa na cadência máxima
        # (1,7 ciclo/s) chega a ~0,09 rad por quadro.
        self.assertLess(worst, .1)

    def test_restarted_action_crossfades(self):
        """Disparo reiniciado a cada 0,2 s (antes do fim do clipe): o tronco não volta de golpe."""
        an = Animator()
        previous, worst = None, 0.0
        for i in range(120):
            t = i / 60
            an.update(self.rig, t, 0.0, events={'Fire': t % .2})
            q = self.rig.pose(an)[1]
            if previous is not None and i > 12:
                worst = max(worst, abs(angle(q) - angle(previous)))
            previous = q
        self.assertLess(worst, .08)

    def test_arms_layer_follows_locomotion_chest(self):
        an = Animator()
        for i in range(30):
            an.update(self.rig, i / 60, 1.2, walk=1.0, layers={'Carry': 1.0})
        q = self.rig.pose(an)
        self.assertAlmostEqual(angle(q[1]), .2, places=3)  # tronco continua na caminhada
        # Braço = giro do peito da caminhada composto com o braço erguido do Carry.
        expected = animation.qmul(np.array(axis_angle((0, 1, 0), .2)), np.array(axis_angle((1, 0, 0), .7)))
        self.assertTrue(np.allclose(q[5], expected, atol=1e-3) or np.allclose(q[5], -expected, atol=1e-3), q[5])

    def test_cycle_follows_distance(self):
        an = Animator()
        for i in range(61):
            an.update(self.rig, i / 60, 1.2)
        # 1,2 m/s com passada de 1,2 m: um ciclo por segundo (dentro dos limites de cadência).
        self.assertLess(min(an.cycle, 1 - an.cycle), .03)


if __name__ == '__main__':
    unittest.main()
