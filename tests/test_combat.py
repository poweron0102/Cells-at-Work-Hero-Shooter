import unittest
from simulation_support import headless_game, mount_arena, step
from EasyCells3D.Geometry import Vec3
from UserComponents.cells.network import connect
from UserComponents.cells.catalog import HEROES
from UserComponents.cells.world import block


class CombatIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.game = headless_game()
        self.net = connect(self.game, "127.0.0.1", 0, True, "Test host")
        self.net.start(True)
        # Keep all test actors still, using the production no-input path.
        for p in self.net.roster.values():
            p["bot"] = False
        self.arena = mount_arena(self.game)
        for _ in range(60):
            step(self.game)
        self.shooter, self.target = self.arena.actors[0], self.arena.actors[3]
        self.shooter.body.teleport(Vec3(0, 1, 20))
        self.target.body.teleport(Vec3(0, 1, 14))
        self.shooter.yaw = self.shooter.pitch = 0

    def tearDown(self):
        self.game.close()

    def test_hitscan_damages_enemy_and_cover_blocks_it(self):
        health = self.target.health+self.target.shield
        self.shooter.weapon.fire()
        self.assertLess(self.target.health+self.target.shield, health)
        block(self.game, "Test cover", (0, 1, 17), (3, 3, 1), (100, 100, 100))
        step(self.game)
        self.shooter.weapon.timer = 0
        health = self.target.health+self.target.shield
        self.shooter.weapon.fire()
        self.assertEqual(self.target.health+self.target.shield, health)

    def test_jump_uses_engine_ground_check_and_gravity(self):
        for _ in range(20):
            step(self.game)
        self.assertTrue(self.shooter.controller.is_grounded)
        initial_y = self.shooter.transform.y
        self.shooter.controller.jump()
        for _ in range(12):
            step(self.game)
        self.assertGreater(self.shooter.transform.y, initial_y+.3)
        for _ in range(120):
            step(self.game)
        self.assertAlmostEqual(self.shooter.transform.y, initial_y, delta=.1)

    def test_reload_death_and_respawn_reset_combatant(self):
        self.shooter.weapon.ammo = 0
        self.shooter.weapon.reload()
        for _ in range(100):
            step(self.game)
        self.assertEqual(self.shooter.weapon.ammo, HEROES[self.shooter.hero].magazine)
        self.target.damage(2000, self.shooter)
        self.assertFalse(self.target.alive)
        self.assertFalse(self.target.body.enable)
        for _ in range(365):
            step(self.game)
        self.assertTrue(self.target.alive)
        self.assertTrue(self.target.body.enable)
        self.assertEqual(self.target.health, HEROES[self.target.hero].health)

    def test_collection_cannot_pass_through_cover(self):
        self.arena.state.phase = 1
        self.arena.samples = [dict(pos=(0, 1, 18), life=20)]
        block(self.game, "Sample cover", (0, 1, 19), (3, 3, .3), (100, 100, 100))
        step(self.game)
        self.arena.collect(self.shooter)
        self.assertEqual(self.arena.state.recognition, 0)


if __name__ == "__main__":
    unittest.main()
