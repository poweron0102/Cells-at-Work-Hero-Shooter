"""Guard the Bairro Arterial export: shader attributes and Raylib mesh limits."""
import json
import struct
import unittest

from UserComponents.cells.layout import MAP_FILE, MAP_FOLDER


class MapAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = MAP_FOLDER / MAP_FILE
        with path.open('rb') as source:
            magic, version, _ = struct.unpack('<III', source.read(12))
            if (magic, version) != (0x46546c67, 2):
                raise ValueError('Runtime map must be a valid GLB 2 file')
            length, _ = struct.unpack('<II', source.read(8))
            cls.data = json.loads(source.read(length))

    def test_every_surface_keeps_its_shader_attributes(self):
        data = self.data
        for mesh in data['meshes']:
            for primitive in mesh['primitives']:
                # scenery.py uses vertex colors, normals and the pattern ID in UV.x.
                for attribute in ('POSITION', 'NORMAL', 'COLOR_0', 'TEXCOORD_0'):
                    self.assertIn(attribute, primitive['attributes'], mesh['name'])

    def test_geometry_is_embedded(self):
        for buffer in self.data['buffers']:
            self.assertNotIn('uri', buffer)

    def test_mesh_batches_fit_raylib_16_bit_indices(self):
        for mesh in self.data['meshes']:
            for primitive in mesh['primitives']:
                count = self.data['accessors'][primitive['attributes']['POSITION']]['count']
                self.assertLessEqual(count, 65535, mesh['name'])


if __name__ == '__main__':
    unittest.main()
