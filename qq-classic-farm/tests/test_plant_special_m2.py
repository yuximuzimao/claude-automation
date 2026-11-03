"""V2 special planting: Runner-owned occupancy + targeted UI/ROI checks."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from farm_plant_picker import PickerView
from farm_plant_special import (
    SpecialPlantStop, SpecialPlantView, plant_one_special,
)

LAYOUT = json.loads((ROOT / "data/ui-layout.json").read_text())
ORDER = ["a", "b", "c", "d", "e", "f", "g"]
QUANTITIES = {s: 3 for s in ORDER}
TARGET = frozenset(tuple(c) for c in LAYOUT["platforms"]["qq"]["safe_special_2x2"][0]["cells"])
IDENTITY = (42, 77, "QQ小程序", "QQ经典农场", 200.0, 50.0)


def view(cid, ns, *, preview=frozenset(), identity=IDENTITY, overlay="none"):
    return SpecialPlantView(cid, ns, identity, overlay, preview)


class FakeAdapter:
    def __init__(self, *, views=None, picker_views=None, occupied=True, fail=None):
        self.views = list(views or [
            view("before", 50),
            view("preview", 101, preview=TARGET),
            view("after", 201),
        ])
        self.picker_views = list(picker_views or [PickerView(1), PickerView(2, True, 3)])
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

    def ensure_one_key_mode(self, desired):
        self.calls.append(("one_key", desired))
        if desired is not False:
            raise RuntimeError("only OFF is modeled here")
        return PickerView(2, True, 3, False)

    def open_plot(self, anchor):
        self.calls.append(("open", anchor))
        if self.fail == "open":
            raise RuntimeError("uncertain")

    def select_seed(self, slot):
        self.calls.append(("select", slot))
        if self.fail == "select":
            raise RuntimeError("uncertain")

    def confirm_special(self):
        self.calls.append("confirm")
        if self.fail == "confirm":
            raise RuntimeError("uncertain")

    def wait(self, seconds):
        self.calls.append(("wait", seconds))

    def verify_cells_occupied(self, cells):
        self.calls.append(("verify_occupied", cells))
        if self.fail == "verify":
            raise RuntimeError("capture failed")
        return self.occupied


class SpecialPlantV2Tests(unittest.TestCase):
    def run_one(self, fake, *, known=frozenset(), placement="gold_a", quantities=QUANTITIES):
        times = iter((100, 200))
        return plant_one_special(
            fake, platform="qq", seed="g", placement=placement,
            known_occupied=known, stable_order=ORDER, quantities=quantities,
            layout=LAYOUT, clock_ns=lambda: next(times),
        )

    def stop(self, code, fake, **kw):
        with self.assertRaises(SpecialPlantStop) as caught:
            self.run_one(fake, **kw)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_success_uses_verified_picker_slot_and_target_roi_only(self):
        fake = FakeAdapter()
        result = self.run_one(fake)
        self.assertEqual(result["status"], "special_plant_verified")
        self.assertEqual(result["picker"], {"page": 2, "slot": 2, "visible_index": 6})
        self.assertIn(("one_key", False), fake.calls)
        self.assertIn(("select", 2), fake.calls)
        self.assertIn(("verify_occupied", TARGET), fake.calls)
        self.assertEqual(
            frozenset(map(tuple, result["occupied_after"])), TARGET)
        self.assertEqual(result["quantities_after"]["g"], 2)
        self.assertEqual(QUANTITIES["g"], 3)

    def test_known_overlap_stops_before_observation(self):
        fake = FakeAdapter()
        self.stop("PLANT_TARGET_OCCUPIED", fake, known=frozenset({next(iter(TARGET))}))
        self.assertEqual(fake.calls, [])

    def test_unknown_or_active_preview_stops_before_open(self):
        for preview in (None, frozenset({(0, 0)})):
            fake = FakeAdapter(views=[view("before", 50, preview=preview)])
            self.stop("PLANT_PREVIEW_UNVERIFIED", fake)
            self.assertFalse(any(isinstance(x, tuple) and x[0] == "open" for x in fake.calls))

    def test_picker_page_drift_never_selects(self):
        fake = FakeAdapter(picker_views=[PickerView(1), PickerView(1, True, 3)])
        self.stop("PICKER_PAGE_DRIFT", fake)
        self.assertFalse(any(isinstance(x, tuple) and x[0] == "select" for x in fake.calls))

    def test_wrong_preview_never_confirms(self):
        fake = FakeAdapter(views=[
            view("before", 50), view("preview", 101, preview=frozenset({(0, 0)}))])
        self.stop("PLANT_PREVIEW_MISMATCH", fake)
        self.assertNotIn("confirm", fake.calls)

    def test_confirm_requires_preview_closed_and_target_roi_occupied(self):
        active = FakeAdapter(views=[
            view("before", 50), view("preview", 101, preview=TARGET),
            view("after", 201, preview=TARGET)])
        self.stop("PLANT_CONFIRM_UNVERIFIED", active)

        missing = FakeAdapter(occupied=False)
        self.stop("PLANT_POSTCONDITION_MISMATCH", missing)

        unavailable = FakeAdapter(fail="verify")
        self.stop("PLANT_POSTCONDITION_UNAVAILABLE", unavailable)

    def test_action_error_is_never_retried(self):
        for fail in ("select", "confirm"):
            fake = FakeAdapter(fail=fail)
            exc = self.stop("PLANT_ACTION_UNCERTAIN", fake)
            self.assertTrue(exc.action_may_have_been_sent)
            needle = ("select", 2) if fail == "select" else "confirm"
            self.assertEqual(fake.calls.count(needle), 1)

    def test_stale_or_moved_view_stops_after_action(self):
        stale = FakeAdapter(views=[
            view("before", 50), view("preview", 100, preview=TARGET)])
        self.stop("PLANT_STALE_OBSERVATION", stale)

        moved_id = (42, 77, "QQ小程序", "QQ经典农场", 201.0, 50.0)
        moved = FakeAdapter(views=[
            view("before", 50), view("preview", 101, preview=TARGET, identity=moved_id)])
        self.stop("USER_INTERFERENCE", moved)

    def test_overlay_invalid_placement_and_inventory_fail_closed(self):
        overlay = FakeAdapter(views=[view("before", 50, overlay="unknown")])
        self.stop("PLANT_OVERLAY", overlay)

        bad = FakeAdapter()
        self.stop("INVALID_PLACEMENT", bad, placement="bad")
        self.assertEqual(bad.calls, [])

        no_stock = FakeAdapter()
        self.stop("TARGET_SEED_NOT_FOUND", no_stock,
                  quantities={**QUANTITIES, "g": 0})
        self.assertEqual(no_stock.calls, [])


if __name__ == "__main__":
    unittest.main()
