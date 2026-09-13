import pyray as rl
from UserComponents.cells.screens import ResultScreen
from UserComponents.cells.ui_base import load_ui
from UserComponents.cells.cursor import set_cursor_captured


def init(game):
    set_cursor_captured(False)
    load_ui(game, ResultScreen())


def loop(game):
    pass
