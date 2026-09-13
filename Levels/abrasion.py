"""Scene assembly only. Entity behavior lives in UserComponents/cells/."""
import pyray as rl
from EasyCells3D.Components import Camera3D
from EasyCells3D.PhysicsComponents3D import BulletPhysicsWorld
from UserComponents.cells.arena import Arena
from UserComponents.cells.audio import AudioFeedback
from UserComponents.cells.actors import load_combatant
from UserComponents.cells.director import StressDirector
from UserComponents.cells.hud import CombatHUD
from UserComponents.cells.player import PlayerInput
from UserComponents.cells.ui_base import load_ui
from UserComponents.cells.visuals import ArenaEffects
from UserComponents.cells.world import build_abrasion


def init(game):
    game.background_color = rl.Color(199, 220, 214, 255)
    game.physics_world = BulletPhysicsWorld()
    camera = game.CreateItem().AddComponent(Camera3D(vfov=75))
    arena = game.CreateItem().AddComponent(Arena(game.session.is_server))
    arena.navigator, arena.gate = build_abrasion(game)
    for slot, player in sorted(game.session.roster.items()):
        arena.actors[slot] = load_combatant(game, arena, slot, player)
    game.CreateItem().AddComponent(StressDirector(arena))
    game.CreateItem().AddComponent(ArenaEffects(arena))
    inputs = game.CreateItem().AddComponent(PlayerInput(arena, camera))
    load_ui(game, CombatHUD(arena, inputs))
    game.CreateItem().AddComponent(AudioFeedback(arena))


def loop(game):
    if game.session.status == "results":
        game.new_game("results")
