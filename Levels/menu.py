import pyray as rl
from UserComponents.cells.screens import MenuScreen
from UserComponents.cells.ui_base import load_ui
from UserComponents.cells.cursor import set_cursor_captured


def init(game):
    set_cursor_captured(False)
    load_ui(game, MenuScreen())


def loop(game):
    pass
