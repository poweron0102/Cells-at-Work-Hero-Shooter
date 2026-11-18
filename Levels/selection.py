from UserComponents.cells.screens import LobbyScreen
from UserComponents.cells.ui_base import load_ui
from UserComponents.cells.cursor import set_cursor_captured


def init(game):
    # A seleção de personagem agora fica embutida no lobby (tira de retratos + prévia do kit).
    set_cursor_captured(False)
    load_ui(game, LobbyScreen(picking=True))


def loop(game):
    if game.session.status in ("loading", "playing"):
        game.new_game("abrasion")
