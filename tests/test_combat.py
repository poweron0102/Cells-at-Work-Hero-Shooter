import unittest
from simulation_support import headless_game, mount_arena, step
from EasyCells3D.Geometry import Vec3
from UserComponents.cells.session import connect
from UserComponents.cells.catalog import HEROES, BALANCE
from UserComponents.cells.world import block


class CombatIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.game = headless_game()
        self.net = connect(self.game, "127.0.0.1", 0, True, "Test host")
        self.net.start(True)
        # Keep all test actors still, using the production no-input path.
        for p in self.net.roster.value.values():
            p["bot"] = False
        self.arena = mount_arena(self.game)
        for _ in range(60):
            step(self.game)
        self.shooter, self.target = self.arena.actors[0], self.arena.actors[3]
        self.shooter.body.teleport(Vec3(0, 1, 60))
        self.target.body.teleport(Vec3(0, 1, 54))
        self.shooter.yaw = self.shooter.pitch = 0
        step(self.game)

    def tearDown(self):
        self.game.close()

    def total(self, actor):
        return actor.health.value+actor.shield.value

    def test_hitscan_damages_enemy_and_cover_blocks_it(self):
        health = self.total(self.target)
        self.shooter.weapon.fire()
        self.assertLess(self.total(self.target), health)
        block(self.game, "Test cover", (0, 1, 57), (3, 3, 1), (100, 100, 100))
        step(self.game)
        self.shooter.weapon.timer = 0
        health = self.total(self.target)
        self.shooter.weapon.fire()
        self.assertEqual(self.total(self.target), health)

    def test_dealing_damage_charges_the_special_but_time_does_not(self):
        # Away from the escort (escorting is an objective and does charge).
        self.shooter.body.teleport(Vec3(0, 1, 40))
        self.target.body.teleport(Vec3(0, 1, 34))
        self.shooter.charge = 0
        step(self.game)
        for _ in range(120):
            step(self.game)
        self.assertEqual(self.shooter.charge, 0)
        self.shooter.weapon.fire()
        self.assertGreater(self.shooter.charge, 0)

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
        self.assertEqual(self.target.killer, self.shooter.slot)
        for _ in range(int(BALANCE['respawn_seconds']*60)+5):
            step(self.game)
        self.assertTrue(self.target.alive)
        self.assertTrue(self.target.body.enable)
        self.assertEqual(self.target.health.value, HEROES[self.target.hero].health)

    def test_bacterium_drops_antigen_and_carried_resources(self):
        self.arena.state.resources[3] = 4
        self.target.damage(2000, self.shooter)
        kinds = sorted(d['kind'] for d in self.arena.drops)
        self.assertEqual(kinds, ['antigen', 'resource'])
        self.assertEqual(self.arena.state.resources[3], 0)

    def test_cells_collect_antigen_physically_and_destroy_resources(self):
        self.arena.add_drop('antigen', self.shooter.feet, 1)
        self.arena.add_drop('resource', self.shooter.feet, 3)
        step(self.game)
        self.assertFalse(self.arena.drops)
        self.assertEqual(self.arena.state.recognition, BALANCE['antigen_per_sample'])
        self.assertEqual(sum(self.arena.state.resources.values()), 0)

    def test_macrophage_slam_knocks_back_and_b_cell_marks(self):
        self.shooter.hero = 'macrophage'
        self.target.body.teleport(Vec3(0, 1, 57.5))
        step(self.game)
        self.shooter.ability()
        for _ in range(10):
            step(self.game)
        self.assertGreater(abs(self.target.transform.z-57.5), .5)
        self.shooter.hero = 'b_cell'
        self.shooter.ability_cd = 0
        self.target.body.teleport(Vec3(0, 1, 54))
        step(self.game)
        self.shooter.ability()
        self.assertGreater(self.target.marked, 0)

    def test_b_cell_zoom_follows_the_mouse_and_resets_on_death(self):
        self.shooter.hero = 'b_cell'
        self.shooter.controls = dict(secondary=True, yaw=0, pitch=0)
        step(self.game)
        self.assertTrue(self.shooter.zoom)
        self.shooter.damage(5000, self.target)
        step(self.game)
        self.assertFalse(self.shooter.zoom)


if __name__ == "__main__":
    unittest.main()
