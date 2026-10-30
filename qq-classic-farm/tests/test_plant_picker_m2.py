"""M2 picker page and slot contract; no live game input."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from farm_plant_picker import PickerStop, PickerView, prepare_picker_target

ORDER = ["a", "b", "c", "d", "e", "f", "g"]
QUANTITIES = {name: 3 for name in ORDER}


class FakePicker:
    def __init__(self, *views, fail_turn=False):
        self.views = list(views)
        self.turns = []
        self.observed = []
        self.fail_turn = fail_turn

    def observe(self, slot, seed):
        self.observed.append((slot, seed))
        return self.views.pop(0)

    def turn_pages(self, direction, count):
        self.turns.append((direction, count))
        if self.fail_turn:
            raise RuntimeError("uncertain partial batch")


class PickerPhaseTests(unittest.TestCase):
    def run_target(self, fake, seed="g", needed=1, quantities=QUANTITIES):
        return prepare_picker_target(fake, platform="qq", seed=seed, needed=needed,
                                     stable_order=ORDER, quantities=quantities)

    def assert_stop(self, code, fake, **kw):
        with self.assertRaises(PickerStop) as ctx:
            self.run_target(fake, **kw)
        self.assertEqual(ctx.exception.code, code)

    def test_target_already_on_verified_page_no_turn(self):
        fake = FakePicker(PickerView(2, True, 3))
        result = self.run_target(fake)
        self.assertEqual(result["position"], {"page": 2, "slot": 2, "visible_index": 6})
        self.assertEqual(result["observations"], 1)
        self.assertEqual(result["llm_round_trips"], 0)
        self.assertFalse(result["selection_sent"])
        self.assertFalse(result["inventory_mutated"])
        self.assertEqual(fake.turns, [])

    def test_bounded_batch_from_observed_page_then_verify(self):
        fake = FakePicker(PickerView(1), PickerView(2, True, 3))
        result = self.run_target(fake)
        self.assertEqual(fake.turns, [(1, 1)])
        self.assertEqual(fake.observed, [(2, "g"), (2, "g")])
        self.assertEqual(result["observations"], 2)

    def test_navigation_backward_from_page_two(self):
        fake = FakePicker(PickerView(2), PickerView(1, True, 3))
        result = self.run_target(fake, seed="a")
        self.assertEqual(result["position"]["slot"], 1)
        self.assertEqual(fake.turns, [(-1, 1)])

    def test_unknown_initial_page_never_guesses_first(self):
        self.assert_stop("PICKER_PAGE_UNKNOWN", FakePicker(PickerView(None)))

    def test_malformed_observation_structurally_stops(self):
        self.assert_stop("PICKER_OBSERVATION_UNAVAILABLE", FakePicker(None))

    def test_boolean_page_is_not_page_one(self):
        self.assert_stop("PICKER_PAGE_UNKNOWN", FakePicker(PickerView(True)))

    def test_page_drift_after_navigation_does_not_retry(self):
        fake = FakePicker(PickerView(1), PickerView(1, True, 3))
        self.assert_stop("PICKER_PAGE_DRIFT", fake)
        self.assertEqual(fake.turns, [(1, 1)])

    def test_partial_navigation_is_uncertain_no_retry(self):
        fake = FakePicker(PickerView(1), fail_turn=True)
        self.assert_stop("PICKER_NAVIGATION_UNCERTAIN", fake)
        self.assertEqual(fake.turns, [(1, 1)])

    def test_icon_mismatch_is_state_drift(self):
        self.assert_stop("STATE_DRIFT", FakePicker(PickerView(2, False, 3)))

    def test_badge_missing_or_insufficient(self):
        self.assert_stop("QUANTITY_UNVERIFIED", FakePicker(PickerView(2, True, None)))
        self.assert_stop("INSUFFICIENT_INVENTORY", FakePicker(PickerView(2, True, 1)), needed=2)

    def test_local_inventory_insufficient_never_navigates(self):
        fake = FakePicker()
        self.assert_stop("INSUFFICIENT_INVENTORY", fake, needed=4)
        self.assertEqual(fake.observed, [])

    def test_zero_stock_shift_uses_m0_model_without_recalibration(self):
        quantities = dict(QUANTITIES)
        quantities["b"] = 0
        fake = FakePicker(PickerView(2, True, 3))
        result = self.run_target(fake, quantities=quantities)
        self.assertEqual(result["position"], {"page": 2, "slot": 1, "visible_index": 5})


if __name__ == "__main__":
    unittest.main()
