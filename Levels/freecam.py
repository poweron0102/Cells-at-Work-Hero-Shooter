"""Map inspection without a match, network session, actors or collisions."""
import pyray as rl
from UserComponents.cells.reference_camera import ReferenceCamera
from UserComponents.cells.scenery import DistrictScenery


def init(game):
    game.background_color = rl.Color(146, 153, 159, 255)
    game.reference_camera = game.CreateItem().AddComponent(ReferenceCamera())
    game.CreateItem().AddComponent(DistrictScenery())


def loop(game):
    pass
