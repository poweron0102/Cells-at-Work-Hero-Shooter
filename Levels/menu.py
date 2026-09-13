import pyray as rl
from UserComponents.cells.screens import MenuScreen
from UserComponents.cells.ui_base import load_ui


def init(game):
    rl.enable_cursor()
    load_ui(game, MenuScreen())


def loop(game):
    pass
