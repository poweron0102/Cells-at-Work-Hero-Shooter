"""Mapa ativo: marcadores e rotas exportados do Blender (``runtime.json``).

Coordenadas do jogo: x leste, y cima, z sul (Blender X, Z, -Y), em metros.
A base das celulas fica ao sul (+z) e a entrada bacteriana ao norte (-z).

``select(chave)`` troca o mapa (``maps.MAPS``) e recarrega todos os nomes deste modulo.
Quem usa os marcadores deve le-los como ``layout.NOME`` na hora do uso (nunca
``from .layout import NOME`` no topo do arquivo), para enxergar o mapa escolhido no lobby.
"""
import json
from . import maps

MAP_KEY = None
MAP_INFO = None
MODE = 'escort'
MAP_FOLDER = MAP_FILE = None
MAP_DATA = {}
POINTS = {}
X0 = Z0 = X1 = Z1 = 0.0
WIDTH = LENGTH = 0.0
NAV_CEILINGS = ()
CELL_SPAWNS = BACTERIA_ENTRANCE = ESCORT_PATH = COLONY_HINTS = ()
WOUND = WOUND_REPAIR = RECON = (0.0, 0.0, 0.0)
RBC_NODES, RBC_EDGES, RBC_DEPOT, DESTINATIONS = {}, [], (0.0, 0.0, 0.0), {}
CELLS_BASE = (0.0, 0.0, 0.0, 0.0)
CANAL = ()
AMBIENT_SPOTS = []
VALVES = []        # coracao: portoes que abrem e fecham com o batimento
EXTRA = {}         # dados especificos do mapa (paleta, raio da ferida, altura da antena...)


def _series(prefix):
    keys = sorted(k for k in POINTS if k.startswith(prefix+'.'))
    return [POINTS[k] for k in keys]


def select(key=None):
    """Carrega o mapa ``key`` (ou o padrao). Devolve a chave efetivamente carregada."""
    global MAP_KEY, MAP_INFO, MODE, MAP_FOLDER, MAP_FILE, MAP_DATA, POINTS, X0, Z0, X1, Z1, WIDTH, LENGTH
    global NAV_CEILINGS, CELL_SPAWNS, BACTERIA_ENTRANCE, ESCORT_PATH, WOUND, WOUND_REPAIR, RECON, COLONY_HINTS
    global RBC_NODES, RBC_EDGES, RBC_DEPOT, DESTINATIONS, CELLS_BASE, CANAL, AMBIENT_SPOTS, VALVES, EXTRA
    info = maps.info(key or maps.DEFAULT)
    if not info.exists():
        info = maps.info(maps.DEFAULT)
    if info.key == MAP_KEY:
        return MAP_KEY
    data = json.loads((info.path/'runtime.json').read_text(encoding='utf-8'))
    MAP_KEY, MAP_INFO, MODE = info.key, info, data.get('mode', info.mode)
    MAP_FOLDER, MAP_FILE, MAP_DATA = info.path, info.model_file, data
    POINTS = {k: tuple(v) for k, v in data['points'].items()}
    X0, Z0, X1, Z1 = data['bounds']
    WIDTH, LENGTH = X1-X0, Z1-Z0
    NAV_CEILINGS = tuple(data['nav_ceilings'])
    CELL_SPAWNS = _series('spawn_cells')
    BACTERIA_ENTRANCE = _series('spawn_bacteria')
    ESCORT_PATH = _series('escort')
    WOUND = POINTS.get('wound', ESCORT_PATH[-1] if ESCORT_PATH else (0.0, 0.0, 0.0))
    WOUND_REPAIR = ESCORT_PATH[-1] if ESCORT_PATH else WOUND
    RECON = POINTS['recon']
    COLONY_HINTS = _series('colony')
    RBC_NODES = {k.split('.', 1)[1]: v for k, v in POINTS.items() if k.startswith('rbc.')}
    RBC_EDGES = [tuple(e) for e in data['rbc_edges']]
    RBC_DEPOT = RBC_NODES['depot']
    DESTINATIONS = {k: list(v) for k, v in data['destinations'].items()}
    CELLS_BASE = tuple(data['cells_base'])  # x0, z0, x1, z1: construcao bacteriana proibida
    CANAL = tuple(data.get('canal', ()))
    AMBIENT_SPOTS = [tuple(p) for p in data.get('ambient_spots', [])]
    VALVES = [dict(v) for v in data.get('valves', [])]
    EXTRA = dict(data.get('extra', {}))
    return MAP_KEY


def in_cells_base(x, z):
    x0, z0, x1, z1 = CELLS_BASE
    return x0 <= x <= x1 and z0 <= z <= z1


def label(name):
    """Texto do objetivo no modo do mapa ativo (``maps.MODES``)."""
    return maps.MODES[MODE][name]


select(maps.DEFAULT)
