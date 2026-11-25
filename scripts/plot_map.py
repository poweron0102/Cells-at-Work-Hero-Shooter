"""Planta de um mapa vista de cima, direto do layout em Python (sem Blender).

Desenha a colisao (cor pela altura), a escolta, as rotas e destinos das hemacias, os spawns,
o posto de reconhecimento, as sugestoes de colonia e as valvas. Serve para conferir o tracado
antes de exportar.

    .venv\\Scripts\\python.exe scripts\\plot_map.py --map timo [--scale 6]
Grava ``.scratch/maps/<mapa>_planta.png``.
"""
import argparse
import importlib
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'referencias'/'scripts'/'mapa'))
import pyray as rl  # noqa: E402

MODULES = {'bairro': 'distrito_layout', 'timo': 'timo_layout', 'medula': 'medula_layout', 'coracao': 'coracao_layout'}


def build(key):
    import distrito_geo
    layout = importlib.import_module(MODULES[key])
    geo = distrito_geo.Geo()
    markers = layout.build(geo)
    return geo, markers


def height_color(y):
    """Chao baixo azul, rua cinza, paredes do claro ao escuro conforme a altura."""
    if y < -.5:
        return rl.Color(90, 120, 170, 255)
    if y < .4:
        return rl.Color(205, 200, 190, 255)
    k = max(0.0, min(1.0, (y-.4)/8))
    v = int(170-120*k)
    return rl.Color(v, v-10, v-25, 255)


def rect_lines(img, a, b, col):
    for p, q in ((rl.Vector2(a.x, a.y), rl.Vector2(b.x, a.y)), (rl.Vector2(b.x, a.y), rl.Vector2(b.x, b.y)),
                 (rl.Vector2(b.x, b.y), rl.Vector2(a.x, b.y)), (rl.Vector2(a.x, b.y), rl.Vector2(a.x, a.y))):
        rl.image_draw_line_ex(img, p, q, 2, col)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--map', default='timo')
    parser.add_argument('--scale', type=float, default=6.0, help='pixels por metro')
    parser.add_argument('--pad', type=float, default=6.0)
    args = parser.parse_args()
    geo, markers = build(args.map)
    X0, Z0, X1, Z1 = markers['bounds']
    s, pad = args.scale, args.pad
    w, h = int((X1-X0+2*pad)*s), int((Z1-Z0+2*pad)*s)

    def P(x, z):
        return rl.Vector2((x-X0+pad)*s, (z-Z0+pad)*s)
    img = rl.gen_image_color(w, h, rl.Color(250, 248, 240, 255))
    # Colisao: triangulos voltados para cima (chao) e verticais (paredes, pela altura do topo).
    tris = []
    for a, b, c in geo.collision+geo.screen:
        top = max(a[1], b[1], c[1])
        tris.append((top, a, b, c))
    tris.sort(key=lambda t: t[0])
    for top, a, b, c in tris:
        if min(a[0], b[0], c[0]) < X0-pad or max(a[0], b[0], c[0]) > X1+pad:
            continue
        ux, uz = b[0]-a[0], b[2]-a[2]
        vx, vz = c[0]-a[0], c[2]-a[2]
        area = ux*vz-uz*vx
        col = height_color(top)
        pa, pb, pc = P(a[0], a[2]), P(b[0], b[2]), P(c[0], c[2])
        if abs(area) < 1e-6:
            rl.image_draw_line_v(img, pa, pb, col)
            rl.image_draw_line_v(img, pb, pc, col)
            continue
        if area > 0:
            pb, pc = pc, pb
        rl.image_draw_triangle(img, pa, pb, pc, col)
    # Grade de 10 m.
    for x in range(int(math.floor(X0/10))*10, int(X1)+1, 10):
        rl.image_draw_line_v(img, P(x, Z0-pad), P(x, Z1+pad), rl.Color(0, 0, 0, 30))
    for z in range(int(math.floor(Z0/10))*10, int(Z1)+1, 10):
        rl.image_draw_line_v(img, P(X0-pad, z), P(X1+pad, z), rl.Color(0, 0, 0, 30))
    rect_lines(img, P(X0, Z0), P(X1, Z1), rl.Color(0, 0, 0, 160))
    pts = markers['points']
    # Base das celulas (construcao proibida).
    bx0, bz0, bx1, bz1 = markers['cells_base']
    rect_lines(img, P(bx0, bz0), P(bx1, bz1), rl.Color(30, 150, 150, 255))
    # Rotas das hemacias.
    nodes = {k.split('.', 1)[1]: v for k, v in pts.items() if k.startswith('rbc.')}
    for a, b in markers['rbc_edges']:
        pa, pb = P(nodes[a][0], nodes[a][2]), P(nodes[b][0], nodes[b][2])
        rl.image_draw_line_ex(img, pa, pb, 3, rl.Color(230, 70, 70, 255))
    for name, p in nodes.items():
        rl.image_draw_circle_v(img, P(p[0], p[2]), 4, rl.Color(200, 40, 40, 255))
        rl.image_draw_text(img, name, int(P(p[0], p[2]).x)+5, int(P(p[0], p[2]).y)-6, 12, rl.Color(120, 20, 20, 255))
    for letter, doors in markers['destinations'].items():
        for d in doors:
            p = nodes[d]
            rl.image_draw_circle_lines_v(img, P(p[0], p[2]), 9, rl.Color(240, 120, 0, 255))
    # Escolta.
    escort = [pts[k] for k in sorted(k for k in pts if k.startswith('escort.'))]
    for a, b in zip(escort, escort[1:]):
        rl.image_draw_line_ex(img, P(a[0], a[2]), P(b[0], b[2]), 5, rl.Color(240, 190, 40, 255))
    for k, col in (('spawn_cells', rl.Color(20, 160, 160, 255)), ('spawn_bacteria', rl.Color(160, 60, 200, 255))):
        for name, p in pts.items():
            if name.startswith(k+'.'):
                rl.image_draw_circle_v(img, P(p[0], p[2]), 6, col)
    for name, p in pts.items():
        if name.startswith('colony.'):
            rl.image_draw_circle_lines_v(img, P(p[0], p[2]), 7, rl.Color(120, 40, 160, 255))
    if 'recon' in pts:
        p = pts['recon']
        rl.image_draw_circle_v(img, P(p[0], p[2]), 8, rl.Color(60, 140, 240, 255))
    if 'wound' in pts:
        p = pts['wound']
        rl.image_draw_circle_lines_v(img, P(p[0], p[2]), 12, rl.Color(140, 30, 60, 255))
    for v in markers.get('valves', []):
        cx, cz, half = v['pos'][0], v['pos'][2], v['width']/2
        ax = v['axis']
        a = P(cx-half, cz) if ax == 'x' else P(cx, cz-half)
        b = P(cx+half, cz) if ax == 'x' else P(cx, cz+half)
        rl.image_draw_line_ex(img, a, b, 6, rl.Color(20, 120, 220, 255))
    out = ROOT/'.scratch'/'maps'
    out.mkdir(parents=True, exist_ok=True)
    path = out/f'{args.map}_planta.png'
    rl.export_image(img, str(path))
    rl.unload_image(img)
    print(path, f'{len(geo.collision)} triangulos de colisao, {sum(len(g.faces) for g in geo.groups.values())} faces')


if __name__ == '__main__':
    main()
