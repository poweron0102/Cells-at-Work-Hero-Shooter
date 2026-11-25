"""Capturas de uma partida de treino real (janela oculta) em pontos do mapa.

    .venv\Scripts\python.exe scripts\check_match_views.py [--map coracao]
Salva PNGs em .scratch/match/ (com o prefixo do mapa fora do Bairro Arterial). Teleporta o
jogador local e adianta o estado (escolta, colonias, ferida fechada, criancas da medula,
valvas do coracao) para mostrar cada sistema na tela.
"""
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pyray as rl  # noqa: E402
from EasyCells3D import Game  # noqa: E402
from EasyCells3D.Components import Component  # noqa: E402
from EasyCells3D.Geometry import Vec3  # noqa: E402
from UserComponents.cells.session import connect  # noqa: E402

SHOTS = [
    # frame, name, slot, position, yaw, pitch, setup
    (200, 'avenida', 0, (0, 1, 66), 0, .05, None),
    (230, 'praca', 0, (-20, 1, 30), 2.4, -.05, 'escort40'),
    (260, 'escolta', 0, (6, 1, 30), -.6, -.12, 'escort40'),
    (290, 'canal', 0, (-24, -1.4, 0), 1.57, .05, None),
    (320, 'ponte_oeste', 0, (-30, 1, 18), -2.5, .05, None),
    (350, 'colonia', 3, (-50, 1, -26), 3.6, -.15, 'colony'),
    (380, 'obra', 0, (0, 1, -50), 0, -.12, 'escort120'),
    (410, 'ferida_fechada', 0, (-6, 1, -56), 0.2, -.25, 'closed'),
    (440, 'entrada_bacterias', 3, (0, -1.5, -84), 3.14, .02, None),
    (470, 'respawn', 3, (0, -1.5, -84), 3.14, .02, 'kill'),
]
MAP_SHOTS = {
    'bairro': SHOTS,
    'timo': [
        (200, 'dormitorio', 0, (0, 1, 56), 0, .02, None),
        (240, 'campo', 0, (-22, 1, 42), .9, -.05, 'escort:20'),
        (280, 'labirinto', 0, (3, 1, 14), 0, -.05, 'escort:46'),
        (320, 'labirinto_bacteria', 3, (-9, 1, -6), 3.14, -.05, 'escort:60'),
        (360, 'colonia', 3, (-24, 1, -16), 2.2, -.15, 'colony:-21,-20'),
        (400, 'ferida_fechada', 0, (-6, 1, -50), .2, -.2, 'closed'),
    ],
    'medula': [
        (420, 'gramado', 0, (-27, 1, 50), .85, -.05, 'kids'),
        (460, 'cidade', 0, (-4.5, 1, 31), 0, -.06, 'kids'),
        (500, 'caca', 3, (-4.5, 1, 18), 3.14, -.08, 'kids'),
        (540, 'choro', 3, (-12, 1, 28), 1.9, -.1, 'cry'),
        (580, 'arcada', 0, (32, 1, 24), 2.9, -.02, 'kids'),
        (620, 'formatura', 0, (-2, 1, -40), .5, -.1, 'closed'),
    ],
    'coracao': [
        (200, 'veia_cava', 0, (4, 1, 50), 0, .02, 'escort:2'),
        (240, 'templo', 0, (-8, 1, 34), .25, .02, 'escort:18'),
        (280, 'valva_fechada', 0, (3, 1, 9), -.15, .02, 'valve:0:closed'),
        (320, 'valva_aberta', 0, (3, 1, 9), -.15, .02, 'valve:0:open'),
        (360, 'endocardite', 0, (-7, 1, 4), .95, -.08, 'jam:0'),
        (400, 'ventriculo', 0, (16, 5, -34.5), -1.2, -.15, 'valve:1:closed'),
        (440, 'pulmao', 0, (-10, 1, -66), 2.2, -.05, 'closed'),
    ],
}
MAP = next((a.split('=', 1)[1] for a in sys.argv[1:] if a.startswith('--map=')), None)
if '--map' in sys.argv:
    MAP = sys.argv[sys.argv.index('--map')+1]
MAP = MAP or 'bairro'
SHOTS = MAP_SHOTS[MAP]
PREFIX = '' if MAP == 'bairro' else MAP+'_'


def place_kids(arena, cry=False):
    """Medula: tres criancas andando nas ruas perto da camera (e uma chorando, se ``cry``)."""
    from UserComponents.cells import layout
    hem = arena.hemacias
    for i, (node, dest) in enumerate((('Tb1', 'C'), ('Lb', 'B'), ('Ta1', 'A'), ('Tb2', 'C'))):
        kid = hem.cells[i]
        kid.reset(dest, hem.health)
        kid.pos = list(layout.RBC_NODES[node])
        kid.pos[2] += i*.7
        hem.replan(kid, hem.clock)
    if cry:
        hem.damage(0, 9999)
        arena.add_drop('resource', tuple(hem.cells[0].pos), 2)


class Probe(Component):
    def __init__(self):
        self.frame = 0

    def loop(self):
        self.frame += 1
        game = self.game
        arena = getattr(game.session, 'arena', None) if getattr(game, 'session', None) else None
        if arena is None:
            return
        for frame, name, slot, pos, yaw, pitch, setup in SHOTS:
            if self.frame == frame-25:
                roster = game.session.roster.value
                for s, p in roster.items():
                    p['owner'] = 0 if s != slot else game.session.manager.id
                    p['bot'] = s != slot
                actor = arena.actors[slot]
                if not actor.alive:
                    actor.spawn()
                actor.body.teleport(Vec3(*pos))
                state = arena.state
                if setup and setup.startswith('escort:'):
                    state.escort = float(setup.split(':')[1])
                elif setup == 'kids':
                    place_kids(arena)
                elif setup == 'cry':
                    place_kids(arena, cry=True)
                elif setup and setup.startswith('valve:'):
                    _, ident, mode = setup.split(':')
                    v = arena.valves[int(ident)]
                    state.escort = arena.valve_progress[v['id']]-2.3
                    from UserComponents.cells.heart import rhythm_open
                    from UserComponents.cells.catalog import BALANCE
                    t = .4 if (v['kind'] == 'av') == (mode == 'closed') else BALANCE['heart_systole']+.4
                    state.elapsed = t
                elif setup and setup.startswith('jam:'):
                    v = arena.valves[int(setup.split(':')[1])]
                    state.escort = arena.valve_progress[v['id']]-2.3
                    state.resources[slot] = 20
                    x, y, z = v['pos']
                    state.add_colony(slot, (x+5, 0, z+3.2))
                elif setup and setup.startswith('colony:'):
                    cx, cz = (float(c) for c in setup.split(':')[1].split(','))
                    state.resources[slot] = 20
                    state.add_colony(slot, (cx, 0, cz))
                    state.colonies[-1]['dev'] = 12
                elif setup == 'escort40':
                    state.escort = 40
                elif setup == 'escort120':
                    state.escort = 120
                elif setup == 'closed':
                    if state.mode == 'training':
                        state.escort = state.escort_total
                        state.seal()
                    else:
                        state.escort = state.escort_total-.01
                elif setup == 'colony':
                    state.resources[slot] = 20
                    state.add_colony(slot, (-53, 0, -30))
                    state.colonies[-1]['dev'] = 12
                elif setup == 'kill':
                    actor.damage(5000, arena.actors[0])
            if frame-25 <= self.frame <= frame:
                actor = arena.actors[slot]
                game.inputs.yaw, game.inputs.pitch = yaw, pitch
                actor.yaw = yaw
            if self.frame == frame:
                rl.take_screenshot(f'.scratch/match/{PREFIX}{name}.png')
                print('shot', name, flush=True)
        if self.frame > SHOTS[-1][0]+5:
            game.running = False


def main():
    os.chdir(ROOT)
    (ROOT/'.scratch/match').mkdir(parents=True, exist_ok=True)
    rl.set_trace_log_level(rl.TraceLogLevel.LOG_WARNING)
    rl.set_config_flags(rl.ConfigFlags.FLAG_WINDOW_HIDDEN)
    game = Game('menu', 'Match views', screen_resolution=(1280, 720), target_fps=60)
    connect(game, '127.0.0.1', 0, True, 'Worker 1146')
    game.session.map.value = MAP
    game.session.recording.value = False  # nao grava replay na pasta do jogador
    game.session.start(True)
    game.new_game('lobby', supress=True)
    item = game.CreateItem()
    item.destroy_on_load = False
    item.AddComponent(Probe())
    import UserComponents.cells.player as player_module
    original = player_module.PlayerInput.init

    def init(self):
        original(self)
        game.inputs = self
    player_module.PlayerInput.init = init
    try:
        game.run()
    finally:
        game.close()


if __name__ == '__main__':
    main()
