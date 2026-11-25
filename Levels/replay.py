"""Cena do replay: sem replay carregado mostra a lista; com um, a arena em 3ª pessoa."""
import pyray as rl
from EasyCells3D.Components import Camera3D
from EasyCells3D.PhysicsComponents3D import BulletPhysicsWorld
from UserComponents.cells.arena import Arena
from UserComponents.cells.actors import load_combatant
from UserComponents.cells.cursor import set_cursor_captured
from UserComponents.cells.replay import ReplayDirector
from UserComponents.cells.ui_base import load_ui
from UserComponents.cells.world import build_district


def build(game, visuals=True):
    """Arena de espectador alimentada pelo replay (``visuals=False`` nos testes sem janela)."""
    from UserComponents.cells import layout
    layout.select(game.session.map_key)
    game.physics_world = BulletPhysicsWorld()
    camera = game.CreateItem().AddComponent(Camera3D(vfov=75)) if visuals else None
    arena = game.CreateItem().AddComponent(Arena())
    arena.navigator = build_district(game)
    for slot, player in sorted(game.session.roster.value.items()):
        arena.actors[slot] = load_combatant(game, arena, slot, player)
    director = game.CreateItem().AddComponent(ReplayDirector(arena, camera, game.replay))
    if visuals:
        from UserComponents.cells.audio import AudioFeedback
        from UserComponents.cells.ability_fx import AbilityEffects
        from UserComponents.cells.outline import SilhouettePass
        from UserComponents.cells.shots import ShotEffects
        from UserComponents.cells.visuals import ArenaEffects
        game.CreateItem().AddComponent(ArenaEffects(arena))
        game.CreateItem().AddComponent(SilhouettePass(arena))
        game.CreateItem().AddComponent(AbilityEffects(arena))
        game.CreateItem().AddComponent(ShotEffects(arena))
        game.CreateItem().AddComponent(AudioFeedback(arena))
    return director


def init(game):
    set_cursor_captured(False)
    from UserComponents.cells.replay_screens import ReplayLibrary, ReplayOverlay
    if getattr(game, "replay", None) is None:
        game.time_scale = 1.0
        load_ui(game, ReplayLibrary())
        return
    director = build(game)
    from UserComponents.cells import layout
    game.background_color = rl.Color(*layout.EXTRA.get('background', (244, 233, 213)), 255)
    load_ui(game, ReplayOverlay(director))


def loop(game):
    pass
