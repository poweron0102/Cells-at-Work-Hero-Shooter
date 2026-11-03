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
            length, kind = struct.unpack('<II', source.read(8))
            if kind != 0x004e4942:
                raise ValueError('Expected embedded GLB binary data')
            cls.binary = source.read(length)

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

    def test_every_vertex_has_baked_lighting_without_losing_pattern_id(self):
        for mesh in self.data['meshes']:
            for primitive in mesh['primitives']:
                accessor = self.data['accessors'][primitive['attributes']['TEXCOORD_0']]
                self.assertEqual(accessor['componentType'], 5126)  # float UVs
                view = self.data['bufferViews'][accessor['bufferView']]
                offset = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
                stride = view.get('byteStride', 8)
                for i in range(accessor['count']):
                    u, v = struct.unpack_from('<ff', self.binary, offset + i*stride)
                    self.assertTrue(0 <= int(u) <= 17, (mesh['name'], u))
                    self.assertAlmostEqual(u % 1, 0.5, places=4)
                    # Blender flips V on glTF export; shader accepts either sign.
                    self.assertAlmostEqual(abs(v-0.5), 1.0, places=4)


if __name__ == '__main__':
    unittest.main()
