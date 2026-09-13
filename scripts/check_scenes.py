"""Exercise real scene changes, GPU rendering and cleanup in a hidden window."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pyray as rl
from EasyCells3D import Game
from EasyCells3D.Components import Component
from UserComponents.cells.network import connect, disconnect


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
            game.session.start(True)
            game.new_game("abrasion")
        elif f == 150:
            self.capture("combat")
            game.session.arena.actors[0].damage(1000, game.session.arena.actors[3])
        elif f == 156:
            self.capture("respawn")
            game.session.arena.state.phase = 1
        elif f == 165:
            self.capture("identification")
            game.session.arena.state.phase = 2
            game.session.arena.state.infected = True
        elif f == 173:
            self.capture("colonization")
            game.session.arena.state.winner = "cells"
        elif f == 340:
            if game.current_level != "results":
                raise SystemExit("FAIL: results scene not reached")
            self.capture("results")
            disconnect(game)
            game.new_game("menu")
        elif f == 350:
            self.capture("menu_after_match")
            if len(game.cameras) != 1 or game.physics_world is not None:
                raise SystemExit("FAIL: stale scene resources")
            game.running = False


def main():
    os.chdir(ROOT)
    (ROOT/".scratch/scenes").mkdir(parents=True, exist_ok=True)
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
    print("PASS: all scenes, respawn, results, return to menu, physics and camera cleanup")


if __name__ == "__main__":
    main()
