from UserComponents.cells.screens import SelectionScreen
from UserComponents.cells.ui_base import load_ui


def init(game):
    load_ui(game, SelectionScreen())


def loop(game):
    if game.session.status == "playing":
        game.new_game("abrasion")
