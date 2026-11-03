"""Bairro Arterial: marcadores e rotas exportados do Blender (runtime.json).

Coordenadas do jogo: x leste, y cima, z sul (Blender X, Z, -Y), em metros.
A base das celulas fica ao sul (+z) e a ferida ao norte (-z).
"""
import json
from pathlib import Path

MAP_FOLDER = Path(__file__).resolve().parents[2] / 'Assets/Maps/BairroArterial'
MAP_FILE = 'BairroArterial.glb'
MAP_DATA = json.loads((MAP_FOLDER / 'runtime.json').read_text(encoding='utf-8'))
POINTS = {k: tuple(v) for k, v in MAP_DATA['points'].items()}
X0, Z0, X1, Z1 = MAP_DATA['bounds']
WIDTH, LENGTH = X1-X0, Z1-Z0
NAV_CEILINGS = tuple(MAP_DATA['nav_ceilings'])


def _series(prefix):
    keys = sorted(k for k in POINTS if k.startswith(prefix+'.'))
    return [POINTS[k] for k in keys]


CELL_SPAWNS = _series('spawn_cells')
BACTERIA_ENTRANCE = _series('spawn_bacteria')
ESCORT_PATH = _series('escort')
WOUND = POINTS['wound']
WOUND_REPAIR = ESCORT_PATH[-1]
RECON = POINTS['recon']
COLONY_HINTS = _series('colony')
RBC_NODES = {k.split('.', 1)[1]: v for k, v in POINTS.items() if k.startswith('rbc.')}
RBC_EDGES = [tuple(e) for e in MAP_DATA['rbc_edges']]
RBC_DEPOT = RBC_NODES['depot']
DESTINATIONS = {k: list(v) for k, v in MAP_DATA['destinations'].items()}
CELLS_BASE = tuple(MAP_DATA['cells_base'])  # x0, z0, x1, z1: construcao bacteriana proibida
CANAL = tuple(MAP_DATA['canal'])
AMBIENT_SPOTS = [tuple(p) for p in MAP_DATA.get('ambient_spots', [])]


def in_cells_base(x, z):
    x0, z0, x1, z1 = CELLS_BASE
    return x0 <= x <= x1 and z0 <= z <= z1
