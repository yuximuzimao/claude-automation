"""M2 local phase composition, tested without real windows or mouse input."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from farm_plant_cycle import PlantPhaseStop, run_plant_phase
from farm_plant_special import SpecialPlantStop
from seed_order import compute_picker_position, consume_confirmed

LAYOUT = json.loads((ROOT / "data/ui-layout.json").read_text())
ORDER = ["a", "b", "c", "d", "s", "o"]
QUANTITIES = {"a": 1, "b": 1, "c": 1, "d": 1, "s": 3, "o": 12}
ACTIONS = {
    "special": [{"seed": "s", "placements": ["gold_a", "gold_b", "gold_c"]}],
    "ordinary": [{"seed": "o", "count": 12}],
}


class PhaseTests(unittest.TestCase):
    def run_phase(self, **kw):
        return run_plant_phase(
            object(), platform="qq", actions=kw.pop("actions", ACTIONS),
            stable_order=ORDER, quantities=kw.pop("quantities", QUANTITIES),
            layout=LAYOUT, inventory_verified=kw.pop("inventory_verified", True),
            **kw,
        )

    def test_three_special_then_ordinary_uses_shifted_picker_and_checkpoints(self):
        calls, snapshots = [], []

        def special(_adapter, *, seed, placement, stable_order, quantities, **_):
            pos = compute_picker_position("qq", seed, stable_order, quantities).as_dict()
            calls.append(("special", placement, pos))
            return {
                "status": "special_plant_verified", "platform": "qq", "seed": seed, "placement": placement,
                "picker": pos, "quantities_after": consume_confirmed(
                    stable_order, quantities, seed, 1),
                "persisted": False, "llm_round_trips": 0,
            }

        def ordinary(_adapter, *, seed, count, stable_order, quantities, **_):
            pos = compute_picker_position("qq", seed, stable_order, quantities).as_dict()
            calls.append(("ordinary", count, pos))
            return {
                "status": "ordinary_plant_verified", "platform": "qq", "seed": seed,
                "count": count, "picker": pos,
                "quantities_after": consume_confirmed(stable_order, quantities, seed, count),
                "persisted": False, "llm_round_trips": 0,
            }

        with patch("farm_plant_cycle.plant_one_special", side_effect=special), \
             patch("farm_plant_cycle.plant_ordinary_one_key", side_effect=ordinary):
            result = self.run_phase(checkpoint=lambda e, q: snapshots.append((len(e), dict(q))))

        self.assertEqual([c[0] for c in calls], ["special"] * 3 + ["ordinary"])
        self.assertEqual(calls[0][2]["page"], 1)
        self.assertEqual(calls[-1][2], {"page": 1, "slot": 5, "visible_index": 4})
        self.assertEqual(result["quantities_after"]["s"], 0)
        self.assertEqual(result["quantities_after"]["o"], 0)
        self.assertEqual(QUANTITIES["s"], 3)
        self.assertEqual([x[0] for x in snapshots], [1, 2, 3, 4])
        self.assertEqual(snapshots[2][1]["s"], 0)
        self.assertFalse(result["persisted"])
        self.assertEqual(result["llm_round_trips"], 0)

    def test_partial_second_special_reports_first_confirmed_only_and_never_ordinary(self):
        events = []
        def special(_adapter, *, placement, stable_order, quantities, **_):
            events.append(placement)
            if placement == "gold_b":
                raise SpecialPlantStop("PLANT_PREVIEW_MISMATCH", "Unsafe preview",
                                       action_may_have_been_sent=True)
            return {
                "status": "special_plant_verified", "platform": "qq", "seed": "s", "placement": placement,
                "quantities_after": consume_confirmed(stable_order, quantities, "s", 1),
                "persisted": False, "llm_round_trips": 0,
            }

        with patch("farm_plant_cycle.plant_one_special", side_effect=special), \
             patch("farm_plant_cycle.plant_ordinary_one_key") as ordinary:
            with self.assertRaises(PlantPhaseStop) as caught:
                self.run_phase()
            ordinary.assert_not_called()
        error = caught.exception
        self.assertEqual(error.code, "PLANT_PREVIEW_MISMATCH")
        self.assertEqual(events, ["gold_a", "gold_b"])
        self.assertEqual(len(error.completed), 1)
        self.assertEqual(error.confirmed_quantities["s"], 2)
        self.assertTrue(error.action_may_have_been_sent)
        self.assertFalse(error.recovery()["retry_allowed"])
        self.assertEqual(QUANTITIES["s"], 3)

    def test_unverified_inventory_stops_before_any_adapter_call(self):
        with patch("farm_plant_cycle.plant_one_special") as special:
            with self.assertRaises(PlantPhaseStop) as caught:
                self.run_phase(inventory_verified=False)
            special.assert_not_called()
        self.assertEqual(caught.exception.code, "INVENTORY_DIRTY")

    def test_invalid_total_and_insufficient_stock_stop_before_any_ui(self):
        for actions, quantities, code in (
            ({**ACTIONS, "ordinary": [{"seed": "o", "count": 11}]},
             QUANTITIES, "INVALID_PLACEMENT"),
            (ACTIONS, {**QUANTITIES, "s": 2}, "INSUFFICIENT_INVENTORY"),
        ):
            with self.subTest(code=code):
                with patch("farm_plant_cycle.plant_one_special") as special:
                    with self.assertRaises(PlantPhaseStop) as caught:
                        self.run_phase(actions=actions, quantities=quantities)
                    special.assert_not_called()
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(caught.exception.completed, [])

    def test_checkpoint_failure_stops_after_verified_first_action(self):
        def special(_adapter, *, stable_order, quantities, **_):
            return {
                "status": "special_plant_verified", "platform": "qq", "seed": "s",
                "quantities_after": consume_confirmed(stable_order, quantities, "s", 1),
                "persisted": False, "llm_round_trips": 0,
            }
        with patch("farm_plant_cycle.plant_one_special", side_effect=special) as spec, \
             patch("farm_plant_cycle.plant_ordinary_one_key") as ordinary:
            with self.assertRaises(PlantPhaseStop) as caught:
                self.run_phase(checkpoint=lambda *_: (_ for _ in ()).throw(OSError("disk full")))
            ordinary.assert_not_called()
        self.assertEqual(spec.call_count, 1)
        self.assertEqual(caught.exception.code, "RECOVERY_CHECKPOINT_FAILED")
        self.assertEqual(caught.exception.confirmed_quantities["s"], 2)
        self.assertEqual(len(caught.exception.completed), 1)

    def test_incorrect_confirmed_quantity_never_reaches_next_transaction(self):
        def wrong(_adapter, **_):
            return {
                "status": "special_plant_verified", "platform": "qq", "seed": "s",
                "quantities_after": dict(QUANTITIES),  # no decrement despite claimed success
                "persisted": False, "llm_round_trips": 0,
            }
        with patch("farm_plant_cycle.plant_one_special", side_effect=wrong) as special, \
             patch("farm_plant_cycle.plant_ordinary_one_key") as ordinary:
            with self.assertRaises(PlantPhaseStop) as caught:
                self.run_phase()
            ordinary.assert_not_called()
        self.assertEqual(special.call_count, 1)
        self.assertEqual(caught.exception.code, "INVALID_TRANSACTION_RESULT")
        self.assertEqual(caught.exception.confirmed_quantities["s"], 3)

    def test_untrusted_transaction_result_stops_without_running_next_action(self):
        with patch("farm_plant_cycle.plant_one_special", return_value={
            "status": "special_plant_verified", "quantities_after": dict(QUANTITIES),
            "persisted": True, "llm_round_trips": 0,
        }) as special, patch("farm_plant_cycle.plant_ordinary_one_key") as ordinary:
            with self.assertRaises(PlantPhaseStop) as caught:
                self.run_phase()
            ordinary.assert_not_called()
        self.assertEqual(special.call_count, 1)
        self.assertEqual(caught.exception.code, "INVALID_TRANSACTION_RESULT")


if __name__ == "__main__":
    unittest.main()
