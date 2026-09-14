"""Drive the real engine components without creating a graphics context."""
from types import ModuleType
from EasyCells3D import Game
from EasyCells3D.Components import Camera3D
from EasyCells3D.PhysicsComponents3D import BulletPhysicsWorld
from UserComponents.cells.arena import Arena
from UserComponents.cells.actors import load_combatant
from UserComponents.cells.world import build_abrasion


def headless_game():
    level = ModuleType("headless_test")
    level.init = lambda game: None
    level.loop = lambda game: None
    return Game(level, "Simulation test", render_target=True)


def mount_arena(game):
    game.physics_world = BulletPhysicsWorld()
    arena = game.CreateItem().AddComponent(Arena())
    arena.navigator, arena.gate = build_abrasion(game)
    for slot, player in game.session.roster.value.items():
        arena.actors[slot] = load_combatant(game, arena, slot, player)
    return arena


def step(game, dt=1/60):
    game.delta_time = dt
    game.run_time += dt
    for function in game.to_init:
        function()
    game.to_init.clear()
    for item in list(game.item_list):
        # Call directly so component exceptions fail a test instead of being logged.
        item._global_transform = item.transform.clone()
        for component in item._unique_components():
            if component.enable:
                component.loop()
    game.scheduler.update()
    if game.physics_world:
        game.physics_world.step(dt)
