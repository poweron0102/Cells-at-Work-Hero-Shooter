"""Guarda contra z-fight: nenhuma face visivel coplanar sobreposta no Bairro Arterial."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import check_map_overlaps  # noqa: E402
import distrito_geo  # noqa: E402
import distrito_layout  # noqa: E402


class MapGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.geo = distrito_geo.Geo()
        cls.markers = distrito_layout.build(cls.geo)

    def test_no_coplanar_overlapping_faces(self):
        problems = check_map_overlaps.find_overlaps(self.geo)
        self.assertEqual(problems[:5], [], f"{len(problems)} sobreposicoes coplanares (z-fight)")

    def test_floor_finishes_never_overlap(self):
        geo = distrito_geo.Geo()
        distrito_layout.build(geo)
        self.assertEqual(geo.overlays, [])  # flushed into non-overlapping pieces

    def test_perimeter_closes_every_side(self):
        X0, Z0, X1, Z1 = self.markers['bounds']
        # Sample points just outside the boundary must be inside some perimeter building.
        group = self.geo.groups['perimetro']
        boxes = []
        for idx, *_ in group.faces:
            pts = [group.verts[i] for i in idx]
            boxes.append((min(p[0] for p in pts), min(p[2] for p in pts), max(p[0] for p in pts), max(p[2] for p in pts)))
        samples = [(X0-1, z) for z in range(int(Z0), int(Z1), 3)]+[(X1+1, z) for z in range(int(Z0), int(Z1), 3)]
        samples += [(x, Z0-1) for x in range(int(X0), int(X1), 3)]+[(x, Z1+1) for x in range(int(X0), int(X1), 3)]
        for x, z in samples:
            self.assertTrue(any(b[0]-.01 <= x <= b[2]+.01 and b[1]-.01 <= z <= b[3]+.01 for b in boxes), (x, z))


if __name__ == '__main__':
    unittest.main()
