"""Travessia real (Bullet) no Bairro Arterial exportado do Blender."""
import math
import unittest
from simulation_support import headless_game, mount_arena, step
from EasyCells3D.Geometry import Vec3
from UserComponents.cells.session import connect
from UserComponents.cells.layout import (CELL_SPAWNS, BACTERIA_ENTRANCE, ESCORT_PATH, RBC_NODES, DESTINATIONS,
                                         COLONY_HINTS, RECON, CANAL)


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

    def ground(self, x, z, top=12):
        hit = self.game.physics_world.raycast(Vec3(x, top, z), Vec3(0, -1, 0), top+6, 1)
        return hit.point.y if hit else None

    def test_every_spawn_lands_on_safe_ground(self):
        for slot, actor in self.arena.actors.items():
            expected = CELL_SPAWNS[slot % 3] if slot < 3 else BACTERIA_ENTRANCE[slot % 3]
            self.assertAlmostEqual(actor.transform.y, expected[1]+.95, delta=.15)
            self.assertTrue(actor.controller.is_grounded)

    def test_markers_sit_on_walkable_ground(self):
        for name, p in list(RBC_NODES.items())+[('recon', RECON)]+[(f'escort{i}', p) for i, p in enumerate(ESCORT_PATH)]:
            with self.subTest(marker=name):
                y = self.ground(p[0], p[2], p[1]+1.5)
                self.assertIsNotNone(y)
                self.assertAlmostEqual(y, p[1], delta=.35)

    def test_slowest_hero_leaves_canal_by_ramps(self):
        # Ramps along both banks rise toward the higher end (south bank west of the central bridge).
        for start, yaw, bank in (((-6, -1.4, 4.5), -math.pi/2, math.pi), ((6, -1.4, -4.5), math.pi/2, 0)):
            with self.subTest(start=start):
                self.place('macrophage', start)
                self.drive(120, yaw=yaw, z=1)
                self.drive(60, yaw=bank, z=1)
                self.drive(20)
                self.assertAlmostEqual(self.actor.transform.y, .95, delta=.2)
                self.assertTrue(self.actor.controller.is_grounded)

    def test_bridges_cross_without_falling(self):
        for x in (-40, 0, 40):
            with self.subTest(bridge=x):
                self.place('macrophage', (x, 1, 16))
                self.drive(440, yaw=0, z=1)
                self.assertLess(self.actor.transform.z, -13)
                self.assertAlmostEqual(self.actor.transform.y, .95, delta=.2)

    def test_underpass_keeps_the_canal_route(self):
        self.place('macrophage', (-10, -1.4, 0))
        self.drive(260, yaw=math.pi/2, z=1)
        self.assertGreater(self.actor.transform.x, 6)
        self.assertAlmostEqual(self.actor.transform.y, CANAL[2]+.95, delta=.2)

    def test_walkways_are_reachable_by_stairs(self):
        self.place('macrophage', (-8.8, 1, 72))
        self.drive(240, yaw=0, z=1)
        self.assertGreater(self.actor.transform.y, 4.8)

    def test_navigation_reaches_every_objective_from_both_bases(self):
        nav = self.arena.navigator
        goals = [ESCORT_PATH[0], ESCORT_PATH[-1], RECON]+[RBC_NODES[d] for doors in DESTINATIONS.values() for d in doors]
        goals += COLONY_HINTS
        for start in (CELL_SPAWNS[0], BACTERIA_ENTRANCE[0]):
            for goal in goals:
                with self.subTest(start=start, goal=goal):
                    path = nav.path(Vec3(start[0], start[1]+.95, start[2]), Vec3(goal[0], goal[1]+.95, goal[2]))
                    self.assertTrue(path)
                    self.assertLess((path[-1]-Vec3(goal[0], goal[1]+.95, goal[2])).magnitude(), 2.6)

    def test_bases_have_no_direct_line_of_sight(self):
        world = self.game.physics_world
        for a in CELL_SPAWNS:
            for b in BACTERIA_ENTRANCE:
                start = Vec3(a[0], a[1]+1.5, a[2])
                delta = Vec3(b[0], b[1]+1.5, b[2])-start
                self.assertIsNotNone(world.raycast(start, delta, delta.magnitude(), 1))

    def test_bot_leaves_station_and_reaches_the_escort(self):
        self.actor.hero = 'macrophage'
        roster = self.net.roster.value
        roster[0]['bot'] = True
        target = Vec3(*ESCORT_PATH[0])
        for _ in range(1800):
            step(self.game)
            if Vec3(self.actor.transform.x-target.x, 0, self.actor.transform.z-target.z).magnitude() < 6:
                break
        self.assertLess(Vec3(self.actor.transform.x-target.x, 0, self.actor.transform.z-target.z).magnitude(), 6)


if __name__ == '__main__':
    unittest.main()
