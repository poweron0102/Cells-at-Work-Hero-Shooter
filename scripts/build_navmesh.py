"""Gera Assets/Maps/BairroArterial/nav.json a partir da colisao exportada.

    .venv\Scripts\python.exe scripts\build_navmesh.py
Rode depois de exportar o mapa (o hash de runtime.json invalida o cache).
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from EasyCells3D.PhysicsComponents3D import BulletPhysicsWorld, PhysicsBody3D, BodyType, TriangleMeshShape  # noqa: E402
sys.path.insert(0, str(ROOT/"tests"))
from simulation_support import headless_game  # noqa: E402
from UserComponents.cells.layout import MAP_DATA  # noqa: E402
from UserComponents.cells.navigation import Navigator  # noqa: E402


def main():
    game = headless_game()
    game.physics_world = BulletPhysicsWorld()
    item = game.CreateItem()
    item.AddComponent(PhysicsBody3D(TriangleMeshShape(MAP_DATA['vertices'], MAP_DATA['indices']), body_type=BodyType.STATIC))
    for function in game.to_init:
        function()
    game.to_init.clear()
    start = time.time()
    nav = Navigator(game.physics_world)
    nav.build()
    nav.save()
    nodes = sum(len(v) for v in nav.columns.values())
    print(f'nav.json: {nodes} nos, {sum(len(e) for e in nav.edges.values())} arestas em {time.time()-start:.1f}s')
    game.close()


if __name__ == '__main__':
    main()
