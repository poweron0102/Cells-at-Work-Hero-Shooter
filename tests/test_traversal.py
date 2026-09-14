"""Real Bullet traversal of production ramps, roof gaps and exclusive ledges."""
import math
import unittest
from simulation_support import headless_game, mount_arena, step
from EasyCells3D.Geometry import Vec3
from UserComponents.cells.session import connect
from UserComponents.cells.catalog import HEROES, POINTS, CORE_POSITIONS


class TraversalTests(unittest.TestCase):
    def setUp(self):
        self.game = headless_game()
        self.net = connect(self.game, '127.0.0.1', 0, True, 'Traversal')
        self.net.start(True)
        for player in self.net.roster.value.values():
            player['bot'] = False
        self.arena = mount_arena(self.game)
        for _ in range(30):
            step(self.game)
        self.actor = self.arena.actors[0]

    def tearDown(self):
        self.game.close()

    def place(self, hero, position):
        self.actor.hero = hero
        self.actor.controls = {}
        self.actor.body.teleport(Vec3(*position))
        self.actor.previous = {}
        for _ in range(25):
            step(self.game)

    def drive(self, frames, **command):
        for _ in range(frames):
            self.actor.controls = command
            step(self.game)

    def test_slowest_hero_walks_up_ramp_and_lands_on_roof(self):
        self.place('macrophage', (14, 1, 46.8))
        self.drive(225, yaw=0, z=1)
        self.drive(30)
        self.assertLess(self.actor.transform.z, 30)
        self.assertAlmostEqual(self.actor.transform.y, 4.95, delta=.12)
        self.assertTrue(self.actor.controller.is_grounded)
        start = self.actor.transform.y
        self.drive(16, jump=True)
        self.assertGreater(self.actor.transform.y, start+.6)
        self.drive(90)
        self.assertAlmostEqual(self.actor.transform.y, start, delta=.12)

    def test_tower_requires_high_jump_from_gallery(self):
        for hero, can_reach in (('macrophage', False), ('killer_t', True), ('pseudomonas', True)):
            with self.subTest(hero=hero):
                self.place(hero, (28.7, 5, 22))
                self.drive(45, yaw=math.pi/2, z=1, jump=True)
                self.drive(60)
                if can_reach:
                    self.assertGreater(self.actor.transform.x, 32)
                    self.assertAlmostEqual(self.actor.transform.y, 7.95, delta=.15)
                else:
                    self.assertLess(self.actor.transform.y, 7)

    def test_fast_flanker_crosses_gap_slow_hero_falls_safely(self):
        for hero, can_reach in (('macrophage', False), ('streptococcus', True)):
            with self.subTest(hero=hero):
                self.place(hero, (-4.9, 5, -22))
                self.drive(59, yaw=math.pi/2, z=1, sprint=True, jump=True)
                self.drive(70)
                if can_reach:
                    self.assertGreater(self.actor.transform.x, 4.5)
                    self.assertAlmostEqual(self.actor.transform.y, 4.95, delta=.15)
                else:
                    self.assertAlmostEqual(self.actor.transform.y, .95, delta=.15)

    def test_spawn_routes_reach_every_objective_with_gate_open_or_closed(self):
        nav = self.arena.navigator
        for closed in (False, True):
            self.arena.gate.enable = closed
            for slot in range(6):
                for x, z in POINTS+CORE_POSITIONS:
                    path = nav.path(self.arena.spawn_position(slot), Vec3(x, 1, z))
                    self.assertTrue(path, (closed, slot, x, z))
                    self.assertLess((path[-1]-Vec3(x, 1, z)).magnitude(), 2.1)

    def test_navigation_can_climb_public_roof(self):
        path = self.arena.navigator.path(Vec3(14, 1, 46), Vec3(14, 4.95, 28))
        self.assertTrue(path)
        self.assertAlmostEqual(path[-1].y, 4.95)
        self.assertTrue(any(1.5 < node.y < 4.5 for node in path))


if __name__ == '__main__':
    unittest.main()
