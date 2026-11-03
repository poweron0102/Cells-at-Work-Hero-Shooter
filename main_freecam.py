"""Standalone map reference viewer: fly freely and press P to capture."""
import argparse
import os
from pathlib import Path

import pyray as rl
from EasyCells3D import Game


def main():
    parser = argparse.ArgumentParser(description="Camera livre do Bairro Arterial")
    parser.add_argument("--output", type=Path, default=Path("capturas"),
                        help="Pasta dos prints e dados da camera (padrao: capturas)")
    parser.add_argument("--frames", type=int, default=0, help=argparse.SUPPRESS)
    parser.add_argument("--capture", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--hidden", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    os.chdir(Path(__file__).resolve().parent)
    rl.set_trace_log_level(rl.LOG_WARNING)
    if args.hidden:
        rl.set_config_flags(rl.FLAG_WINDOW_HIDDEN)
    game = Game("freecam", "Cells at Work | Camera livre", screen_resolution=(1280, 720),
                dynamic_resolution=not args.hidden, target_fps=60)
    try:
        game.reference_camera.output = args.output.resolve()
        game.reference_camera.frame_limit = args.frames
        game.reference_camera.capture_on_exit = args.capture
        game.run()
    finally:
        game.close()


if __name__ == "__main__":
    main()
