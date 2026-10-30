"""M2 special seed preview/confirm/occupancy transaction, all local mocks."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from farm_plant_picker import PickerView, PickerStop
from farm_plant_special import SpecialPlantStop, SpecialPlantView, plant_one_special, ALL_CELLS

LAYOUT = json.loads((ROOT / "data/ui-layout.json").read_text())
ORDER = ["a", "b", "c", "d", "e", "f", "g"]
QUANTITIES = {s: 3 for s in ORDER}
TARGET = frozenset(tuple(c) for c in LAYOUT["platforms"]["qq"]["safe_special_2x2"][0]["cells"])
IDENTITY = (42, 77, "QQ小程序", "QQ经典农场", 200.0, 50.0)


def view(cid, ns, *, occupied=(), preview=frozenset(), identity=IDENTITY, overlay="none",
         field=True):
    cells = {cell: cell in occupied for cell in ALL_CELLS} if field else None
    return SpecialPlantView(cid, ns, identity, overlay, cells, preview)


class FakeAdapter:
    def __init__(self, views=None, picker_views=None, fail=None):
        self.views = list(views or [
            view("before", 50),
            view("preview", 101, preview=TARGET, field=False),
            view("after", 201, occupied=TARGET),
        ])
        self.picker_views = list(picker_views or [PickerView(1), PickerView(2, True, 3)])
        self.calls = []
        self.fail = fail

    def observe_field(self):
        self.calls.append("observe_field")
        return self.views.pop(0)

    def observe(self, slot, seed):
        self.calls.append(("picker_observe", slot, seed))
        return self.picker_views.pop(0)

    def turn_pages(self, direction, count):
        self.calls.append(("turn_pages", direction, count))
        if self.fail == "turn_pages":
            raise RuntimeError("partial navigation")

    def open_plot(self, anchor):
        self.calls.append(("open_plot", anchor))
        if self.fail == "open_plot":
            raise RuntimeError("uncertain click")

    def select_seed(self, slot):
        self.calls.append(("select_seed", slot))
        if self.fail == "select_seed":
            raise RuntimeError("uncertain click")

    def confirm_special(self):
        self.calls.append("confirm_special")
        if self.fail == "confirm_special":
            raise RuntimeError("uncertain click")


class SpecialPlantTests(unittest.TestCase):
    def run_one(self, fake, **kwargs):
        times = iter((100, 200))
        return plant_one_special(
            fake, platform="qq", seed="g", placement="gold_a",
            stable_order=ORDER, quantities=QUANTITIES, layout=LAYOUT,
            clock_ns=lambda: next(times), **kwargs,
        )

    def stopped(self, code, fake):
        with self.assertRaises((SpecialPlantStop, PickerStop)) as ctx:
            self.run_one(fake)
        self.assertEqual(ctx.exception.code, code)

    def test_exact_preview_and_confirm_updates_only_returned_copy(self):
        fake = FakeAdapter()
        result = self.run_one(fake)
        self.assertEqual(result["status"], "special_plant_verified")
        self.assertEqual(result["picker"], {"page": 2, "slot": 2, "visible_index": 6})
        self.assertEqual(result["quantities_after"]["g"], 2)
        self.assertEqual(QUANTITIES["g"], 3)
        self.assertFalse(result["persisted"])
        self.assertEqual(result["llm_round_trips"], 0)
        self.assertEqual([x for x in fake.calls if x == "confirm_special"], ["confirm_special"])
        self.assertLess(fake.calls.index(("select_seed", 2)), fake.calls.index("confirm_special"))

    def test_existing_target_occupancy_stops_before_click(self):
        fake = FakeAdapter(views=[view("before", 50, occupied={next(iter(TARGET))})])
        self.stopped("PLANT_TARGET_OCCUPIED", fake)
        self.assertNotIn("confirm_special", fake.calls)
        self.assertFalse(any(isinstance(x, tuple) and x[0] == "open_plot" for x in fake.calls))

    def test_unverified_initial_preview_stops(self):
        fake = FakeAdapter(views=[view("before", 50, preview=None)])
        self.stopped("PLANT_PREVIEW_UNVERIFIED", fake)

    def test_picker_page_drift_stops_without_select(self):
        fake = FakeAdapter(picker_views=[PickerView(1), PickerView(1, True, 3)])
        self.stopped("PICKER_PAGE_DRIFT", fake)
        self.assertFalse(any(isinstance(x, tuple) and x[0] == "select_seed" for x in fake.calls))

    def test_wrong_preview_does_not_confirm(self):
        fake = FakeAdapter(views=[
            view("before", 50), view("preview", 101, preview=frozenset({(0, 0)}), field=False)])
        self.stopped("PLANT_PREVIEW_MISMATCH", fake)
        self.assertNotIn("confirm_special", fake.calls)

    def test_stale_preview_does_not_confirm(self):
        fake = FakeAdapter(views=[
            view("before", 50), view("before", 101, preview=TARGET, field=False)])
        with self.assertRaises(SpecialPlantStop) as ctx:
            self.run_one(fake)
        self.assertEqual(ctx.exception.code, "PLANT_STALE_OBSERVATION")
        self.assertTrue(ctx.exception.action_may_have_been_sent)
        self.assertNotIn("confirm_special", fake.calls)

    def test_preview_before_action_completion_does_not_confirm(self):
        fake = FakeAdapter(views=[
            view("before", 50), view("preview", 100, preview=TARGET, field=False)])
        self.stopped("PLANT_STALE_OBSERVATION", fake)
        self.assertNotIn("confirm_special", fake.calls)

    def test_window_moved_during_preview_stops(self):
        moved = (42, 77, "QQ小程序", "QQ经典农场", 201.0, 50.0)
        fake = FakeAdapter(views=[
            view("before", 50), view("preview", 101, preview=TARGET, identity=moved, field=False)])
        self.stopped("USER_INTERFERENCE", fake)
        self.assertNotIn("confirm_special", fake.calls)

    def test_postcondition_requires_all_24_cells(self):
        fake = FakeAdapter(views=[
            view("before", 50), view("preview", 101, preview=TARGET, field=False),
            view("after", 201, occupied=TARGET, field=False)])
        self.stopped("PLANT_FIELD_UNVERIFIED", fake)
        self.assertIn("confirm_special", fake.calls)

    def test_postcondition_must_not_change_other_plots(self):
        fake = FakeAdapter(views=[
            view("before", 50), view("preview", 101, preview=TARGET, field=False),
            view("after", 201, occupied=TARGET | {(0, 0)})])
        self.stopped("PLANT_POSTCONDITION_MISMATCH", fake)

    def test_preview_still_active_after_confirm_stops(self):
        fake = FakeAdapter(views=[
            view("before", 50), view("preview", 101, preview=TARGET, field=False),
            view("after", 201, occupied=TARGET, preview=TARGET)])
        self.stopped("PLANT_CONFIRM_UNVERIFIED", fake)

    def test_partial_confirm_does_not_retry(self):
        fake = FakeAdapter(fail="confirm_special")
        self.stopped("PLANT_ACTION_UNCERTAIN", fake)
        self.assertEqual(fake.calls.count("confirm_special"), 1)

    def test_unknown_overlay_stops_before_click(self):
        fake = FakeAdapter(views=[view("before", 50, overlay="unknown")])
        self.stopped("PLANT_OVERLAY", fake)

    def test_unknown_placement_stops_before_observe(self):
        fake = FakeAdapter()
        with self.assertRaises(SpecialPlantStop) as ctx:
            plant_one_special(fake, platform="qq", seed="g", placement="bad",
                              stable_order=ORDER, quantities=QUANTITIES, layout=LAYOUT)
        self.assertEqual(ctx.exception.code, "INVALID_PLACEMENT")
        self.assertEqual(fake.calls, [])

    def test_zero_inventory_stops_before_opening_picker(self):
        fake = FakeAdapter()
        times = iter((100, 200))
        with self.assertRaises(SpecialPlantStop) as ctx:
            plant_one_special(fake, platform="qq", seed="g", placement="gold_a",
                              stable_order=ORDER, quantities={**QUANTITIES, "g": 0},
                              layout=LAYOUT, clock_ns=lambda: next(times))
        self.assertEqual(ctx.exception.code, "TARGET_SEED_NOT_FOUND")
        self.assertEqual(fake.calls, [])

    def test_field_observation_exception_is_structured_stop(self):
        fake = FakeAdapter(views=[view("before", 50)])
        self.stopped("PLANT_OBSERVATION_UNAVAILABLE", fake)
        self.assertNotIn("confirm_special", fake.calls)

    def test_nonadjacent_2x2_layout_stops_before_action(self):
        import copy
        layout = copy.deepcopy(LAYOUT)
        layout["platforms"]["qq"]["safe_special_2x2"][0]["cells"] = [
            [0, 0], [0, 3], [5, 0], [5, 3],
        ]
        layout["platforms"]["qq"]["safe_special_2x2"][0]["anchor_cell"] = [0, 0]
        fake = FakeAdapter()
        with self.assertRaises(SpecialPlantStop) as ctx:
            plant_one_special(fake, platform="qq", seed="g", placement="gold_a",
                              stable_order=ORDER, quantities=QUANTITIES, layout=layout)
        self.assertEqual(ctx.exception.code, "INVALID_PLACEMENT")
        self.assertEqual(fake.calls, [])


if __name__ == "__main__":
    unittest.main()
