import unittest
from UserComponents.cells.rules import MatchState, EscortPath, escort_blockers
from UserComponents.cells.catalog import CELLS, BACTERIA, BALANCE, can_select, unlocked


def state_with_colonies(n, slot=3):
    state = MatchState()
    state.resources[slot] = BALANCE['colony_cost']*n
    for i in range(n):
        assert state.add_colony(slot, (i*10, 0, 0))
    return state


class EscortTests(unittest.TestCase):
    def setUp(self):
        self.path = EscortPath([(0, 0, 0), (0, 0, -10), (10, 0, -10)])

    def test_path_measures_and_interpolates(self):
        self.assertAlmostEqual(self.path.total, 20)
        self.assertEqual(self.path.at(15), (5, 0, -10))
        self.assertEqual(self.path.direction(2), (0, -1))

    def test_living_bacteria_ahead_on_same_passage_block(self):
        self.assertEqual(escort_blockers(self.path, 0, [(3, (0, .95, -3), True)]), [3])

    def test_bacteria_above_behind_walls_or_behind_do_not_block(self):
        roof = (3, (0, 4.95, -3), True)        # balcony / bridge above
        wall = (4, (0, .95, -3), False)        # no line of sight
        behind = (5, (0, .95, 4), True)        # behind the platelets
        below = (6, (0, -1.45, -3), True)      # canal under the bridge
        self.assertEqual(escort_blockers(self.path, 0, [roof, wall, behind, below]), [])

    def test_progress_stops_while_blocked_and_is_never_lost(self):
        state = MatchState(escort_total=20)
        state.tick(5)
        progress = state.escort
        self.assertGreater(progress, 0)
        state.tick(5, blockers=[3], bacteria_alive=1)
        self.assertEqual(state.escort, progress)
        self.assertEqual(state.blocked_by, [3])
        state.tick(1)
        self.assertGreater(state.escort, progress)

    def test_closing_the_wound_is_irreversible(self):
        state = MatchState(escort_total=1)
        state.tick(10, bacteria_alive=1)
        self.assertTrue(state.wound_closed)
        state.tick(1, blockers=[3], bacteria_alive=1)
        self.assertTrue(state.wound_closed)
        self.assertEqual(state.escort, 1)


class ColonyTests(unittest.TestCase):
    def test_build_charges_only_on_completion_and_respects_limit(self):
        state = MatchState()
        state.resources[3] = BALANCE['colony_cost']-1
        self.assertIn("Precisa", state.build_problem(3, state.resources[3]))
        self.assertIsNone(state.add_colony(3, (0, 0, 0)))
        self.assertEqual(state.resources[3], BALANCE['colony_cost']-1)
        state = state_with_colonies(BALANCE['colony_limit'])
        state.resources[3] = 99
        self.assertIn("Limite", state.build_problem(3, 99))
        self.assertIsNone(state.add_colony(3, (50, 0, 0)))
        self.assertEqual(state.build_problem(4, 99), "")  # the limit is per player

    def test_protection_grows_with_other_colonies_and_has_a_cap(self):
        state = state_with_colonies(1)
        self.assertEqual(state.protection(state.colonies[0]['id']), 0)
        state = MatchState()
        for slot in (3, 4, 5):
            state.resources[slot] = 99
            for i in range(3):
                state.add_colony(slot, (slot*20+i*6, 0, 0))
        self.assertAlmostEqual(state.protection(state.colonies[0]['id']), BALANCE['colony_protection_cap'])

    def test_destroying_removes_contribution_and_protection_without_healing(self):
        state = state_with_colonies(2)
        a, b = state.colonies
        before = state.infection()
        state.damage_colony(a['id'], 100)
        self.assertAlmostEqual(BALANCE['colony_health']-a['hp'], 100*(1-BALANCE['colony_protection_each']))
        lost = a['hp']
        state.damage_colony(b['id'], 10_000)
        self.assertEqual(len(state.colonies), 1)
        self.assertLess(state.infection(), before)
        self.assertEqual(state.protection(a['id']), 0)
        self.assertEqual(a['hp'], lost)  # losing protection neither heals nor damages

    def test_development_spends_resources_up_to_the_cap(self):
        state = state_with_colonies(1)
        cid = state.colonies[0]['id']
        state.resources[3] = 100
        state.develop(3, cid)
        self.assertEqual(state.colonies[0]['dev'], BALANCE['colony_dev_cap'])
        spent = 100-state.resources[3]
        self.assertEqual(spent, -(-BALANCE['colony_dev_cap']//BALANCE['colony_dev_per_resource']))
        self.assertEqual(state.develop(3, cid), 0)

    def test_repair_never_exceeds_max_health(self):
        state = state_with_colonies(1)
        cid = state.colonies[0]['id']
        state.damage_colony(cid, 50)
        state.repair(cid, 999)
        self.assertEqual(state.colonies[0]['hp'], BALANCE['colony_health'])


class VictoryTests(unittest.TestCase):
    def test_bacteria_win_by_collective_infection_even_with_wound_open(self):
        state = MatchState()
        for slot in (3, 4, 5):
            state.resources[slot] = 999
        x = 0
        while state.infection() < BALANCE['infection_goal']:
            slot = 3+len(state.colonies) % 3
            colony = state.add_colony(slot, (x, 0, 0))
            self.assertIsNotNone(colony, "goal must be reachable with nine colonies")
            state.develop(slot, colony['id'])
            x += 10
        self.assertGreater(len(state.colonies), 3)  # several developed colonies are required
        state.tick(.1, bacteria_alive=3)
        self.assertEqual(state.winner, BACTERIA)

    def test_no_passive_infection_growth(self):
        state = state_with_colonies(2)
        before = state.infection()
        state.tick(600, blockers=[3], bacteria_alive=3)
        self.assertEqual(state.infection(), before)
        self.assertEqual(state.winner, "")

    def test_cells_win_only_with_wound_closed_no_colonies_and_no_bacteria(self):
        state = MatchState(wound_closed=True)
        state.tick(.1, bacteria_alive=1)
        self.assertEqual(state.winner, "")
        state = state_with_colonies(1)
        state.wound_closed = True
        state.tick(.1, bacteria_alive=0)
        self.assertEqual(state.winner, "")
        state.damage_colony(state.colonies[0]['id'], 10_000)
        state.tick(.1, bacteria_alive=0)
        self.assertEqual(state.winner, CELLS)


class RecognitionTests(unittest.TestCase):
    def test_antigens_unlock_b_cell_then_killer_t(self):
        state = MatchState()
        self.assertFalse(unlocked("b_cell", state.recognition))
        state.antigen(BALANCE['unlock_b_cell'])
        self.assertTrue(unlocked("b_cell", state.recognition))
        self.assertFalse(unlocked("killer_t", state.recognition))
        state.antigen(100)
        self.assertTrue(unlocked("killer_t", state.recognition))
        self.assertIn("liberado", state.notice)

    def test_recon_needs_closed_wound_and_uncontested_channel(self):
        state = MatchState()
        self.assertFalse(state.channel_recon(0, 99, False))
        state.wound_closed = True
        self.assertFalse(state.channel_recon(0, BALANCE['recon_channel'], True))
        self.assertEqual(state.recon, 0)
        self.assertTrue(state.channel_recon(0, BALANCE['recon_channel'], False))
        self.assertGreater(state.reveal, 0)
        self.assertFalse(state.recon_available())  # cooldown; the reveal is temporary
        state.tick(BALANCE['recon_reveal']+.1, bacteria_alive=1)
        self.assertEqual(state.reveal, 0)

    def test_snapshot_round_trip(self):
        state = state_with_colonies(2)
        state.antigen(30)
        copy = MatchState()
        copy.apply(state.snapshot())
        self.assertEqual(copy.infection(), state.infection())
        self.assertEqual(copy.recognition, 30)


class SelectionTests(unittest.TestCase):
    def test_simultaneous_limits_and_team_validation(self):
        roster = {0: {"hero": "neutrophil"}, 1: {"hero": "neutrophil"}, 2: {"hero": "macrophage"}}
        self.assertFalse(can_select("neutrophil", CELLS, roster))
        self.assertTrue(can_select("neutrophil", CELLS, roster, exclude=0))
        self.assertFalse(can_select("macrophage", BACTERIA, roster))
        self.assertFalse(can_select("killer_t", CELLS, {}, 0))
        self.assertTrue(can_select("killer_t", CELLS, {}, 100))


if __name__ == "__main__":
    unittest.main()
