"""Braços de primeira pessoa com esqueleto (fp_arms): assets e pose, sem GPU."""
import json
import math
import unittest

from UserComponents.cells import fp_arms
from UserComponents.cells.fp_arms import (FINGERS, LIMITS, THUMB_LIMITS, HandRig, cross, dot, length, m_apply,
                                          mv, norm, sub)
from UserComponents.cells.models import raylib_mesh_indices, read_glb
from UserComponents.cells.weapons import ASSET_DIR, m_rows

IDENTITY = (((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), (0.0, 0.0, 0.0))


def det(m):
    return dot(m[0], cross(m[1], m[2]))


def axis_distance(p, grip, space=IDENTITY):
    """Distância de p ao eixo do cilindro da empunhadura (no espaço ``space``)."""
    c = m_apply(space, grip.c)
    u = norm(mv(space[0], grip.axis))
    w = sub(p, c)
    return length(sub(w, tuple(x * dot(w, u) for x in u)))


class ArmsAssetTests(unittest.TestCase):
    def test_glb_and_json_agree(self):
        for hero in fp_arms.HEROES:
            with self.subTest(hero=hero):
                meta = fp_arms.load_meta(hero)
                self.assertIsNotNone(meta)
                gltf, _ = read_glb(ASSET_DIR / f'{hero}_arms.glb')
                _, count = raylib_mesh_indices(gltf)
                self.assertEqual(meta['mesh_count'], count)
                joints = [gltf['nodes'][j]['name'] for j in gltf['skins'][0]['joints']]
                self.assertEqual(sorted(joints), sorted(meta['bones']))
                self.assertEqual(set(meta['rest']), set(meta['bones']))
                for bone, parent in meta['parents'].items():
                    self.assertTrue(parent is None or parent in meta['rest'], bone)
                for side in ('R', 'L'):
                    h = meta['hands'][side]
                    f, n, s = norm(h['forward']), norm(h['normal']), norm(h['thumb'])
                    self.assertAlmostEqual(dot(f, n), 0.0, places=5)
                    self.assertAlmostEqual(abs(dot(cross(f, n), s)), 1.0, places=5)
                    for name in FINGERS + ('thumb',):
                        for k in (1, 2, 3):
                            self.assertIn(f'{name}{k}.{side}', meta['radius'])

    def test_every_hero_with_arms_has_a_choreography(self):
        for hero in fp_arms.HEROES:
            with self.subTest(hero=hero):
                cfg = fp_arms.config(hero)
                grips = cfg['grips']
                self.assertEqual(set(cfg['hold']), {'R', 'L'})
                for side in ('R', 'L'):
                    self.assertIn(cfg['hold'][side], grips)
                for side in ('R', 'L'):
                    keys = cfg['tracks'][side]
                    times = [k.t for k in keys]
                    self.assertEqual(times, sorted(times))
                    self.assertTrue(0.0 <= times[0] and times[-1] <= 1.0)
                    for k in keys:
                        self.assertIn(k.grip, grips)
                        self.assertTrue(k.arc is None or len(k.arc) == 3)
                    # Fim da recarga: mão de volta na empunhadura de repouso.
                    self.assertEqual(keys[-1].grip, cfg['hold'][side])
                self.assertEqual(len(cfg['tilt']), 6)
                start, end = fp_arms.reload_parts(hero, 0.0), fp_arms.reload_parts(hero, 1.0)
                for key in ('mag', 'bolt', 'bump'):
                    self.assertAlmostEqual(start.get(key, 0.0), 0.0, places=6)
                    self.assertAlmostEqual(end.get(key, 0.0), 0.0, places=6)


class HandPoseTests(unittest.TestCase):
    def rigs(self):
        for hero in fp_arms.HEROES:
            meta = fp_arms.load_meta(hero)
            yield hero, {s: HandRig(meta, s) for s in ('R', 'L')}, fp_arms.config(hero)

    def test_palm_rests_on_every_grip(self):
        for hero, rigs, cfg in self.rigs():
            for name, grip in cfg['grips'].items():
                for side, rig in rigs.items():
                    with self.subTest(hero=hero, grip=name, side=side):
                        wrist, rot = rig.place(grip, IDENTITY)
                        self.assertAlmostEqual(det(rot), 1.0, places=6)
                        palm = tuple(w + d for w, d in zip(wrist, mv(rot, sub(rig.palm, rig.W))))
                        self.assertAlmostEqual(axis_distance(palm, grip), grip.r[0], places=6)
                        # A palma olha para o eixo do cilindro.
                        to_axis = sub(m_apply(IDENTITY, grip.c), palm)
                        self.assertGreater(dot(mv(rot, rig.n), to_axis), 0.0)

    def test_fingers_close_within_joint_limits_and_wrap_the_grip(self):
        for hero, rigs, cfg in self.rigs():
            for name, grip in cfg['grips'].items():
                rig = rigs['R' if name == 'grip' else 'L']
                with self.subTest(hero=hero, grip=name):
                    angles = rig.solve(grip)
                    for finger in FINGERS:
                        limits = grip.reach or LIMITS
                        for a, lim in zip(angles[finger], limits):
                            self.assertGreaterEqual(a, 0.0)
                            self.assertLessEqual(a, lim + 1e-9)
                    self.assertEqual(len(angles['thumb']), 4)
                    for a, lim in zip(angles['thumb'][1:], THUMB_LIMITS):
                        self.assertLessEqual(a, lim + 1e-9)
                    # Dedos resolvidos terminam encostados no cilindro (não flutuam longe dele).
                    wrist, rot = rig.place(grip, IDENTITY)
                    for finger in FINGERS:
                        if finger in grip.fix:
                            continue
                        tip = rig.points(finger, rig.deltas(finger, angles[finger]), wrist, rot)[3]
                        r = rig.chains[finger][2][2]
                        self.assertLess(axis_distance(tip, grip), max(grip.r) + r * 2.5, finger)

    def test_arm_reaches_the_wrist_from_an_off_screen_shoulder(self):
        for hero, rigs, cfg in self.rigs():
            fp = m_rows(json.loads((ASSET_DIR / f'{hero}.json').read_text(encoding='utf-8'))['fp'])
            for side, rig in rigs.items():
                with self.subTest(hero=hero, side=side):
                    grip = cfg['grips'][cfg['hold'][side]]
                    wrist, rot = rig.place(grip, fp)
                    bones = {b: (head, r) for b, head, r in
                             rig.bones(wrist, rot, rig.solve(grip), cfg['shoulders'][side], cfg['poles'][side])}
                    shoulder, elbow = bones[rig.upper][0], bones[rig.fore][0]
                    self.assertAlmostEqual(length(sub(elbow, shoulder)), rig.L1, places=5)
                    self.assertAlmostEqual(length(sub(wrist, elbow)), rig.L2, places=5)
                    # Ombro fora da tela (abaixo do campo de visão vertical de 50°).
                    self.assertLess(shoulder[1], -abs(shoulder[2]) * math.tan(math.radians(25)))
                    for _b, (_h, r) in bones.items():
                        self.assertAlmostEqual(det(r), 1.0, places=5)

    def test_reload_track_blends_between_grips(self):
        keys = fp_arms.config('macrophage')['tracks']['L']
        a, b, k = fp_arms.track(keys, None)
        self.assertEqual((a.grip, b.grip, k), ('pump', 'pump', 1.0))
        a, b, k = fp_arms.track(keys, .25)
        self.assertEqual((a.grip, b.grip), ('pouch', 'port'))
        self.assertTrue(0.0 < k < 1.0)
        self.assertTrue(fp_arms.held_shell('macrophage', .3))
        self.assertFalse(fp_arms.held_shell('macrophage', .9))
        self.assertFalse(fp_arms.held_shell('b_cell', .3))


class AnimFileTests(unittest.TestCase):
    def test_saved_file_round_trips(self):
        for hero in fp_arms.HEROES:
            with self.subTest(hero=hero):
                text = fp_arms.anim_path(hero).read_text(encoding='utf-8')
                data = json.loads(text)
                self.assertEqual(json.loads(fp_arms.dump_anim(data)), data)
                fp_arms.parse_config(data)

    def test_key_adjustments_move_and_turn_the_hand(self):
        hero = 'macrophage'
        data = json.loads(fp_arms.anim_path(hero).read_text(encoding='utf-8'))
        data['tracks']['L'][0].update(offset=[0.0, 0.05, 0.0], rot=[0.0, 0.0, 30.0], fingers={'index': [0, 0, 0]})
        base, moved = fp_arms.config(hero), fp_arms.parse_config(data)
        rig = HandRig(fp_arms.load_meta(hero), 'L')
        space = lambda _part: IDENTITY  # noqa: E731
        w0, r0, f0 = fp_arms.key_pose(rig, base['grips'], base['tracks']['L'][0], space)
        w1, r1, f1 = fp_arms.key_pose(rig, moved['grips'], moved['tracks']['L'][0], space)
        self.assertAlmostEqual(w1[1] - w0[1], .05, places=6)
        self.assertAlmostEqual(dot(mv(r0, (0.0, 0.0, 1.0)), mv(r1, (0.0, 0.0, 1.0))), 1.0, places=6)
        self.assertAlmostEqual(dot(mv(r0, (1.0, 0.0, 0.0)), mv(r1, (1.0, 0.0, 0.0))), math.cos(math.radians(30)),
                               places=6)
        self.assertEqual(f1['index'], (0.0, 0.0, 0.0))

    def test_wrist_bends_the_forearm_and_keeps_the_hand(self):
        hero = 'b_cell'
        data = json.loads(fp_arms.anim_path(hero).read_text(encoding='utf-8'))
        base = fp_arms.parse_config(data)
        data['tracks']['L'][0]['wrist'] = [25.0, -10.0]
        bent = fp_arms.parse_config(data)
        rigs = {s: HandRig(fp_arms.load_meta(hero), s) for s in ('R', 'L')}
        space = lambda _part: IDENTITY  # noqa: E731
        b0 = {n: (h, r) for n, h, r in fp_arms.Arms(hero, base).pose(rigs, space)}
        arms = fp_arms.Arms(hero, bent)
        b1 = {n: (h, r) for n, h, r in arms.pose(rigs, space)}
        for name in ('hand.L', 'index3.L', 'thumb2.L', 'hand.R', 'forearm.R'):
            self.assertEqual(b0[name], b1[name], name)
        rig = rigs['L']
        wrist, rot = b1['hand.L']
        # O antebraço sai do punho na direção que dá exatamente o pulso pedido, e torce junto com a mão.
        got = rig.wrist_angles(rot, norm(sub(wrist, b1['forearm.L'][0])))
        self.assertAlmostEqual(got[0], 25.0, places=6)
        self.assertAlmostEqual(got[1], -10.0, places=6)
        self.assertEqual(arms.wrist['L'][0], (25.0, -10.0))
        self.assertAlmostEqual(length(sub(wrist, b1['forearm.L'][0])), rig.L2, places=6)
        self.assertAlmostEqual(length(sub(b1['forearm.L'][0], b1['upperarm.L'][0])), rig.L1, places=6)

    def test_wrist_axes_are_anatomical_on_both_hands(self):
        meta = fp_arms.load_meta('b_cell')
        for side in ('R', 'L'):
            with self.subTest(side=side):
                rig = HandRig(meta, side)
                # Mão em relação ao antebraço: flexão + leva os dedos para o lado da palma, desvio + para
                # o polegar (nas duas mãos).
                self.assertGreater(dot(mv(rig.wrist_matrix((30.0, 0.0)), rig.f), rig.n), .4)
                self.assertGreater(dot(mv(rig.wrist_matrix((0.0, 10.0)), rig.f), rig.s), .1)
                self.assertLess(dot(mv(rig.wrist_matrix((0.0, -30.0)), rig.f), rig.s), -.4)
                for bend in ((0.0, 0.0), (50.0, -40.0), (-40.0, 10.0), (12.5, -7.0)):
                    for rot in (fp_arms.I3, fp_arms.euler_xyz((20.0, -35.0, 70.0))):
                        fore = fp_arms.mm(rot, fp_arms.tr(rig.wrist_matrix(bend)))
                        got = rig.wrist_angles(rot, mv(fore, (0.0, 0.0, 1.0)))
                        self.assertAlmostEqual(got[0], bend[0], places=6)
                        self.assertAlmostEqual(got[1], bend[1], places=6)

    def test_wrist_never_leaves_its_limits(self):
        data = json.loads(fp_arms.anim_path('b_cell').read_text(encoding='utf-8'))
        data['tracks']['R'][0]['wrist'] = [90.0, -90.0, 30.0]  # formato antigo (3 números): torção ignorada
        self.assertEqual(fp_arms.parse_config(data)['tracks']['R'][0].wrist, (50.0, -40.0))
        for hero in fp_arms.HEROES:
            cfg = fp_arms.config(hero)
            meta = fp_arms.load_meta(hero)
            rigs = {s: HandRig(meta, s) for s in ('R', 'L')}
            fp = m_rows(json.loads((ASSET_DIR / f'{hero}.json').read_text(encoding='utf-8'))['fp'])
            arms = fp_arms.Arms(hero, cfg)
            for p in [None] + [i / 24 for i in range(25)]:
                bones = {n: (h, r) for n, h, r in arms.pose(rigs, lambda _part: fp, p)}
                for side, rig in rigs.items():
                    with self.subTest(hero=hero, p=p, side=side):
                        x, y = arms.wrist[side][0]
                        self.assertTrue(fp_arms.WRIST_X[0] - 1e-9 <= x <= fp_arms.WRIST_X[1] + 1e-9, x)
                        self.assertTrue(fp_arms.WRIST_Y[0] - 1e-9 <= y <= fp_arms.WRIST_Y[1] + 1e-9, y)
                        wrist, rot = bones[rig.hand]
                        got = rig.wrist_angles(rot, norm(sub(wrist, bones[rig.fore][0])))
                        self.assertAlmostEqual(got[0], x, places=5)
                        self.assertAlmostEqual(got[1], y, places=5)

    def test_elbows_stay_off_screen(self):
        """Em nenhum herói o cotovelo aparece na tela, parado ou em qualquer ponto da recarga."""
        from types import SimpleNamespace
        from UserComponents.cells.models import _compose
        from UserComponents.cells.weapons import gun_matrix, part_local
        for hero in fp_arms.HEROES:
            weapon = json.loads((ASSET_DIR / f'{hero}.json').read_text(encoding='utf-8'))
            fp = m_rows(weapon['fp'])
            parts = [SimpleNamespace(name=e['name'], anim=e.get('anim', 'static'),
                                     pivot=tuple(e.get('pivot', (0.0, 0.0, 0.0))),
                                     axis=tuple(e.get('axis', (0.0, 0.0, 1.0))), amount=float(e.get('amount', 0.0)))
                     for e in weapon['parts']]
            cfg = fp_arms.config(hero)
            rigs = {s: HandRig(fp_arms.load_meta(hero), s) for s in ('R', 'L')}
            arms = fp_arms.Arms(hero, cfg)
            for p in [None] + [i / 40 for i in range(41)]:
                st, bump = fp_arms.reload_state(hero, p, cfg) if p is not None else ({}, 0.0)
                roll, pitch, yaw, x, y, z = fp_arms.reload_offsets(hero, p, cfg) if p is not None else (0.0,) * 6
                gun = gun_matrix(fp, x, y + bump, z, pitch, yaw, roll)
                local = {q.name: part_local(q, st) for q in parts}

                def space(name, gun=gun, local=local):
                    m = local.get(name) if name else None
                    return gun if m is None else _compose(gun, m)

                bones = {n: h for n, h, _r in arms.pose(rigs, space, p)}
                for side, rig in rigs.items():
                    with self.subTest(hero=hero, p=p, side=side):
                        self.assertGreater(fp_arms.offscreen(bones[rig.fore]), .05)

    def test_invalid_file_is_rejected_with_a_message(self):
        data = json.loads(fp_arms.anim_path('b_cell').read_text(encoding='utf-8'))
        data['tracks']['L'][1]['grip'] = 'nao_existe'
        with self.assertRaisesRegex(ValueError, 'nao_existe'):
            fp_arms.parse_config(data)

if __name__ == '__main__':
    unittest.main()
