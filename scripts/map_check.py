"""Confere um mapa direto do layout em Python (sem Blender nem export).

Monta a colisao do ``Geo`` no Bullet e verifica o que os testes do jogo exigem:
spawns e marcadores sobre chao caminhavel, rotas das hemacias livres, navegacao dos
bots das duas bases ate todos os objetivos e sugestoes de colonia, nenhuma linha de visao
direta entre as bases e nenhuma face coplanar sobreposta (z-fight).

    .venv\\Scripts\\python.exe scripts\\map_check.py --map timo
"""
import argparse
import importlib
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'scripts'))
sys.path.insert(0, str(ROOT/'tests'))
sys.path.insert(0, str(ROOT/'referencias'/'scripts'/'mapa'))

MODULES = {'bairro': 'distrito_layout', 'timo': 'timo_layout', 'medula': 'medula_layout', 'coracao': 'coracao_layout'}


def runtime_from_geo(key):
    """O mesmo ``runtime.json`` que o export do Blender gravaria (colisao + marcadores)."""
    import distrito_geo
    layout_module = importlib.import_module(MODULES[key])
    geo = distrito_geo.Geo()
    markers = layout_module.build(geo)
    verts, index, idx = [], {}, []
    for tri in geo.collision:
        f = []
        for p in tri:
            k = (round(p[0], 3), round(p[1], 3), round(p[2], 3))
            if k not in index:
                index[k] = len(verts)
                verts.append(k)
            f.append(index[k])
        if len(set(f)) == 3:
            idx.extend(f)
    data = dict(markers)
    data['points'] = {k: tuple(round(c, 4) for c in v) for k, v in markers['points'].items()}
    data['vertices'] = [list(v) for v in verts]
    data['indices'] = idx
    if geo.screen:
        sv, sindex, sidx = [], {}, []
        for tri in geo.screen:
            f = []
            for p in tri:
                k = (round(p[0], 3), round(p[1], 3), round(p[2], 3))
                if k not in sindex:
                    sindex[k] = len(sv)
                    sv.append(k)
                f.append(sindex[k])
            if len(set(f)) == 3:
                sidx.extend(f)
        data['screen_vertices'] = [list(v) for v in sv]
        data['screen_indices'] = sidx
    return geo, data


def install(key, data):
    """Coloca ``data`` no modulo ``layout`` como se fosse o mapa exportado."""
    from UserComponents.cells import layout, maps
    info = maps.info(key)
    layout.MAP_KEY = None
    layout.select(maps.DEFAULT)
    L = layout
    L.MAP_KEY, L.MAP_INFO, L.MODE = key+'*', info, data.get('mode', info.mode)
    L.MAP_DATA = data
    L.POINTS = {k: tuple(v) for k, v in data['points'].items()}
    L.X0, L.Z0, L.X1, L.Z1 = data['bounds']
    L.NAV_CEILINGS = tuple(data['nav_ceilings'])
    L.CELL_SPAWNS = L._series('spawn_cells')
    L.BACTERIA_ENTRANCE = L._series('spawn_bacteria')
    L.ESCORT_PATH = L._series('escort')
    L.WOUND = L.POINTS.get('wound', L.ESCORT_PATH[-1] if L.ESCORT_PATH else (0, 0, 0))
    L.WOUND_REPAIR = L.ESCORT_PATH[-1] if L.ESCORT_PATH else L.WOUND
    L.RECON = L.POINTS['recon']
    L.COLONY_HINTS = L._series('colony')
    L.RBC_NODES = {k.split('.', 1)[1]: v for k, v in L.POINTS.items() if k.startswith('rbc.')}
    L.RBC_EDGES = [tuple(e) for e in data['rbc_edges']]
    L.RBC_DEPOT = L.RBC_NODES['depot']
    L.DESTINATIONS = {k: list(v) for k, v in data['destinations'].items()}
    L.CELLS_BASE = tuple(data['cells_base'])
    L.VALVES = [dict(v) for v in data.get('valves', [])]
    L.EXTRA = dict(data.get('extra', {}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--map', default='timo')
    parser.add_argument('--skip-nav', action='store_true')
    args = parser.parse_args()
    start = time.time()
    geo, data = runtime_from_geo(args.map)
    install(args.map, data)
    from UserComponents.cells import layout as L
    from simulation_support import headless_game
    from EasyCells3D.Geometry import Vec3
    from EasyCells3D.PhysicsComponents3D import BulletPhysicsWorld, PhysicsBody3D, BodyType, TriangleMeshShape
    from check_rbc_routes import edge_problems
    from check_map_overlaps import find_overlaps
    game = headless_game()
    game.physics_world = BulletPhysicsWorld()
    item = game.CreateItem()
    item.AddComponent(PhysicsBody3D(TriangleMeshShape(data['vertices'], data['indices']), body_type=BodyType.STATIC))
    from UserComponents.cells.world import add_screens
    add_screens(game)
    for function in game.to_init:
        function()
    game.to_init.clear()
    world = game.physics_world
    failures = 0

    def report(ok, text):
        nonlocal failures
        failures += 0 if ok else 1
        print(('  ok   ' if ok else '  FALHA ')+text)

    def ground(x, z, top):
        hit = world.raycast(Vec3(x, top, z), Vec3(0, -1, 0), 8, 1)
        return hit.point.y if hit else None
    print(f'{args.map}: {len(data["indices"])//3} triangulos de colisao')
    # Spawns e marcadores sobre chao.
    named = [(f'spawn_cells.{i}', p) for i, p in enumerate(L.CELL_SPAWNS)]
    named += [(f'spawn_bacteria.{i}', p) for i, p in enumerate(L.BACTERIA_ENTRANCE)]
    named += [(f'rbc.{k}', p) for k, p in L.RBC_NODES.items()]+[('recon', L.RECON)]
    named += [(f'escort.{i}', p) for i, p in enumerate(L.ESCORT_PATH)]+[(f'colony.{i}', p) for i, p in enumerate(L.COLONY_HINTS)]
    bad = []
    for name, p in named:
        y = ground(p[0], p[2], p[1]+1.5)
        clear = not world.overlap_sphere(Vec3(p[0], p[1]+1.2, p[2]), .45, 1 | 16)
        if y is None or abs(y-p[1]) > .35 or not clear:
            bad.append(f'{name} {p} chao={y} livre={clear}')
    report(not bad, f'{len(named)} marcadores sobre chao livre'+(': '+'; '.join(bad[:8]) if bad else ''))
    # Rotas das hemacias.
    problems = edge_problems(world, L.RBC_NODES, L.RBC_EDGES)
    report(not problems, f'{len(L.RBC_EDGES)} trechos das hemacias livres' +
           (': '+'; '.join(f'{a}->{b} {why} em ({p[0]:.1f},{p[1]:.1f},{p[2]:.1f})' for a, b, why, p in problems[:8])
            if problems else ''))
    # Linha de visao entre as bases.
    seen = []
    for a in L.CELL_SPAWNS:
        for b in L.BACTERIA_ENTRANCE:
            s = Vec3(a[0], a[1]+1.5, a[2])
            d = Vec3(b[0], b[1]+1.5, b[2])-s
            if world.raycast(s, d, d.magnitude(), 1) is None:
                seen.append((a, b))
    report(not seen, 'sem linha de visao direta entre as bases')
    # z-fight.
    overlaps = find_overlaps(geo)
    report(not overlaps, f'sem faces coplanares sobrepostas ({len(overlaps)})' +
           (': '+'; '.join(f'{p[3]}/{p[4]} plano {p[0]}' for p in overlaps[:6]) if overlaps else ''))
    # Navegacao dos bots.
    if not args.skip_nav:
        from UserComponents.cells.navigation import Navigator
        Navigator._cached.pop(L.MAP_KEY, None)
        nav = Navigator(world)
        t = time.time()
        nav.build()
        Navigator._cached[L.MAP_KEY] = nav.columns, nav.edges
        print(f'  navegacao: {sum(len(v) for v in nav.columns.values())} nos em {time.time()-t:.1f}s')
        goals = [('escolta inicio', L.ESCORT_PATH[0]), ('escolta fim', L.ESCORT_PATH[-1]), ('recon', L.RECON)]
        goals += [(f'porta {d}', L.RBC_NODES[d]) for doors in L.DESTINATIONS.values() for d in doors]
        goals += [(f'colonia {i}', p) for i, p in enumerate(L.COLONY_HINTS)]
        goals += [(f'valva {v.get("id")}', tuple(v['pos'])) for v in L.VALVES]
        missing = []
        for label, origin in (('celulas', L.CELL_SPAWNS[0]), ('bacterias', L.BACTERIA_ENTRANCE[0])):
            for name, goal in goals:
                path = nav.path(Vec3(origin[0], origin[1]+.95, origin[2]), Vec3(goal[0], goal[1]+.95, goal[2]), 1.2, 12000)
                if not path or (path[-1]-Vec3(goal[0], goal[1]+.95, goal[2])).magnitude() > 2.6:
                    missing.append(f'{label}->{name}')
        report(not missing, f'navegacao das duas bases ate {len(goals)} objetivos' + (': '+', '.join(missing[:10]) if missing else ''))
    game.close()
    print(f'{"OK" if not failures else f"{failures} FALHA(S)"} em {time.time()-start:.1f}s')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
