import pyray as rl
from UserComponents.cells.screens import ResultScreen
from UserComponents.cells.ui_base import load_ui


def init(game):
    rl.enable_cursor()
    load_ui(game, ResultScreen())


def loop(game):
    pass
