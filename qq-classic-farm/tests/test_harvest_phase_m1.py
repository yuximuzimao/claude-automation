"""Offline M1 harvest state-machine contract; no screenshots, CGEvents or model calls."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from farm_harvest import HarvestObservation, HarvestStop, prepare_harvest, run_harvest


def observation(**changes) -> HarvestObservation:
    baseline = HarvestObservation(
        overlay="none", calibration_verified=True,
        window_identity=(123, 456, "QQ小程序", "QQ经典农场", 500.0, 200.0),
        window_width=603, window_height=1111,
        hand=(300.0, 900.0),
        special=(("gold_a", 250.0, 580.0), ("gold_b", 170.0, 620.0)),
        occupied_special=frozenset(("gold_a", "gold_b")),
        empty_cells=tuple(False for _ in range(24)),
    )
    return replace(baseline, **changes)


class FakeAdapter:
    def __init__(self, before: HarvestObservation, after: HarvestObservation,
                 *, sent: int | None = None, fail_batch: bool = False):
        self.observations = [before, after]
        self.sent = sent
        self.fail_batch = fail_batch
        self.batches: list[tuple[tuple[float, float], ...]] = []
        self.waits: list[float] = []

    def observe(self):
        return self.observations.pop(0)

    def click_batch(self, points):
        self.batches.append(points)
        if self.fail_batch:
            raise RuntimeError("Helper stopped midway")
        return len(points) if self.sent is None else self.sent

    def wait(self, seconds):
        self.waits.append(seconds)


class HarvestPhaseTests(unittest.TestCase):
    def test_ordered_batch_and_verified_clean_field(self):
        after = observation(hand=None, special=(), occupied_special=frozenset(), empty_cells=(True,) * 24)
        fake = FakeAdapter(observation(), after)
        result = run_harvest(fake)
        self.assertEqual(result["status"], "clean_field_verified")
        self.assertEqual(result["click_count"], 3)
        self.assertEqual(result["llm_round_trips"], 0)
        self.assertEqual(fake.batches, [((250.0, 580.0), (170.0, 620.0), (300.0, 900.0))])
        self.assertEqual(fake.waits, [3.0])

    def test_no_special_stars_still_clicks_hand_once(self):
        before = observation(special=(), occupied_special=frozenset())
        after = observation(hand=None, special=(), occupied_special=frozenset(),
                            empty_cells=(True,) * 24)
        fake = FakeAdapter(before, after)
        self.assertEqual(run_harvest(fake)["click_count"], 1)
        self.assertEqual(fake.batches, [((300.0, 900.0),)])

    def test_already_clean_is_zero_click_and_zero_wait(self):
        clean = observation(hand=None, special=(), occupied_special=frozenset(), empty_cells=(True,) * 24)
        fake = FakeAdapter(clean, clean)
        self.assertEqual(run_harvest(fake)["status"], "already_clean")
        self.assertEqual(fake.batches, [])
        self.assertEqual(fake.waits, [])

    def test_uncalibrated_never_clicks(self):
        fake = FakeAdapter(observation(calibration_verified=False), observation())
        with self.assertRaises(HarvestStop) as caught:
            run_harvest(fake)
        self.assertEqual(caught.exception.code, "HARVEST_CALIBRATION_REQUIRED")
        self.assertEqual(fake.batches, [])

    def test_occupied_special_must_be_verified_independently(self):
        for occupied, expected in ((None, "SPECIAL_OCCUPANCY_UNKNOWN"),
                                   (frozenset({"gold_b"}), "AMBIGUOUS_PICKABLES")):
            with self.subTest(occupied=occupied):
                with self.assertRaises(HarvestStop) as caught:
                    prepare_harvest(observation(occupied_special=occupied))
                self.assertEqual(caught.exception.code, expected)

    def test_duplicate_special_marker_stops_before_any_click(self):
        with self.assertRaises(HarvestStop) as caught:
            prepare_harvest(observation(special=(("gold_a", 250, 580), ("gold_a", 250, 580))))
        self.assertEqual(caught.exception.code, "AMBIGUOUS_PICKABLES")

    def test_unknown_and_known_overlay_stop_without_dismissal(self):
        for overlay, code in (("unknown", "UNKNOWN_OVERLAY"),
                              ("known", "KNOWN_OVERLAY_UNHANDLED"),
                              ("unrecognized", "UNKNOWN_OVERLAY")):
            with self.subTest(overlay=overlay):
                fake = FakeAdapter(observation(overlay=overlay), observation())
                with self.assertRaises(HarvestStop) as caught:
                    run_harvest(fake)
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(fake.batches, [])

    def test_no_hand_on_nonempty_field_is_not_clean(self):
        with self.assertRaises(HarvestStop) as caught:
            prepare_harvest(observation(hand=None, special=()))
        self.assertEqual(caught.exception.code, "HARVEST_HAND_MISSING")

    def test_no_empty_cells_evidence_cannot_be_called_clean(self):
        with self.assertRaises(HarvestStop) as caught:
            prepare_harvest(observation(hand=None, special=(), empty_cells=None))
        self.assertEqual(caught.exception.code, "HARVEST_HAND_MISSING")

    def test_malformed_occupancy_report_rejected(self):
        for cells in ((True,) * 23, (True,) * 23 + (1,)):
            with self.subTest(cells=cells):
                with self.assertRaises(HarvestStop) as caught:
                    prepare_harvest(observation(empty_cells=cells))
                self.assertEqual(caught.exception.code, "INVALID_FIELD_OBSERVATION")

    def test_click_outside_window_rejected_before_batch(self):
        for point in ((-1, 200), (603, 200), (200, float("nan"))):
            with self.subTest(point=point):
                with self.assertRaises(HarvestStop) as caught:
                    prepare_harvest(observation(hand=point))
                self.assertEqual(caught.exception.code, "CLICK_OUTSIDE_WINDOW")

    def test_postcondition_missing_stops_without_reclick(self):
        after = observation(hand=None, special=(), empty_cells=None)
        fake = FakeAdapter(observation(), after)
        with self.assertRaises(HarvestStop) as caught:
            run_harvest(fake)
        self.assertEqual(caught.exception.code, "HARVEST_POSTCONDITION_UNKNOWN")
        self.assertEqual(caught.exception.clicks_sent, 3)
        self.assertEqual(len(fake.batches), 1)

    def test_postcondition_partial_field_stops_without_reclick(self):
        after = observation(hand=None, special=(), empty_cells=(True,) * 23 + (False,))
        fake = FakeAdapter(observation(), after)
        with self.assertRaises(HarvestStop) as caught:
            run_harvest(fake)
        self.assertEqual(caught.exception.code, "HARVEST_FIELD_NOT_CLEAN")
        self.assertEqual(len(fake.batches), 1)

    def test_window_movement_or_identity_change_stops_after_batch(self):
        for changed in ((123, 456, "QQ小程序", "QQ经典农场", 501.0, 200.0),
                        (999, 456, "QQ小程序", "QQ经典农场", 500.0, 200.0)):
            with self.subTest(changed=changed):
                fake = FakeAdapter(observation(), observation(window_identity=changed))
                with self.assertRaises(HarvestStop) as caught:
                    run_harvest(fake)
                self.assertEqual(caught.exception.code, "USER_INTERFERENCE")
                self.assertEqual(caught.exception.clicks_sent, 3)
                self.assertEqual(len(fake.batches), 1)

    def test_postcondition_overlay_stops_without_reclick(self):
        fake = FakeAdapter(observation(), observation(overlay="unknown"))
        with self.assertRaises(HarvestStop) as caught:
            run_harvest(fake)
        self.assertEqual(caught.exception.code, "UNKNOWN_OVERLAY")
        self.assertEqual(caught.exception.clicks_sent, 3)
        self.assertEqual(len(fake.batches), 1)

    def test_clean_field_conflicting_occupied_special_rejected(self):
        with self.assertRaises(HarvestStop) as caught:
            prepare_harvest(observation(hand=None, special=(), empty_cells=(True,) * 24))
        self.assertEqual(caught.exception.code, "HARVEST_STATE_CONFLICT")

    def test_postcondition_false_clean_report_rejected(self):
        after = observation(empty_cells=(True,) * 24)
        fake = FakeAdapter(observation(), after)
        with self.assertRaises(HarvestStop) as caught:
            run_harvest(fake)
        self.assertEqual(caught.exception.code, "HARVEST_STATE_CONFLICT")
        self.assertEqual(len(fake.batches), 1)

    def test_partial_batch_never_retries(self):
        after = observation(hand=None, special=(), occupied_special=frozenset(), empty_cells=(True,) * 24)
        for sent, fail in ((1, False), (None, True)):
            with self.subTest(sent=sent, fail=fail):
                fake = FakeAdapter(observation(), after, sent=sent, fail_batch=fail)
                with self.assertRaises(HarvestStop) as caught:
                    run_harvest(fake)
                self.assertEqual(caught.exception.code, "HARVEST_PARTIAL_ACTION")
                self.assertEqual(len(fake.batches), 1)
                self.assertEqual(fake.waits, [])


if __name__ == "__main__":
    unittest.main()
