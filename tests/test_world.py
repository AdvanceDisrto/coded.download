import unittest
from core.simulation import WorldState, advance, snapshot, canonical_bytes


class WorldTests(unittest.TestCase):
    def test_initial_state_is_synthetic(self):
        self.assertEqual(snapshot(WorldState())["origin"], "SYNTHETIC_SIMULATION")

    def test_deterministic(self):
        self.assertEqual(advance(WorldState()), advance(WorldState()))

    def test_tick_advances(self):
        self.assertEqual(advance(WorldState()).tick, 1)

    def test_diplomacy_reduces_synthetic_crisis(self):
        base = WorldState()
        self.assertLess(advance(base, diplomacy=1).crisis_index,
                        advance(base, diplomacy=0).crisis_index)

    def test_supply_is_not_negative(self):
        self.assertEqual(advance(WorldState(supply_units=2), aid_units=100).supply_units, 0)

    def test_index_clamps(self):
        self.assertEqual(advance(WorldState(crisis_index=0), aid_units=100, diplomacy=1).crisis_index, 0)
        self.assertEqual(advance(WorldState(community_wellbeing_index=99), aid_units=100).community_wellbeing_index, 100)

    def test_validation(self):
        for bad in [-1, 2.4, True]:
            with self.assertRaises(ValueError):
                advance(WorldState(), aid_units=bad)
        for bad in [-0.1, 1.1, True]:
            with self.assertRaises(ValueError):
                advance(WorldState(), diplomacy=bad)

    def test_canonical_order(self):
        self.assertEqual(canonical_bytes({"b": 2, "a": 1}), canonical_bytes({"a": 1, "b": 2}))
