"""Valida os GLB + JSON dos personagens 3D sem GPU (só lê os arquivos)."""
import json
import struct
import unittest
from pathlib import Path

from UserComponents.cells.models import ASSET_DIR, CHARACTER_KEYS, raylib_mesh_indices, read_glb

SWINGS = {'static', 'arm', 'leg', 'weapon', 'tail', 'tentacle', 'head'}


class CharacterAssetTests(unittest.TestCase):
    def load(self, key):
        gltf, binc = read_glb(ASSET_DIR / f'{key}.glb')
        meta = json.loads((ASSET_DIR / f'{key}.json').read_text(encoding='utf-8'))
        return gltf, binc, meta

    def test_all_keys_exist(self):
        self.assertEqual(len(CHARACTER_KEYS), 10)
        for key in CHARACTER_KEYS:
            self.assertTrue((ASSET_DIR / f'{key}.glb').is_file(), key)
            self.assertTrue((ASSET_DIR / f'{key}.json').is_file(), key)

    def rotations(self, gltf, binary, clip, bone):
        channel = next(c for c in clip['channels'] if c['target']['path'] == 'rotation'
                       and gltf['nodes'][c['target']['node']]['name'] == bone)
        acc = gltf['accessors'][clip['samplers'][channel['sampler']]['output']]
        view = gltf['bufferViews'][acc['bufferView']]
        offset = view.get('byteOffset', 0) + acc.get('byteOffset', 0)
        return [struct.unpack_from('<4f', binary, offset + i * view.get('byteStride', 16)) for i in range(acc['count'])]

    def test_tripo_characters_skin_and_looping_gameplay_clips(self):
        """Hemácia, plaqueta e Célula B: malha com pele, clipes cíclicos fechados e camadas conhecidas."""
        moving = {'Idle': 'head', 'Walk': 'thigh.L', 'Run': 'thigh.L', 'Repair': 'forearm.R', 'Carry': 'forearm.R',
                  'Wave': 'forearm.R'}
        for key, expected in (('platelet', {'Idle', 'Walk', 'Repair'}),
                              ('red_blood_cell', {'Idle', 'Walk', 'Run', 'Carry', 'Wave'}),
                              ('b_cell', {'Idle', 'Walk', 'Run', 'Jump', 'Land', 'Fire', 'Reload', 'Melee', 'Sit'})):
            gltf, binary, meta = self.load(key)
            for node in gltf['nodes']:
                if 'mesh' in node:
                    self.assertIn('skin', node)
                    for prim in gltf['meshes'][node['mesh']]['primitives']:
                        self.assertTrue({'JOINTS_0', 'WEIGHTS_0'} <= prim['attributes'].keys())
            clips = {a['name']: a for a in gltf['animations']}
            self.assertEqual(set(clips), expected, key)
            self.assertEqual(set(meta['clips']), expected)
            self.assertLessEqual(set(meta['layers'].values()), {'upper', 'lower', 'arms', 'full'})
            self.assertIn('Walk', meta['strides'])
            for name in meta['loops']:
                with self.subTest(key=key, clip=name):
                    rotations = self.rotations(gltf, binary, clips[name], moving.get(name, 'hips'))
                    if name in moving:
                        self.assertNotEqual(rotations[0], rotations[len(rotations) // 4])
                    for first, last in zip(rotations[0], rotations[-1]):
                        self.assertAlmostEqual(first, last, places=5)

    def test_b_cell_weapon_socket_and_red_blood_cell_box(self):
        gltf, _, meta = self.load('b_cell')
        joints = {gltf['nodes'][j]['name'] for j in gltf['skins'][0]['joints']}
        self.assertEqual(meta['mount']['bone'], 'socket_weapon')
        self.assertIn('socket_weapon', joints)
        gltf, _, meta = self.load('red_blood_cell')
        self.assertEqual({p['name'] for p in meta['parts']}, {'body', 'box'})
        self.assertIn('box', {gltf['nodes'][j]['name'] for j in gltf['skins'][0]['joints']})
        self.assertEqual(meta['layers']['Carry'], 'arms')  # pose leve: só braços e caixa sobre a caminhada

    def test_mesh_indices_match_raylib_order(self):
        for key in CHARACTER_KEYS:
            with self.subTest(key=key):
                gltf, _, meta = self.load(key)
                mapping, count = raylib_mesh_indices(gltf)
                self.assertEqual(meta['key'], key)
                self.assertEqual(meta['mesh_count'], count)
                indices = [p['mesh'] for p in meta['parts']]
                self.assertEqual(len(indices), len(set(indices)), 'índices repetidos')
                self.assertTrue(all(0 <= i < count for i in indices))
                names = {p['name'] for p in meta['parts']}
                self.assertIn('body', names)
                for part in meta['parts']:
                    self.assertEqual(mapping[f"{key}.{part['name']}"], [part['mesh']])
                    self.assertIn(part['swing'], SWINGS)
                    self.assertEqual(len(part['pivot']), 3)
                    self.assertTrue(part['parent'] == 'body' or part['parent'] in names)

    def test_macrophage_braid_has_weighted_joints_and_action_curves(self):
        gltf, binary, meta = self.load('macrophage')
        joints = gltf['skins'][0]['joints']
        braid = [next(i for i, node in enumerate(gltf['nodes']) if node['name'] == f'braid.{n}')
                 for n in range(4)]
        for parent, child in zip(braid, braid[1:]):
            self.assertIn(child, gltf['nodes'][parent]['children'])
        self.assertTrue(set(braid) <= set(joints))
        clips = {a['name']: a for a in gltf['animations']}
        self.assertEqual(set(clips), {'Idle', 'Walk', 'Run', 'Jump', 'Land', 'Fire', 'Reload', 'Melee'})
        self.assertEqual(set(meta['clips']), set(clips))

        attrs = gltf['meshes'][0]['primitives'][0]['attributes']
        self.assertIn('TEXCOORD_0', attrs)
        self.assertIn('baseColorTexture', gltf['materials'][0]['pbrMetallicRoughness'])
        ids = gltf['accessors'][attrs['JOINTS_0']]
        weights = gltf['accessors'][attrs['WEIGHTS_0']]
        iv = gltf['bufferViews'][ids['bufferView']]
        wv = gltf['bufferViews'][weights['bufferView']]
        fmt = '<4B' if ids['componentType'] == 5121 else '<4H'
        weighted = set()
        for i in range(ids['count']):
            indices = struct.unpack_from(fmt, binary, iv.get('byteOffset', 0) + ids.get('byteOffset', 0)
                                         + i * iv.get('byteStride', struct.calcsize(fmt)))
            values = struct.unpack_from('<4f', binary, wv.get('byteOffset', 0) + weights.get('byteOffset', 0)
                                        + i * wv.get('byteStride', 16))
            self.assertAlmostEqual(sum(values), 1.0, places=5)
            weighted.update(joints[j] for j, w in zip(indices, values) if w > .01)
        self.assertTrue(set(braid) <= weighted)
        for name in ('Walk', 'Run', 'Melee'):
            clip = clips[name]
            rotations = {c['target']['node']: c['sampler'] for c in clip['channels']
                         if c['target']['path'] == 'rotation'}
            for joint in braid:
                acc = gltf['accessors'][clip['samplers'][rotations[joint]]['output']]
                self.assertGreater(acc['count'], 2)
        self.assertIn(meta['mount']['bone'], {gltf['nodes'][j]['name'] for j in joints})

    def test_primitives_have_colors_normals_and_fit_u16(self):
        for key in CHARACTER_KEYS:
            with self.subTest(key=key):
                gltf, _, _ = self.load(key)
                for mesh in gltf['meshes']:
                    for prim in mesh['primitives']:
                        attrs = prim['attributes']
                        self.assertIn('COLOR_0', attrs)
                        self.assertIn('NORMAL', attrs)
                        self.assertLessEqual(gltf['accessors'][attrs['POSITION']]['count'], 65535)

    def test_feet_on_ground_and_height(self):
        for key in CHARACTER_KEYS:
            with self.subTest(key=key):
                gltf, _, meta = self.load(key)
                mins, maxs = [], []
                for mesh in gltf['meshes']:
                    for prim in mesh['primitives']:
                        acc = gltf['accessors'][prim['attributes']['POSITION']]
                        mins.append(acc['min'][1])
                        maxs.append(acc['max'][1])
                self.assertAlmostEqual(min(mins), 0.0, delta=0.05)
                h = meta['height']
                self.assertLessEqual(abs(max(maxs) - h), 0.15 * h, f'altura {max(maxs):.2f} vs {h}')

    def test_bodies_face_plus_z(self):
        """Pontas dos pés (ou cabeça do quadrúpede) ficam em +Z: o modelo olha para +Z."""
        for key in CHARACTER_KEYS:
            with self.subTest(key=key):
                gltf, binc, meta = self.load(key)
                mapping, _ = raylib_mesh_indices(gltf)
                legs = [p for p in meta['parts'] if p['swing'] in ('leg', 'head')]
                if not legs and gltf.get('skins'):
                    # Uma malha contínua inclui as botas. Compare a dianteira e o calcanhar
                    # perto do chão com a origem do osso do tornozelo na pose de repouso.
                    skin = gltf['skins'][0]
                    foot = next(j for j, n in enumerate(skin['joints']) if gltf['nodes'][n]['name'] == 'foot.L')
                    inv = gltf['accessors'][skin['inverseBindMatrices']]
                    view = gltf['bufferViews'][inv['bufferView']]
                    m = struct.unpack_from('<16f', binc, view.get('byteOffset', 0)
                                           + inv.get('byteOffset', 0) + foot * 64)
                    ankle_z = -sum(m[8+i] * m[12+i] for i in range(3))
                    prim = gltf['meshes'][0]['primitives'][0]
                    pos = gltf['accessors'][prim['attributes']['POSITION']]
                    view = gltf['bufferViews'][pos['bufferView']]
                    start = view.get('byteOffset', 0) + pos.get('byteOffset', 0)
                    feet = [z for x, y, z in (struct.unpack_from('<3f', binc, start + i * view.get('byteStride', 12))
                                               for i in range(pos['count'])) if x > 0 and y < .09]
                    self.assertGreater(max(feet) - ankle_z, ankle_z - min(feet))
                    continue
                self.assertTrue(legs)
                node_mesh = {n['name']: n['mesh'] for n in gltf['nodes'] if 'mesh' in n}
                zs = []
                for part in legs:
                    prim = gltf['meshes'][node_mesh[f"{key}.{part['name']}"]]['primitives'][0]
                    acc = gltf['accessors'][prim['attributes']['POSITION']]
                    zs.append((acc['max'][2] - part['pivot'][2]) - (part['pivot'][2] - acc['min'][2]))
                self.assertGreater(sum(zs) / len(zs), 0.0)


if __name__ == '__main__':
    unittest.main()
