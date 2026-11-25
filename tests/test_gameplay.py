"""Integracao: hemacias, colonias, respawn por colonia, escolta e reconhecimento."""
import math
import unittest
from simulation_support import headless_game, mount_arena, step
from EasyCells3D.Geometry import Vec3
from UserComponents.cells.session import connect
from UserComponents.cells.catalog import BALANCE, CELLS
from UserComponents.cells.layout import RBC_NODES, RECON, ESCORT_PATH
from UserComponents.cells import npcs


class GameplayTests(unittest.TestCase):
    def setUp(self):
        self.game = headless_game()
        self.net = connect(self.game, "127.0.0.1", 0, True, "Gameplay")
        self.net.start(True)
        for p in self.net.roster.value.values():
            p["bot"] = False
        self.arena = mount_arena(self.game)
        for _ in range(30):
            step(self.game)
        self.state = self.arena.state

    def tearDown(self):
        self.game.close()

    def run_for(self, seconds):
        for _ in range(int(seconds*30)):
            step(self.game, 1/30)

    # -- hemacias ---------------------------------------------------------
    def first_rbc(self):
        hem = self.arena.hemacias
        cell = hem.cells[0]
        cell.reset('A')
        hem.replan(cell, hem.clock)
        return hem, cell

    def test_red_blood_cells_deliver_to_different_buildings(self):
        self.run_for(140)
        delivered = {k: v for k, v in self.arena.hemacias.deliveries.items() if v}
        self.assertGreaterEqual(len(delivered), 2, self.arena.hemacias.deliveries)

    def test_threat_in_sight_causes_detour_and_walls_hide_threats(self):
        hem, cell = self.first_rbc()
        original = list(cell.path)
        bacterium = self.arena.actors[3]
        # A bacterium standing on the planned route, in plain sight.
        route_node = RBC_NODES[original[1]]
        bacterium.body.teleport(Vec3(route_node[0], route_node[1]+1, route_node[2]))
        cell.pos = list(RBC_NODES['S'])
        cell.yaw = math.atan2(route_node[0]-cell.pos[0], -(route_node[2]-cell.pos[2]))
        step(self.game, 1/30)
        hem.perceive(cell, [bacterium], hem.clock)
        self.assertIn(3, cell.threats)
        self.assertNotEqual(cell.path, original[1:])
        # Behind the station wall the same bacterium is not perceived.
        hem2, cell2 = hem, hem.cells[1]
        cell2.reset('B')
        hem2.replan(cell2, hem2.clock)
        bacterium.body.teleport(Vec3(0, 1, 86))  # inside the cells' station
        step(self.game, 1/30)
        cell2.pos = [0, 0, 66]
        cell2.yaw = 0
        hem2.perceive(cell2, [bacterium], hem2.clock)
        self.assertNotIn(3, cell2.threats)

    def test_detour_when_one_route_is_watched(self):
        hem, cell = self.first_rbc()
        cell.pos = list(RBC_NODES['S'])
        cell.threats = {3: (RBC_NODES['SW'], hem.clock)}
        hem.replan(cell, hem.clock)
        self.assertEqual(cell.state, 'deliver')
        self.assertNotIn('SW', cell.path)
        self.assertIn(cell.path[-1], ('A_e', 'A_n'))

    def test_no_safe_route_means_retreat_not_suicide_and_later_resume(self):
        hem, cell = self.first_rbc()
        # Every street leaving the junction is watched: there is no safe detour.
        threats = {s: (RBC_NODES[n], hem.clock) for s, n in ((3, 'SW'), (4, 'P'), (5, 'P2'), (6, 'SE'))}
        cell.pos = list(RBC_NODES['S'])
        cell.threats = dict(threats)
        hem.replan(cell, hem.clock)
        self.assertEqual(cell.state, 'flee')
        for t in threats.values():
            self.assertGreater(math.dist(RBC_NODES[cell.path[0]], t[0]), 6)
        cell.threats.clear()
        cell.calm_since = hem.clock-10
        hem.perceive(cell, [], hem.clock)
        self.assertEqual(cell.state, 'deliver')

    def test_every_route_follows_the_streets_even_when_fleeing_mid_block(self):
        hem, cell = self.first_rbc()
        # Halfway down the street S -> SW, with a bacterium right ahead.
        s, sw = RBC_NODES['S'], RBC_NODES['SW']
        cell.pos = [(s[0]+sw[0])/2, 0, (s[2]+sw[2])/2]
        cell.threats = {3: ((cell.pos[0]-4, 0, cell.pos[2]), hem.clock)}
        hem.replan(cell, hem.clock)
        self.assertIn(cell.path[0], ('S', 'SW'))  # first leg stays on the current street
        for a, b in zip(cell.path, cell.path[1:]):
            self.assertIn(b, npcs.graph()[a])
        self.assertNotEqual(cell.path[0], 'SW')  # never runs through the bacterium

    def test_scared_cells_scatter_in_different_safe_directions(self):
        hem, cell = self.first_rbc()
        # Junction with the delivery street watched on both sides: each scared cell draws its own escape.
        threats = {3: (RBC_NODES['A_e'], hem.clock), 4: (RBC_NODES['WSc'], hem.clock)}
        firsts, spots = set(), set()
        for _ in range(24):
            cell.reset('A')
            cell.pos = list(RBC_NODES['WBs'])
            cell.threats = dict(threats)
            hem.replan(cell, hem.clock)
            self.assertEqual(cell.state, 'flee')
            firsts.add(cell.path[0])
            for a, b in zip(cell.path, cell.path[1:]):
                self.assertIn(b, npcs.graph()[a])  # still along the streets
            route = [cell.pos]+[RBC_NODES[n] for n in cell.path]
            cost = sum(npcs.leg_cost(p, q, [t[0] for t in threats.values()], 9.0)-math.dist(p, q)
                       for p, q in zip(route, route[1:]))
            self.assertEqual(cost, 0)  # never runs towards a threat
            if cell.tail:
                spots.add((round(cell.tail[0], 1), round(cell.tail[2], 1)))
        self.assertGreaterEqual(len(firsts), 2, firsts)
        self.assertGreaterEqual(len(spots), 4, spots)

    def test_bacterium_close_by_scares_even_with_a_safe_detour(self):
        hem, cell = self.first_rbc()
        cell.pos = list(RBC_NODES['S'])
        cell.threats = {3: ((cell.pos[0]+3, 0, cell.pos[2]+2), hem.clock)}
        hem.replan(cell, hem.clock)
        self.assertEqual(cell.state, 'flee')
        cell.threats.clear()
        cell.calm_since = hem.clock-10
        hem.perceive(cell, [], hem.clock)
        self.assertEqual(cell.state, 'deliver')

    def test_cells_leave_the_depot_one_at_a_time_and_wait_while_the_door_is_watched(self):
        hem = self.arena.hemacias
        for cell in hem.cells:
            cell.state, cell.timer = 'inside', 99
        a, b = hem.cells[0], hem.cells[1]
        a.timer = b.timer = 0
        bacterium = self.arena.actors[3]
        door = RBC_NODES['depot_out']
        bacterium.body.teleport(Vec3(door[0], door[1]+1, door[2]-6))
        step(self.game, 1/30)
        hem.tick(1/30, [bacterium])
        self.assertEqual((a.state, b.state), ('inside', 'inside'))
        bacterium.body.teleport(Vec3(60, 1, -60))
        step(self.game, 1/30)
        hem.tick(1/30, [bacterium])
        self.assertEqual(sum(c.state != 'inside' for c in (a, b)), 1)
        for _ in range(int(npcs.DOOR_GAP*30)+2):
            hem.tick(1/30, [])
        self.assertNotIn('inside', (a.state, b.state))

    def test_cells_on_the_same_street_keep_their_distance(self):
        hem = self.arena.hemacias
        for cell in hem.cells:
            cell.state, cell.timer = 'inside', 99
        lead, back = hem.cells[0], hem.cells[1]
        s, sw = RBC_NODES['S'], RBC_NODES['SW']
        for cell, k in ((lead, .2), (back, .2-1.0/math.dist(s, sw))):
            cell.reset('A')
            cell.pos = [s[0]+(sw[0]-s[0])*k, s[1], s[2]+(sw[2]-s[2])*k]
            cell.state, cell.path, cell.threats = 'deliver', ['SW', 'A_e'], {}
        for _ in range(60):
            hem.tick(1/30, [])
            self.assertGreater(math.dist(lead.pos, back.pos), .9)

    def test_killing_a_red_blood_cell_drops_resources_for_bacteria(self):
        hem, cell = self.first_rbc()
        self.arena.hit_rbc(3, cell.id, 999)
        self.assertEqual(cell.state, 'dead')
        self.assertEqual(self.arena.drops[-1]['kind'], 'resource')
        bacterium = self.arena.actors[3]
        x, y, z = self.arena.drops[-1]['pos']
        bacterium.body.teleport(Vec3(x, y+1, z))
        self.arena.hit_rbc(0, hem.cells[1].id, 999)  # cells cannot hurt red blood cells
        self.assertNotEqual(hem.cells[1].state, 'dead')
        self.run_for(.3)
        self.assertEqual(self.state.resources.get(3), BALANCE['rbc_resource'])

    # -- colonias e respawn -------------------------------------------------
    def test_building_charges_on_completion_and_damage_interrupts(self):
        bacterium = self.arena.actors[3]
        self.state.resources[3] = BALANCE['colony_cost']
        bacterium.body.teleport(Vec3(-53, 1, -30))
        bacterium.pitch = -1.0
        self.run_for(.5)
        bacterium.controls = dict(build=True, yaw=bacterium.yaw, pitch=-1.0)
        self.run_for(1)
        self.assertIsNotNone(bacterium.build)
        self.assertEqual(self.state.resources[3], BALANCE['colony_cost'])
        bacterium.damage(5, self.arena.actors[0])
        self.assertIsNone(bacterium.build)
        self.run_for(BALANCE['colony_build_time']+.6)
        self.assertEqual(len(self.state.colonies), 1)
        self.assertEqual(self.state.resources[3], 0)

    def test_building_is_forbidden_inside_the_cells_station(self):
        bacterium = self.arena.actors[3]
        self.state.resources[3] = 99
        bacterium.body.teleport(Vec3(0, 1, 84))
        self.run_for(.3)
        point, problem = bacterium.build_target()
        self.assertIn("base", problem)
        self.arena.request_build(3, point)
        self.assertFalse(self.state.colonies)

    def test_waiting_bacteria_respawn_after_a_colony_is_built(self):
        self.state.escort = self.state.escort_total-.01
        self.run_for(.2)
        self.assertTrue(self.state.wound_closed)
        victim = self.arena.actors[4]
        victim.damage(5000, self.arena.actors[0])
        self.run_for(BALANCE['respawn_seconds']+.5)
        self.assertFalse(victim.alive)
        self.assertTrue(victim.waiting)
        self.state.resources[3] = BALANCE['colony_cost']
        colony = self.state.add_colony(3, (-53, 0, -30))
        self.run_for(.5)
        self.assertTrue(victim.alive)
        self.assertLess(math.dist(victim.feet, colony['pos']), 3)

    def test_destroyed_chosen_colony_falls_back_to_another(self):
        self.state.resources[3] = BALANCE['colony_cost']*2
        a = self.state.add_colony(3, (-53, 0, -30))
        b = self.state.add_colony(3, (52, 0, 26))
        victim = self.arena.actors[4]
        victim.damage(5000, self.arena.actors[0])
        victim.spawn_choice = ('colony', a['id'])
        self.state.damage_colony(a['id'], 99999)
        self.state.escort = self.state.escort_total  # entrance closed as well
        self.state.wound_closed = True
        self.run_for(BALANCE['respawn_seconds']+.5)
        self.assertTrue(victim.alive)
        self.assertLess(math.dist(victim.feet, b['pos']), 3)

    def test_cells_shoot_colonies(self):
        self.state.resources[3] = BALANCE['colony_cost']
        colony = self.state.add_colony(3, (0, 0, 48))
        self.run_for(.2)
        shooter = self.arena.actors[0]
        shooter.body.teleport(Vec3(0, 1, 58))
        shooter.yaw, shooter.pitch = 0, -.08
        step(self.game)
        hp = colony['hp']
        shooter.weapon.fire()
        self.assertLess(self.state.colony(colony['id'])['hp'], hp)

    # -- escolta e reconhecimento -------------------------------------------
    def test_bacterium_ahead_blocks_escort_but_not_from_the_walkway(self):
        self.run_for(.5)
        head = self.arena.path.at(self.state.escort)
        bacterium = self.arena.actors[3]
        bacterium.body.teleport(Vec3(head[0], 1, head[2]-3))
        self.run_for(.4)
        self.assertEqual(self.state.blocked_by, [3])
        progress = self.state.escort
        self.run_for(1)
        self.assertEqual(self.state.escort, progress)
        bacterium.body.teleport(Vec3(-8.8, 5.3, head[2]-3))  # on the wooden walkway above
        self.run_for(.4)
        self.assertEqual(self.state.blocked_by, [])
        self.assertGreater(self.state.escort, progress)

    def test_recon_reveals_after_wound_closes(self):
        cell = self.arena.actors[0]
        cell.body.teleport(Vec3(RECON[0], RECON[1]+1, RECON[2]))
        self.run_for(BALANCE['recon_channel']+1)
        self.assertEqual(self.state.reveal, 0)
        self.state.escort = self.state.escort_total-.01
        self.run_for(BALANCE['recon_channel']+1)
        self.assertGreater(self.state.reveal, 0)

    def test_snapshot_reaches_client_state(self):
        from UserComponents.cells.rules import MatchState
        self.run_for(2)
        data = self.arena.snapshot()
        mirror = MatchState()
        mirror.apply(data['state'])
        self.assertAlmostEqual(mirror.escort, self.state.escort)
        view = npcs.RemoteHemacias()
        view.apply(data['rbc'])
        self.assertEqual(len(view.cells), len(data['rbc']))


if __name__ == "__main__":
    unittest.main()
