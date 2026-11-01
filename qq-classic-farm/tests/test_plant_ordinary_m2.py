"""V2 ordinary one-key planting: Runner-known remaining cells only."""
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from farm_plant_picker import PickerView
from farm_plant_ordinary import OrdinaryPlantView, plant_ordinary_one_key
from farm_plant_special import ALL_CELLS, SpecialPlantStop

ORDER = ["a", "b", "c", "d", "e", "f", "g"]
QUANTITIES = {s: 8 for s in ORDER}
IDENTITY = (42, 77, "QQ小程序", "QQ经典农场", 200.0, 50.0)
REMAINING = frozenset({(0, 0), (1, 0), (2, 0)})
KNOWN = frozenset(ALL_CELLS - REMAINING)


def view(cid, ns, *, identity=IDENTITY, preview=frozenset(), overlay="none"):
    return OrdinaryPlantView(cid, ns, identity, overlay, preview, None)


class Adapter:
    def __init__(self, *, views=None, picker_views=None, occupied=True, fail=None):
        self.views = list(views or [view("before", 50), view("after", 201)])
        self.picker_views = list(
            picker_views or [PickerView(1), PickerView(2, True, 8, True)])
        self.occupied = occupied
        self.fail = fail
        self.calls = []

    def observe_field(self):
        self.calls.append("field")
        return self.views.pop(0)

    def observe(self, slot, seed):
        self.calls.append(("picker", slot, seed))
        return self.picker_views.pop(0)

    def turn_pages(self, direction, count):
        self.calls.append(("turn", direction, count))

    def open_plot(self, anchor):
        self.calls.append(("open", anchor))
        if self.fail == "open":
            raise RuntimeError("uncertain")

    def arm_ordinary_selection(self, count, seed):
        self.calls.append(("arm", count, seed))

    def select_seed(self, slot):
        self.calls.append(("select", slot))
        if self.fail == "select":
            raise RuntimeError("uncertain")

    def wait(self, seconds):
        self.calls.append(("wait", seconds))
        if self.fail == "wait":
            raise RuntimeError("uncertain")

    def verify_cells_occupied(self, cells):
        self.calls.append(("verify_occupied", cells))
        if self.fail == "verify":
            raise RuntimeError("capture failed")
        return self.occupied


class OrdinaryPlantV2Tests(unittest.TestCase):
    def run_one(self, adapter, *, known=KNOWN, count=3, quantities=QUANTITIES):
        return plant_ordinary_one_key(
            adapter, platform="qq", seed="g", count=count,
            known_occupied=known, stable_order=ORDER, quantities=quantities,
            clock_ns=lambda: 200,
        )

    def stop(self, code, adapter, **kw):
        with self.assertRaises(SpecialPlantStop) as caught:
            self.run_one(adapter, **kw)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_success_uses_runner_remaining_set_and_verified_slot(self):
        adapter = Adapter()
        result = self.run_one(adapter)
        self.assertEqual(result["status"], "ordinary_plant_verified")
        self.assertEqual(result["anchor_cell"], [0, 0])
        self.assertEqual(result["picker"], {"page": 2, "slot": 2, "visible_index": 6})
        self.assertIn(("arm", 3, "g"), adapter.calls)
        self.assertIn(("select", 2), adapter.calls)
        self.assertIn(("verify_occupied", REMAINING), adapter.calls)
        self.assertEqual(
            frozenset(map(tuple, result["occupied_after"])), ALL_CELLS)
        self.assertEqual(result["quantities_after"]["g"], 5)
        self.assertEqual(QUANTITIES["g"], 8)

    def test_count_must_equal_runner_known_remaining_cells(self):
        adapter = Adapter()
        self.stop("PLANT_COUNT_MISMATCH", adapter, count=2)
        self.assertEqual(adapter.calls, [])

    def test_one_key_must_be_verified_before_seed_selection(self):
        for state in (None, False):
            adapter = Adapter(
                picker_views=[PickerView(1), PickerView(2, True, 8, state)])
            exc = self.stop("ONE_KEY_NOT_VERIFIED", adapter)
            self.assertTrue(exc.action_may_have_been_sent)
            self.assertFalse(any(isinstance(x, tuple) and x[0] == "select"
                                 for x in adapter.calls))

    def test_picker_drift_or_bad_badge_never_selects(self):
        drift = Adapter(picker_views=[PickerView(1), PickerView(1, True, 8, True)])
        self.stop("PICKER_PAGE_DRIFT", drift)
        self.assertFalse(any(isinstance(x, tuple) and x[0] == "select" for x in drift.calls))

        shortage = Adapter(picker_views=[PickerView(1), PickerView(2, True, 2, True)])
        self.stop("INSUFFICIENT_INVENTORY", shortage)
        self.assertFalse(any(isinstance(x, tuple) and x[0] == "select" for x in shortage.calls))

    def test_postcondition_checks_only_planned_remaining_cells(self):
        missing = Adapter(occupied=False)
        exc = self.stop("PLANT_POSTCONDITION_MISMATCH", missing)
        self.assertTrue(exc.action_may_have_been_sent)
        self.assertIn(("verify_occupied", REMAINING), missing.calls)

        unavailable = Adapter(fail="verify")
        self.stop("PLANT_POSTCONDITION_UNAVAILABLE", unavailable)

    def test_preview_overlay_and_freshness_fail_closed(self):
        preview = Adapter(views=[view("before", 50, preview=None)])
        self.stop("PLANT_PREVIEW_UNVERIFIED", preview)

        overlay = Adapter(views=[view("before", 50, overlay="unknown")])
        self.stop("PLANT_OVERLAY", overlay)

        stale = Adapter(views=[view("before", 50), view("after", 200)])
        self.stop("PLANT_STALE_OBSERVATION", stale)

        moved = (42, 77, "QQ小程序", "QQ经典农场", 201.0, 50.0)
        moved_adapter = Adapter(views=[view("before", 50), view("after", 201, identity=moved)])
        self.stop("USER_INTERFERENCE", moved_adapter)

    def test_action_errors_are_never_retried(self):
        for fail in ("select", "wait"):
            adapter = Adapter(fail=fail)
            exc = self.stop("PLANT_ACTION_UNCERTAIN", adapter)
            self.assertTrue(exc.action_may_have_been_sent)
            self.assertEqual(adapter.calls.count(("select", 2)), 1)

    def test_inventory_and_state_validation_happen_before_ui(self):
        shortage = Adapter()
        self.stop("INSUFFICIENT_INVENTORY", shortage,
                  quantities={**QUANTITIES, "g": 2})
        self.assertEqual(shortage.calls, [])

        invalid = Adapter()
        self.stop("PLANT_STATE_INVALID", invalid, known={(0, 0)})  # not frozenset
        self.assertEqual(invalid.calls, [])


if __name__ == "__main__":
    unittest.main()
