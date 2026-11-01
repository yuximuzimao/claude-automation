"""V2 phase composition: one initial EMPTY check, then Runner-owned occupancy."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from farm_plant_cycle import PlantPhaseStop, run_plant_phase
from farm_plant_special import ALL_CELLS, SpecialPlantStop
from seed_order import consume_confirmed

LAYOUT = json.loads((ROOT / "data/ui-layout.json").read_text())
ORDER = ["a", "b", "c", "d", "s", "o"]
QUANTITIES = {"a": 1, "b": 1, "c": 1, "d": 1, "s": 3, "o": 12}
ACTIONS = {
    "special": [{"seed": "s", "placements": ["gold_a", "gold_b", "gold_c"]}],
    "ordinary": [{"seed": "o", "count": 12}],
}


class PhaseAdapter:
    def __init__(self, empty=True):
        self.empty = empty
        self.calls = []

    def require_empty_field(self):
        self.calls.append("empty")
        return self.empty


def placement_cells(name):
    row = next(x for x in LAYOUT["platforms"]["qq"]["safe_special_2x2"]
               if x["id"] == name)
    return frozenset(tuple(c) for c in row["cells"])


class PlantPhaseV2Tests(unittest.TestCase):
    def run_phase(self, adapter=None, **kw):
        return run_plant_phase(
            adapter or PhaseAdapter(),
            platform="qq",
            actions=kw.pop("actions", ACTIONS),
            stable_order=ORDER,
            quantities=kw.pop("quantities", QUANTITIES),
            layout=LAYOUT,
            inventory_verified=kw.pop("inventory_verified", True),
            **kw,
        )

    def test_phase_checks_empty_once_then_tracks_confirmed_placements(self):
        adapter = PhaseAdapter()
        seen = []
        occupied = frozenset()
        current = dict(QUANTITIES)

        def special(_adapter, *, seed, placement, known_occupied, stable_order,
                    quantities, **_):
            nonlocal occupied, current
            self.assertEqual(known_occupied, occupied)
            cells = placement_cells(placement)
            occupied = frozenset(occupied | cells)
            current = consume_confirmed(stable_order, quantities, seed, 1)
            seen.append(("special", placement, occupied))
            return {
                "status": "special_plant_verified",
                "platform": "qq",
                "seed": seed,
                "placement": placement,
                "picker": {"page": 1, "slot": 1, "visible_index": 0},
                "occupied_after": [list(c) for c in sorted(occupied)],
                "quantities_after": current,
                "persisted": False,
                "llm_round_trips": 0,
            }

        def ordinary(_adapter, *, seed, count, known_occupied, stable_order,
                     quantities, **_):
            self.assertEqual(known_occupied, occupied)
            self.assertEqual(len(ALL_CELLS - known_occupied), count)
            updated = consume_confirmed(stable_order, quantities, seed, count)
            seen.append(("ordinary", count, ALL_CELLS))
            return {
                "status": "ordinary_plant_verified",
                "platform": "qq",
                "seed": seed,
                "count": count,
                "picker": {"page": 1, "slot": 1, "visible_index": 0},
                "occupied_after": [list(c) for c in sorted(ALL_CELLS)],
                "quantities_after": updated,
                "persisted": False,
                "llm_round_trips": 0,
            }

        with patch("farm_plant_cycle.plant_one_special", side_effect=special),              patch("farm_plant_cycle.plant_ordinary_one_key", side_effect=ordinary):
            result = self.run_phase(adapter)

        self.assertEqual(adapter.calls, ["empty"])
        self.assertEqual([x[0] for x in seen], ["special", "special", "special", "ordinary"])
        self.assertEqual(frozenset(map(tuple, result["occupied_after"])), ALL_CELLS)
        self.assertEqual(result["quantities_after"]["s"], 0)
        self.assertEqual(result["quantities_after"]["o"], 0)
        self.assertFalse(result["persisted"])
        self.assertEqual(result["llm_round_trips"], 0)

    def test_not_empty_stops_before_any_transaction(self):
        adapter = PhaseAdapter(empty=False)
        with patch("farm_plant_cycle.plant_one_special") as special:
            with self.assertRaises(PlantPhaseStop) as caught:
                self.run_phase(adapter)
            special.assert_not_called()
        self.assertEqual(caught.exception.code, "PLANT_FIELD_NOT_EMPTY")
        self.assertEqual(adapter.calls, ["empty"])
        self.assertFalse(caught.exception.facts()["retry_allowed"])

    def test_inventory_and_plan_validation_happen_before_empty_check(self):
        adapter = PhaseAdapter()
        with self.assertRaises(PlantPhaseStop) as caught:
            self.run_phase(adapter, inventory_verified=False)
        self.assertEqual(caught.exception.code, "INVENTORY_DIRTY")
        self.assertEqual(adapter.calls, [])

        bad = {**ACTIONS, "ordinary": [{"seed": "o", "count": 11}]}
        with self.assertRaises(PlantPhaseStop) as caught:
            self.run_phase(adapter, actions=bad)
        self.assertEqual(caught.exception.code, "INVALID_PLACEMENT")
        self.assertEqual(adapter.calls, [])

    def test_partial_special_stop_preserves_only_confirmed_runner_state(self):
        adapter = PhaseAdapter()
        first_cells = placement_cells("gold_a")
        calls = []

        def special(_adapter, *, placement, stable_order, quantities,
                    known_occupied, **_):
            calls.append(placement)
            if placement == "gold_b":
                raise SpecialPlantStop("PLANT_PREVIEW_MISMATCH", "bad",
                                       action_may_have_been_sent=True)
            updated = consume_confirmed(stable_order, quantities, "s", 1)
            return {
                "status": "special_plant_verified",
                "platform": "qq", "seed": "s", "placement": placement,
                "occupied_after": [list(c) for c in sorted(first_cells)],
                "quantities_after": updated,
                "persisted": False, "llm_round_trips": 0,
            }

        with patch("farm_plant_cycle.plant_one_special", side_effect=special),              patch("farm_plant_cycle.plant_ordinary_one_key") as ordinary:
            with self.assertRaises(PlantPhaseStop) as caught:
                self.run_phase(adapter)
            ordinary.assert_not_called()

        self.assertEqual(calls, ["gold_a", "gold_b"])
        self.assertEqual(caught.exception.confirmed_occupied, first_cells)
        self.assertEqual(caught.exception.confirmed_quantities["s"], 2)
        self.assertTrue(caught.exception.action_may_have_been_sent)
        self.assertFalse(caught.exception.facts()["retry_allowed"])

    def test_transaction_result_cannot_lie_about_occupancy_or_inventory(self):
        adapter = PhaseAdapter()
        with patch("farm_plant_cycle.plant_one_special", return_value={
            "status": "special_plant_verified",
            "platform": "qq", "seed": "s", "placement": "gold_a",
            "occupied_after": [],
            "quantities_after": dict(QUANTITIES),
            "persisted": False, "llm_round_trips": 0,
        }), patch("farm_plant_cycle.plant_ordinary_one_key") as ordinary:
            with self.assertRaises(PlantPhaseStop) as caught:
                self.run_phase(adapter)
            ordinary.assert_not_called()
        self.assertEqual(caught.exception.code, "INVALID_TRANSACTION_RESULT")

    def test_empty_check_failure_is_structured_and_not_retried(self):
        class Broken:
            def require_empty_field(self):
                raise OSError("capture failed")

        with self.assertRaises(PlantPhaseStop) as caught:
            self.run_phase(Broken())
        self.assertEqual(caught.exception.code, "PLANT_EMPTY_CHECK_UNAVAILABLE")
        self.assertFalse(caught.exception.action_may_have_been_sent)


if __name__ == "__main__":
    unittest.main()
