"""Detecta z-fight no Bairro Arterial sem abrir o Blender.

Procura faces alinhadas aos eixos que ficam no mesmo plano, com a mesma
orientacao, se sobrepoem e tem cor ou padrao diferentes (piscariam na tela).

    .venv\\Scripts\\python.exe scripts\\check_map_overlaps.py [--verbose]
"""
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import distrito_geo  # noqa: E402
import distrito_layout  # noqa: E402


def axis_faces(geo):
    for zone, group in geo.groups.items():
        for idx, color, pat, smooth in group.faces:
            if len(idx) != 4 or smooth:
                continue
            pts = [group.verts[i] for i in idx]
            for axis in range(3):
                values = [p[axis] for p in pts]
                if max(values)-min(values) > 1e-4:
                    continue
                a = pts[1][(axis+1) % 3]-pts[0][(axis+1) % 3], pts[1][(axis+2) % 3]-pts[0][(axis+2) % 3]
                b = pts[2][(axis+1) % 3]-pts[0][(axis+1) % 3], pts[2][(axis+2) % 3]-pts[0][(axis+2) % 3]
                sign = 1 if a[0]*b[1]-a[1]*b[0] > 0 else -1
                u = [p[(axis+1) % 3] for p in pts]
                v = [p[(axis+2) % 3] for p in pts]
                yield (axis, sign, round(values[0], 2)), (min(u), min(v), max(u), max(v)), (color, pat), zone
                break


def covered(rect, others):
    """True when ``rect`` is fully covered by the union of ``others`` (coarse 25 cm sampling)."""
    x0, z0, x1, z1 = rect
    steps_x = max(2, int((x1-x0)/.25))
    steps_z = max(2, int((z1-z0)/.25))
    for i in range(steps_x):
        for j in range(steps_z):
            px = x0+(i+.5)*(x1-x0)/steps_x
            pz = z0+(j+.5)*(z1-z0)/steps_z
            if not any(o[0] <= px <= o[2] and o[1] <= pz <= o[3] for o in others):
                return False
    return True


def find_overlaps(geo, min_area=.02):
    buckets = defaultdict(list)
    for key, rect, look, zone in axis_faces(geo):
        axis, sign, plane = key
        if axis == 1 and plane <= -2.9:
            continue  # underground slab bottoms
        buckets[key].append((rect, look, zone))
    problems = []
    for key, faces in buckets.items():
        axis, sign, plane = key
        opposite = [f[0] for f in buckets.get((axis, -sign, plane), ())]
        faces.sort(key=lambda f: f[0][0])
        for i, (ra, la, za) in enumerate(faces):
            for rb, lb, zb in faces[i+1:]:
                if rb[0] >= ra[2]:
                    break
                if la == lb:
                    continue
                w = min(ra[2], rb[2])-max(ra[0], rb[0])
                h = min(ra[3], rb[3])-max(ra[1], rb[1])
                if w > .01 and h > .01 and w*h >= min_area:
                    shared = (max(ra[0], rb[0]), max(ra[1], rb[1]), min(ra[2], rb[2]), min(ra[3], rb[3]))
                    near = [o for o in opposite if o[0] < shared[2] and o[2] > shared[0] and o[1] < shared[3] and o[3] > shared[1]]
                    if near and covered(shared, near):
                        continue  # both faces are pressed against another solid: never visible
                    problems.append((key, ra, rb, za, zb, w*h))
    return problems


def main():
    geo = distrito_geo.Geo()
    distrito_layout.build(geo)
    problems = find_overlaps(geo)
    by_zone = defaultdict(int)
    for p in problems:
        by_zone[(p[3], p[4])] += 1
    print(f'{len(problems)} sobreposicoes coplanares')
    for zones, count in sorted(by_zone.items(), key=lambda kv: -kv[1]):
        print(f'  {zones[0]} x {zones[1]}: {count}')
    if '--verbose' in sys.argv:
        for key, ra, rb, za, zb, area in problems[:60]:
            print(key, [round(v, 2) for v in ra], [round(v, 2) for v in rb], za, zb, round(area, 2))
    return problems


if __name__ == '__main__':
    main()
