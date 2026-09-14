from UserComponents.cells.screens import LobbyScreen
from UserComponents.cells.ui_base import load_ui
from UserComponents.cells.cursor import set_cursor_captured


def init(game):
    set_cursor_captured(False)
    load_ui(game, LobbyScreen())


def loop(game):
    if game.session.status in ("loading", "playing"):
        game.new_game("abrasion")
