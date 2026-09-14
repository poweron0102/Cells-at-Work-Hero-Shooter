import unittest
from UserComponents.cells.rules import MatchState
from UserComponents.cells.catalog import CELLS, BACTERIA, can_select, unlocked


class RuleTests(unittest.TestCase):
    def test_stress_never_ends_match(self):
        for phase in range(3):
            state = MatchState(phase=phase, stress=100)
            state.tick(.1, [(0, 0)]*3)
            self.assertEqual(state.winner, "")

    def test_breach_requires_two_points_and_contest_stops_capture(self):
        state = MatchState(capture=[99, 99, 0])
        state.tick(1, [(1, 1), (0, 1), (0, 0)])
        self.assertEqual(state.capture, [99, 100, 0])
        self.assertEqual(state.phase, 0)
        state.tick(1, [(0, 1), (0, 0), (0, 0)])
        self.assertEqual(state.phase, 1)

    def test_antigen_progression_and_tissue_unlock(self):
        state = MatchState(phase=1)
        state.antigen(25)
        self.assertFalse(unlocked("b_cell", state.recognition, False))
        state.antigen(25)
        state.tick(.1, [(0, 0)]*3)
        self.assertEqual(state.phase, 2)
        self.assertTrue(unlocked("b_cell", state.recognition, state.infected))
        self.assertTrue(unlocked("killer_t", state.recognition, state.infected))

    def test_destroying_last_core_wins_at_max_stress(self):
        state = MatchState(phase=2, stress=100, cores=[0, 0], maturity=99)
        state.tick(1, [(0, 0)]*3)
        self.assertEqual(state.winner, CELLS)

    def test_bacterial_win_depends_on_maturity(self):
        state = MatchState(phase=2, maturity=99.9, stress=0)
        state.tick(1, [(0, 0)]*3)
        self.assertEqual(state.winner, BACTERIA)

    def test_timer_defends_and_immune_cooldown_is_shared(self):
        state = MatchState(remaining=.1)
        self.assertTrue(state.response())
        self.assertFalse(state.response())
        state.tick(1, [(0, 0)]*3)
        self.assertEqual(state.winner, CELLS)

    def test_simultaneous_limits_and_team_validation(self):
        roster = {0: {"hero": "neutrophil"}, 1: {"hero": "neutrophil"}, 2: {"hero": "macrophage"}}
        self.assertFalse(can_select("neutrophil", CELLS, roster))
        self.assertTrue(can_select("neutrophil", CELLS, roster, exclude=0))
        self.assertFalse(can_select("macrophage", BACTERIA, roster))
        self.assertFalse(can_select("killer_t", CELLS, roster, 100, False))



if __name__ == "__main__":
    unittest.main()
