"""Capturas de uma partida de treino real (janela oculta) em pontos do mapa.

    .venv\Scripts\python.exe scripts\check_match_views.py
Salva PNGs em .scratch/match/. Teleporta o jogador local e adianta o estado
(escolta, colonias, ferida fechada) para mostrar cada sistema na tela.
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
                if setup == 'escort40':
                    state.escort = 40
                elif setup == 'escort120':
                    state.escort = 120
                elif setup == 'closed':
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
                rl.take_screenshot(f'.scratch/match/{name}.png')
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
