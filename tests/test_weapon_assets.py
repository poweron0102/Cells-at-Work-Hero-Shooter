"""Valida os GLB + JSON das armas e as montagens nos personagens, sem GPU (só lê os arquivos)."""
import json
import math
import unittest

from UserComponents.cells.catalog import HEROES
from UserComponents.cells.combat import impact_kind
from UserComponents.cells.models import ASSET_DIR as CHAR_DIR, raylib_mesh_indices, read_glb
from UserComponents.cells.shots import STYLES, style_for, tracer_life
from UserComponents.cells.weapons import ASSET_DIR, WEAPON_KEYS

ANIMS = {'static', 'bolt', 'mag', 'pulse', 'spin', 'support', 'melee'}


class WeaponAssetTests(unittest.TestCase):
    def load(self, key):
        gltf, _ = read_glb(ASSET_DIR / f'{key}.glb')
        meta = json.loads((ASSET_DIR / f'{key}.json').read_text(encoding='utf-8'))
        return gltf, meta

    def test_every_hero_has_a_weapon(self):
        self.assertEqual(set(WEAPON_KEYS), set(HEROES))

    def test_mesh_indices_and_parts(self):
        for key in WEAPON_KEYS:
            with self.subTest(key=key):
                gltf, meta = self.load(key)
                mapping, count = raylib_mesh_indices(gltf)
                self.assertEqual(meta['mesh_count'], count)
                names = {p['name'] for p in meta['parts']}
                self.assertIn('body', names)
                self.assertIn('arm_r', names)
                for part in meta['parts']:
                    self.assertEqual(mapping[f"w_{key}.{part['name']}"], [part['mesh']])
                    self.assertIn(part['anim'], ANIMS)
                    self.assertIn(part['space'], ('gun', 'view'))
                    if part['anim'] != 'static':
                        self.assertEqual(len(part['pivot']), 3)
                        self.assertEqual(len(part['axis']), 3)
                    if part['space'] == 'view':
                        self.assertTrue(part['fp_only'])
                        self.assertEqual(part['anim'], 'melee')
                # Braços só existem em primeira pessoa.
                for part in meta['parts']:
                    if part['name'].startswith('arm_'):
                        self.assertTrue(part['fp_only'], part['name'])

    def test_muzzle_ahead_and_rest_pose_in_view(self):
        for key in WEAPON_KEYS:
            with self.subTest(key=key):
                _, meta = self.load(key)
                self.assertGreater(meta['muzzle'][2], .25, 'cano à frente do cabo (+Z)')
                fp = meta['fp']
                self.assertEqual(len(fp), 3)
                x, y, z = fp[0][3], fp[1][3], fp[2][3]
                self.assertLess(x, 0, 'arma à direita da tela (-X)')
                self.assertLess(y, 0, 'arma abaixo da mira')
                self.assertTrue(.3 < z < .6, 'arma à frente da câmera')
                # Rotação ortonormal (sem escala nem cisalhamento).
                for i in range(3):
                    self.assertAlmostEqual(math.hypot(*fp[i][:3]), 1.0, places=4)

    def test_characters_mount_their_weapon(self):
        for key in WEAPON_KEYS:
            with self.subTest(key=key):
                meta = json.loads((CHAR_DIR / f'{key}.json').read_text(encoding='utf-8'))
                mount = meta.get('mount')
                self.assertIsNotNone(mount)
                parts = {p['name'] for p in meta['parts']}
                self.assertIn(mount['part'], parts | {'body'})
                y = mount['matrix'][1][3]
                self.assertTrue(.6 < y < meta['height'], 'arma na altura das mãos/ombro')


class ShotStyleTests(unittest.TestCase):
    def test_every_hero_and_ability_has_a_style(self):
        for hero in HEROES:
            self.assertIs(style_for('shot', hero), STYLES[hero])
        for kind in ('mark', 'sticky', 'acid', 'beam'):
            self.assertIs(style_for(kind, 'neutrophil'), STYLES[kind])

    def test_tracer_lives_long_enough_to_reach_target(self):
        for hero in HEROES:
            st = style_for('shot', hero)
            life = tracer_life('shot', hero, (0, 0, 0), (0, 0, 50))
            self.assertGreaterEqual(life, 50 / st['speed'])
        self.assertGreater(tracer_life('beam', 'b_cell', (0, 0, 0), (0, 0, 70)), 0)

    def test_impact_kind(self):
        self.assertIsNone(impact_kind([]))
        self.assertEqual(impact_kind([dict(kind='actor')]), 'actor')
        self.assertEqual(impact_kind([dict(kind='rbc')]), 'actor')
        self.assertEqual(impact_kind([dict(kind='world')]), 'world')
        self.assertEqual(impact_kind([dict(kind='colony')]), 'world')


if __name__ == '__main__':
    unittest.main()
