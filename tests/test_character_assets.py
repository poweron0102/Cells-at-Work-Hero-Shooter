"""Valida os GLB + JSON dos personagens 3D sem GPU (só lê os arquivos)."""
import json
import struct
import unittest
from pathlib import Path

from UserComponents.cells.models import ASSET_DIR, CHARACTER_KEYS, raylib_mesh_indices, read_glb

SWINGS = {'static', 'arm', 'leg', 'weapon', 'tail', 'tentacle', 'head'}
# Modelos do Tripo com esqueleto (rig_tripo.py): clipe de ação e um osso que ele mexe.
RIGGED = {'red_blood_cell': ('Wave', 'forearm.R'), 'macrophage': ('Attack', 'forearm.R'),
          'platelet': ('Repair', 'forearm.R')}


def positions(gltf, binary, prim):
    acc = gltf['accessors'][prim['attributes']['POSITION']]
    view = gltf['bufferViews'][acc['bufferView']]
    offset = view.get('byteOffset', 0) + acc.get('byteOffset', 0)
    stride = view.get('byteStride', 12)
    return [struct.unpack_from('<3f', binary, offset + i * stride) for i in range(acc['count'])]


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

    def test_rigged_skin_and_looping_gameplay_clips(self):
        for key, (action, action_bone) in RIGGED.items():
            with self.subTest(key=key):
                self.check_rigged(key, action, action_bone)

    def check_rigged(self, key, action, action_bone):
        gltf, binary, meta = self.load(key)
        for node in gltf['nodes']:
            if 'mesh' in node:
                self.assertIn('skin', node)
                for prim in gltf['meshes'][node['mesh']]['primitives']:
                    self.assertTrue({'JOINTS_0', 'WEIGHTS_0'} <= prim['attributes'].keys())

        clips = {a['name']: a for a in gltf['animations']}
        self.assertEqual(set(meta['clips']), set(clips))
        self.assertEqual(meta['action_clip'], action)
        self.assertEqual(set(meta['clip_seconds']), set(clips))
        for name, bone in [('Idle', 'head'), ('Walk', 'thigh.L'), (action, action_bone)]:
            with self.subTest(name=name):
                clip = clips[name]
                channel = next(c for c in clip['channels'] if c['target']['path'] == 'rotation'
                               and gltf['nodes'][c['target']['node']]['name'] == bone)
                acc = gltf['accessors'][clip['samplers'][channel['sampler']]['output']]
                view = gltf['bufferViews'][acc['bufferView']]
                offset = view.get('byteOffset', 0) + acc.get('byteOffset', 0)
                rotations = [struct.unpack_from('<4f', binary, offset + i * view.get('byteStride', 16))
                             for i in range(acc['count'])]
                self.assertNotEqual(rotations[0], rotations[len(rotations) // 4])
                for first, last in zip(rotations[0], rotations[-1]):
                    self.assertAlmostEqual(first, last, places=5)

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

    def test_primitives_have_colors_normals_and_fit_u16(self):
        for key in CHARACTER_KEYS:
            with self.subTest(key=key):
                gltf, _, _ = self.load(key)
                for mesh in gltf['meshes']:
                    for prim in mesh['primitives']:
                        attrs = prim['attributes']
                        if 'COLOR_0' not in attrs:
                            # Modelos do Tripo: cor na textura do material (UV + baseColorTexture).
                            self.assertIn('TEXCOORD_0', attrs)
                            pbr = gltf['materials'][prim['material']]['pbrMetallicRoughness']
                            self.assertIn('baseColorTexture', pbr)
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
                if key in RIGGED:
                    # Malha única deformável: as pontas das botas avançam mais em +Z que os calcanhares.
                    node = next(n for n in gltf['nodes'] if n.get('name') == f'{key}.body')
                    feet = [p for p in positions(gltf, binc, gltf['meshes'][node['mesh']]['primitives'][0])
                            if p[1] < 0.04 * meta['height']]
                    self.assertTrue(feet)
                    self.assertGreater(max(p[2] for p in feet) + min(p[2] for p in feet), 0.0)
                    continue
                mapping, _ = raylib_mesh_indices(gltf)
                legs = [p for p in meta['parts'] if p['swing'] in ('leg', 'head')]
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
