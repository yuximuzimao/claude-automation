"""M2 ordinary one-key fill: exact empty count, one-key proof, fresh 24-cell postcondition."""
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from farm_plant_picker import PickerView
from farm_plant_ordinary import (
    OrdinaryPlantStop, OrdinaryPlantView, plant_ordinary_one_key,
)
from farm_plant_special import ALL_CELLS, SpecialPlantStop

ORDER = ["a", "b", "c", "d", "e", "f", "g"]
QUANTITIES = {s: 8 for s in ORDER}
IDENTITY = (42, 77, "QQ小程序", "QQ经典农场", 200.0, 50.0)
EMPTY = frozenset({(0, 0), (1, 0), (2, 0)})


def view(cid, ns, *, empty=EMPTY, identity=IDENTITY, one_key=True,
         preview=frozenset(), overlay="none", full=True):
    cells = {c: c not in empty for c in ALL_CELLS} if full else None
    return OrdinaryPlantView(cid, ns, identity, overlay, cells, preview, one_key)


class Adapter:
    def __init__(self, views=None, picker_views=None, fail=None):
        self.views = list(views or [view("before", 50), view("after", 201, empty=())])
        self.picker_views = list(picker_views or [PickerView(1), PickerView(2, True, 8, True)])
        self.calls = []
        self.fail = fail

    def observe_field(self):
        self.calls.append("field")
        return self.views.pop(0)

    def observe(self, slot, seed):
        self.calls.append(("picker", slot, seed))
        return self.picker_views.pop(0)

    def turn_pages(self, direction, count):
        self.calls.append(("turn", direction, count))
        if self.fail == "turn":
            raise RuntimeError("partial turn")

    def open_plot(self, anchor):
        self.calls.append(("open", anchor))
        if self.fail == "open":
            raise RuntimeError("click uncertain")

    def select_seed(self, slot):
        self.calls.append(("select", slot))
        if self.fail == "select":
            raise RuntimeError("click uncertain")

    def wait(self, seconds):
        self.calls.append(("wait", seconds))
        if self.fail == "wait":
            raise RuntimeError("animation uncertain")


class OrdinaryPlantTests(unittest.TestCase):
    def run_one(self, adapter, **kw):
        return plant_ordinary_one_key(
            adapter, platform="qq", seed="g", count=kw.pop("count", 3),
            stable_order=ORDER, quantities=kw.pop("quantities", QUANTITIES),
            clock_ns=lambda: 200, **kw,
        )

    def stop(self, code, adapter, **kw):
        with self.assertRaises(SpecialPlantStop) as ctx:
            self.run_one(adapter, **kw)
        self.assertEqual(ctx.exception.code, code)
        return ctx.exception

    def test_success_verifies_all_24_and_only_returns_copy(self):
        adapter = Adapter()
        result = self.run_one(adapter)
        self.assertEqual(result["status"], "ordinary_plant_verified")
        self.assertEqual(result["count"], 3)
        self.assertEqual(result["anchor_cell"], [0, 0])
        self.assertEqual(result["picker"], {"page": 2, "slot": 2, "visible_index": 6})
        self.assertEqual(result["quantities_after"]["g"], 5)
        self.assertEqual(QUANTITIES["g"], 8)
        self.assertFalse(result["persisted"])
        self.assertEqual(result["llm_round_trips"], 0)
        self.assertEqual(adapter.calls.count(("select", 2)), 1)
        self.assertLess(adapter.calls.index(("select", 2)), adapter.calls.index(("wait", 2.0)))

    def test_requires_exact_empty_count_before_opening(self):
        a = Adapter(views=[view("before", 50, empty={(0, 0)})])
        self.stop("PLANT_COUNT_MISMATCH", a)
        self.assertFalse(any(isinstance(x, tuple) and x[0] == "open" for x in a.calls))

    def test_one_key_is_checked_in_picker_before_seed_selection(self):
        for state in (None, False):
            with self.subTest(state=state):
                a = Adapter(picker_views=[PickerView(1), PickerView(2, True, 8, state)])
                exc = self.stop("ONE_KEY_NOT_VERIFIED", a)
                self.assertTrue(exc.action_may_have_been_sent)  # plot open/page turn only
                self.assertIn(("open", (0, 0)), a.calls)
                self.assertFalse(any(isinstance(x, tuple) and x[0] == "select" for x in a.calls))

    def test_field_toggle_is_not_picker_authority(self):
        a = Adapter(views=[view("before", 50, one_key=False),
                           view("after", 201, empty=())])
        self.assertEqual(self.run_one(a)["status"], "ordinary_plant_verified")
        b = Adapter(views=[view("before", 50, one_key=True)],
                    picker_views=[PickerView(1), PickerView(2, True, 8, False)])
        self.stop("ONE_KEY_NOT_VERIFIED", b)
        self.assertFalse(any(isinstance(x, tuple) and x[0] == "select" for x in b.calls))

    def test_inventory_shortage_stops_before_observe(self):
        a = Adapter()
        self.stop("INSUFFICIENT_INVENTORY", a, quantities={**QUANTITIES, "g": 2})
        self.assertEqual(a.calls, [])

    def test_no_empty_cells_stops_before_action(self):
        a = Adapter(views=[view("before", 50, empty=())])
        self.stop("PLANT_COUNT_MISMATCH", a)
        self.assertEqual(a.calls, ["field"])

    def test_preview_active_stops(self):
        a = Adapter(views=[view("before", 50, preview=frozenset({(0, 0)}))])
        self.stop("PLANT_PREVIEW_UNVERIFIED", a)

    def test_overlay_stops(self):
        a = Adapter(views=[view("before", 50, overlay="unknown")])
        self.stop("PLANT_OVERLAY", a)

    def test_picker_page_drift_does_not_select(self):
        a = Adapter(picker_views=[PickerView(1), PickerView(1, True, 8)])
        self.stop("PICKER_PAGE_DRIFT", a)
        self.assertFalse(any(isinstance(x, tuple) and x[0] == "select" for x in a.calls))

    def test_bad_picker_badge_does_not_select(self):
        a = Adapter(picker_views=[PickerView(1), PickerView(2, True, 2)])
        self.stop("INSUFFICIENT_INVENTORY", a)
        self.assertFalse(any(isinstance(x, tuple) and x[0] == "select" for x in a.calls))

    def test_partial_fill_stops_without_inventory_change(self):
        a = Adapter(views=[view("before", 50), view("after", 201, empty={(0, 0)})])
        exc = self.stop("PLANT_POSTCONDITION_MISMATCH", a)
        self.assertTrue(exc.action_may_have_been_sent)
        self.assertEqual(a.calls.count(("select", 2)), 1)
        self.assertEqual(QUANTITIES["g"], 8)

    def test_stale_postcondition_stops(self):
        a = Adapter(views=[view("before", 50), view("after", 200, empty=())])
        exc = self.stop("PLANT_STALE_OBSERVATION", a)
        self.assertTrue(exc.action_may_have_been_sent)

    def test_window_move_stops_after_action(self):
        moved = (42, 77, "QQ小程序", "QQ经典农场", 201.0, 50.0)
        a = Adapter(views=[view("before", 50), view("after", 201, empty=(), identity=moved)])
        self.stop("USER_INTERFERENCE", a)

    def test_postcondition_requires_all_cells(self):
        a = Adapter(views=[view("before", 50), view("after", 201, empty=(), full=False)])
        self.stop("PLANT_FIELD_UNVERIFIED", a)

    def test_select_error_not_retried(self):
        a = Adapter(fail="select")
        exc = self.stop("PLANT_ACTION_UNCERTAIN", a)
        self.assertTrue(exc.action_may_have_been_sent)
        self.assertEqual(a.calls.count(("select", 2)), 1)

    def test_wait_error_not_retried(self):
        a = Adapter(fail="wait")
        self.stop("PLANT_ACTION_UNCERTAIN", a)
        self.assertEqual(a.calls.count(("select", 2)), 1)

    def test_invalid_count_stops_without_observe(self):
        a = Adapter()
        self.stop("INVALID_PLANT_COUNT", a, count=0)
        self.assertEqual(a.calls, [])


if __name__ == "__main__":
    unittest.main()
