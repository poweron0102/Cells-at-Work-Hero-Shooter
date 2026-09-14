"""Cells at Work: Abrasion. Python 3.14 / EasyCells3D."""
import argparse
import os
from pathlib import Path
import pyray as rl
from EasyCells3D import Game
from EasyCells3D.Components import Component
from UserComponents.cells.session import connect


class FrameLimit(Component):
    """Optional unattended capture used by the smoke checks."""
    def __init__(self, frames, screenshot):
        self.frames, self.screenshot = frames, screenshot

    def loop(self):
        self.frames -= 1
        if self.frames <= 0:
            if self.screenshot:
                path = Path(self.screenshot).resolve()
                path.parent.mkdir(parents=True, exist_ok=True)
                rl.take_screenshot(Path(os.path.relpath(path, Path.cwd())).as_posix())
            self.game.running = False


def main():
    parser = argparse.ArgumentParser(description="Cells at Work / Abrasion LAN prototype")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--host", action="store_true")
    mode.add_argument("--join", metavar="IP")
    parser.add_argument("--port", type=int, default=25765)
    parser.add_argument("--name", default="Worker 1146")
    parser.add_argument("--training", action="store_true", help="Host a practice match with five bots")
    parser.add_argument("--frames", type=int, default=0, help=argparse.SUPPRESS)
    parser.add_argument("--screenshot", help=argparse.SUPPRESS)
    parser.add_argument("--hidden", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.training and args.join:
        parser.error("--training cannot be combined with --join")
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    os.chdir(Path(__file__).resolve().parent)
    rl.set_trace_log_level(rl.TraceLogLevel.LOG_WARNING)
    if args.hidden:
        rl.set_config_flags(rl.ConfigFlags.FLAG_WINDOW_HIDDEN)
    game = Game("menu", "Cells at Work | Abrasion", screen_resolution=(1280, 720),
                dynamic_resolution=not args.hidden, target_fps=60)
    try:
        if args.host or args.join or args.training:
            connect(game, args.join or "0.0.0.0", args.port, not bool(args.join), args.name)
            if args.training:
                game.session.start(True)
            game.new_game("lobby", supress=True)
        if args.frames:
            probe = game.CreateItem()
            probe.destroy_on_load = False
            probe.AddComponent(FrameLimit(args.frames, args.screenshot))
        game.run()
    finally:
        game.close()


if __name__ == "__main__":
    main()
