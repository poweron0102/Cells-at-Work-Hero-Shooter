"""Verifica se as rotas das hemacias atravessam geometria do mapa.

As hemacias andam em linha reta entre os nos de ``rbc_edges``; cada aresta
precisa de chao continuo (sem degrau ou queda) e de um corredor livre da
largura do corpo. Usa a colisao exportada (runtime.json) no Bullet.

    .venv\\Scripts\\python.exe scripts\\check_rbc_routes.py
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RADIUS = .5      # meia largura do corredor livre
SAMPLE = .4      # passo da amostragem ao longo da aresta
MAX_STEP = .3    # maior variacao de altura do chao entre duas amostras
SOLID = 1 | 16   # mapa e alambrados (hemacias nao atravessam tela)


def edge_problems(world, nodes, edges):
    """Lista ``(a, b, motivo, ponto)`` para cada aresta bloqueada."""
    from EasyCells3D.Geometry import Vec3
    out = []
    for a, b in edges:
        pa, pb = nodes[a], nodes[b]
        dx, dz = pb[0]-pa[0], pb[2]-pa[2]
        length = math.hypot(dx, dz)
        ux, uz = dx/length, dz/length
        px, pz = -uz, ux
        steps = max(2, int(length/SAMPLE))
        prev = None
        problem = None
        y = pa[1]
        for i in range(steps+1):
            t = i/steps
            x, z = pa[0]+dx*t, pa[2]+dz*t
            hit = world.raycast(Vec3(x, y+1.6, z), Vec3(0, -1, 0), 3.5, SOLID)
            if hit is None:
                problem = ('sem chao', (x, y, z))
                break
            if abs(hit.point.y-y) > MAX_STEP and i:
                problem = (f'degrau {hit.point.y-y:+.2f} m', (x, hit.point.y, z))
                break
            y = hit.point.y
            # Body corridor: across the path and from the previous sample, at knee and chest height.
            for h in (.5, 1.1):
                if world.raycast(Vec3(x-px*RADIUS, y+h, z-pz*RADIUS), Vec3(px, 0, pz), 2*RADIUS, SOLID) is not None:
                    problem = ('obstaculo', (x, y+h, z))
                    break
                if prev is not None:
                    for off in (-RADIUS, 0, RADIUS):
                        a0 = Vec3(prev[0]+px*off, prev[1]+h, prev[2]+pz*off)
                        delta = Vec3(x+px*off, y+h, z+pz*off)-a0
                        if world.raycast(a0, delta, delta.magnitude(), SOLID) is not None:
                            problem = ('obstaculo', (x, y+h, z))
                            break
                if problem:
                    break
            if problem:
                break
            prev = (x, y, z)
        if problem:
            out.append((a, b)+problem)
    return out


def map_world(map_key=None):
    sys.path.insert(0, str(ROOT/'tests'))
    from simulation_support import headless_game
    from EasyCells3D.PhysicsComponents3D import BulletPhysicsWorld, PhysicsBody3D, BodyType, TriangleMeshShape
    from UserComponents.cells import layout
    if map_key:
        layout.select(map_key)
    MAP_DATA = layout.MAP_DATA
    game = headless_game()
    game.physics_world = BulletPhysicsWorld()
    item = game.CreateItem()
    item.AddComponent(PhysicsBody3D(TriangleMeshShape(MAP_DATA['vertices'], MAP_DATA['indices']), body_type=BodyType.STATIC))
    from UserComponents.cells.world import add_screens
    add_screens(game)
    for function in game.to_init:
        function()
    game.to_init.clear()
    return game


def main():
    import argparse
    from UserComponents.cells import layout
    parser = argparse.ArgumentParser()
    parser.add_argument('--map', default=None)
    args = parser.parse_args()
    game = map_world(args.map)
    RBC_NODES, RBC_EDGES = layout.RBC_NODES, layout.RBC_EDGES
    problems = edge_problems(game.physics_world, RBC_NODES, RBC_EDGES)
    for a, b, why, p in problems:
        print(f'{a:>6} -> {b:<6} {why:<16} em ({p[0]:.1f}, {p[1]:.1f}, {p[2]:.1f})')
    print(f'{len(problems)} de {len(RBC_EDGES)} arestas bloqueadas')
    game.close()
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
