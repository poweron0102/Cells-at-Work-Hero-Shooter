"""Exercise real scene changes, GPU rendering and cleanup in a hidden window."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pyray as rl
from EasyCells3D import Game
from EasyCells3D.Components import Component
from UserComponents.cells.session import connect, disconnect
from UserComponents.cells import replay


class SceneProbe(Component):
    def __init__(self):
        self.frame = 0

    def capture(self, name):
        rl.take_screenshot(f".scratch/scenes/{name}.png")
        print(f"CAPTURE {name}: {len(self.game.cameras)} cameras / {len(self.game.item_list)} root items", flush=True)

    def loop(self):
        self.frame += 1
        f, game = self.frame, self.game
        if f == 8:
            self.capture("menu")
            connect(game, "127.0.0.1", 0, True, "Worker 1146")
            game.new_game("lobby")
        elif f == 16:
            self.capture("lobby")
            game.new_game("selection")
        elif f == 24:
            self.capture("selection")
            game.session.recording.value = True  # grava o replay desta partida
            game.session.start(True)
            game.new_game("abrasion")
        elif f == 150:
            self.capture("combat")
            game.session.arena.actors[0].damage(1000, game.session.arena.actors[3])
        elif f == 156:
            self.capture("respawn")
            game.session.arena.state.escort = 60
        elif f == 165:
            self.capture("escort")
            game.session.arena.state.escort = game.session.arena.state.escort_total
        elif f == 173:
            self.capture("wound_closed")
            game.session.arena.state.winner = "cells"
        elif f == 420:
            if game.current_level != "results":
                raise SystemExit("FAIL: results scene not reached")
            self.capture("results")
            saved = getattr(game, "last_replay", None)
            if saved is None or not saved.exists():
                raise SystemExit("FAIL: match replay was not saved")
            from UserComponents.cells.replay_screens import open_from_file
            error = open_from_file(game, saved)
            raise SystemExit(f"FAIL: replay did not open: {error}")
        elif f == 440:
            if game.current_level != "replay" or game.replay is None:
                raise SystemExit("FAIL: replay scene not reached")
            self.capture("replay")
            self.director().seek(game.replay.data.duration)
        elif f == 448:
            self.capture("replay_end")
            self.director().seek(1.0)  # voltar no tempo remonta a cena
        elif f == 456:
            if abs(self.director().clock - 1.0) > .2:
                raise SystemExit("FAIL: backward seek did not rebuild the replay")
            self.capture("replay_rewind")
            replay.close_replay(game)
        elif f == 464:
            self.capture("replay_library")
            if game.session is not None or game.time_scale != 1.0:
                raise SystemExit("FAIL: replay session left behind")
            game.new_game("menu")
        elif f == 472:
            self.capture("menu_after_match")
            if len(game.cameras) != 1 or game.physics_world is not None:
                raise SystemExit("FAIL: stale scene resources")
            game.running = False

    def director(self):
        return next(d for d in (item.GetComponent(replay.ReplayDirector) for item in self.game.item_list) if d)


def main():
    os.chdir(ROOT)
    (ROOT/".scratch/scenes").mkdir(parents=True, exist_ok=True)
    replay.REPLAY_DIR = ROOT/".scratch/scenes/replays"  # não suja a pasta replays/ do jogador
    rl.set_trace_log_level(rl.TraceLogLevel.LOG_WARNING)
    rl.set_config_flags(rl.ConfigFlags.FLAG_WINDOW_HIDDEN)
    game = Game("menu", "Scene verification", screen_resolution=(1280, 720), target_fps=60)
    item = game.CreateItem()
    item.destroy_on_load = False
    item.AddComponent(SceneProbe())
    try:
        game.run()
    finally:
        game.close()
    print("PASS: all scenes, respawn, results, replay (play, seek, rewind, library), return to menu, "
          "physics and camera cleanup")


if __name__ == "__main__":
    main()
