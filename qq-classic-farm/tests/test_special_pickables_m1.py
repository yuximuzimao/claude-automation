"""M1 special-pickable geometry regression tests; no desktop I/O or mouse events."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from farm_capture import FarmCapture
from farm_geometry import WindowFrame, plot_local_point
from farm_vision import (
    VisionStop, _filter_special_pickables, _special_centers, probe_harvest,
)
from farm_io import WindowHandle, probe_window_harvest


class SpecialPickableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layout = json.loads((ROOT / "data/ui-layout.json").read_text(encoding="utf-8"))

    def capture(self, platform: str, pixel_scale: int = 1) -> FarmCapture:
        width, height = self.layout["platforms"][platform]["baseline_window_size"]
        owner = "QQ小程序" if platform == "qq" else "微信"
        frame = WindowFrame(owner, "QQ经典农场", 430, 90, width, height)
        return FarmCapture(frame, np.zeros((height * pixel_scale, width * pixel_scale), dtype=np.float32))

    @staticmethod
    def item(capture: FarmCapture, local_x: float, local_y: float, score: float = 0.94) -> dict:
        h, w = capture.gray.shape
        return {
            "center_x": local_x * w / capture.frame.width,
            "center_y": local_y * h / capture.frame.height,
            "score": score,
        }

    @staticmethod
    def detected(*items: dict) -> dict:
        return {"count": len(items), "items": list(items)}

    def test_qq_and_wechat_special_centers_follow_layout(self):
        for platform, count in (("qq", 3), ("wechat", 2)):
            with self.subTest(platform=platform):
                capture = self.capture(platform)
                centers = _special_centers(capture, platform, self.layout)
                self.assertEqual(len(centers), count)
                for placement in self.layout["platforms"][platform]["safe_special_2x2"]:
                    points = [
                        plot_local_point(platform, u, v, capture.frame, self.layout)
                        for u, v in placement["cells"]
                    ]
                    x, y = centers[placement["id"]]
                    self.assertAlmostEqual(x, sum(p[0] for p in points) / 4)
                    self.assertAlmostEqual(y, sum(p[1] for p in points) / 4)

    def test_retina_2x_converts_pixels_to_logical_and_accepts_valid_markers(self):
        for platform in ("qq", "wechat"):
            with self.subTest(platform=platform):
                capture = self.capture(platform, 2)
                centers = _special_centers(capture, platform, self.layout)
                markers = [self.item(capture, x + 5, y - 6) for x, y in centers.values()]
                found, ignored = _filter_special_pickables(
                    capture, platform, self.layout, self.detected(*markers)
                )
                self.assertEqual(ignored, 0)
                self.assertEqual({x["placement"] for x in found}, set(centers))
                self.assertEqual(len(found), len(centers))
                for found_item in found:
                    x, y = centers[found_item["placement"]]
                    self.assertAlmostEqual(found_item["local_center"][0], x + 5)
                    self.assertAlmostEqual(found_item["local_center"][1], y - 6)

    def test_ordinary_single_plot_star_is_ignored(self):
        for platform in ("qq", "wechat"):
            with self.subTest(platform=platform):
                capture = self.capture(platform)
                # An individual plot center is outside the narrow special centroid gate.
                u, v = (2, 0) if platform == "qq" else (0, 0)
                ordinary_star = plot_local_point(platform, u, v, capture.frame, self.layout)
                accepted, ignored = _filter_special_pickables(
                    capture, platform, self.layout,
                    self.detected(self.item(capture, *ordinary_star)),
                )
                self.assertEqual(accepted, [])
                self.assertEqual(ignored, 1)

    def test_outside_and_far_away_markers_are_not_actionable(self):
        capture = self.capture("qq")
        accepted, ignored = _filter_special_pickables(
            capture, "qq", self.layout,
            self.detected(self.item(capture, 5, 5), self.item(capture, 600, 1100)),
        )
        self.assertEqual(accepted, [])
        self.assertEqual(ignored, 2)

    def test_boundary_radius_is_strict(self):
        capture = self.capture("wechat")
        x, y = next(iter(_special_centers(capture, "wechat", self.layout).values()))
        accepted, ignored = _filter_special_pickables(
            capture, "wechat", self.layout,
            self.detected(self.item(capture, x + 13.5, y), self.item(capture, x + 14.5, y)),
        )
        self.assertEqual(len(accepted), 1)
        self.assertEqual(ignored, 1)

    def test_duplicate_marker_for_one_placement_stops(self):
        capture = self.capture("qq")
        x, y = next(iter(_special_centers(capture, "qq", self.layout).values()))
        with self.assertRaises(VisionStop) as caught:
            _filter_special_pickables(
                capture, "qq", self.layout,
                self.detected(self.item(capture, x, y), self.item(capture, x + 7, y + 5)),
            )
        self.assertEqual(caught.exception.code, "AMBIGUOUS_PICKABLES")

    def test_invalid_layout_and_overlapping_placements_stop(self):
        capture = self.capture("qq")
        for corruption in ("missing", "overlap", "non_square", "duplicate_id"):
            with self.subTest(corruption=corruption):
                layout = copy.deepcopy(self.layout)
                placements = layout["platforms"]["qq"]["safe_special_2x2"]
                if corruption == "missing":
                    del layout["platforms"]["qq"]["safe_special_2x2"]
                elif corruption == "overlap":
                    placements[1]["cells"] = placements[0]["cells"]
                elif corruption == "non_square":
                    placements[0]["cells"][0] = [0, 0]
                else:
                    placements[1]["id"] = placements[0]["id"]
                with self.assertRaises(VisionStop) as caught:
                    _special_centers(capture, "qq", layout)
                self.assertEqual(caught.exception.code, "INVALID_SPECIAL_GEOMETRY")

    def test_malformed_or_out_of_capture_marker_stops(self):
        capture = self.capture("qq")
        cases = (
            {"items": "not-a-list"},
            self.detected({"center_x": -1, "center_y": 300, "score": 0.9}),
            self.detected({"center_x": 20, "center_y": 30, "score": float("nan")}),
            self.detected({"center_x": 20, "center_y": 30}),
        )
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(VisionStop) as caught:
                    _filter_special_pickables(capture, "qq", self.layout, case)
                self.assertEqual(caught.exception.code, "INVALID_PICKABLE_CANDIDATE")

    def test_wrong_platform_or_window_fails_closed(self):
        capture = self.capture("qq")
        with self.assertRaises(VisionStop) as caught:
            _special_centers(capture, "wechat", self.layout)
        self.assertEqual(caught.exception.code, "INVALID_SPECIAL_GEOMETRY")

    def test_probe_is_read_only_and_not_harvest_authorization(self):
        for platform in ("qq", "wechat"):
            with self.subTest(platform=platform):
                capture = self.capture(platform, 2)
                x, y = next(iter(_special_centers(capture, platform, self.layout).values()))
                marker = self.item(capture, x, y)
                anchors = {
                    "anchors": {"onekey_harvest": {"template": "not-used"}},
                    "matching": {"default_scales": [1.0]},
                }
                with patch("farm_vision.match_anchor", return_value={
                    "matched": True, "local_center": [30, 40], "score": 0.99,
                }) as hand, patch("farm_vision.locate_pickables", return_value=self.detected(marker)) as locator:
                    result = probe_harvest(capture, anchors, platform, self.layout)
                self.assertEqual(hand.call_count, 1)
                self.assertEqual(locator.call_count, 1)
                self.assertEqual(locator.call_args.kwargs["dedupe_radius"], 60.0)
                self.assertEqual(len(result["pickables"]), 1)
                self.assertEqual(len(result["raw_pickable_candidates"]), 1)
                self.assertEqual(locator.call_args.kwargs["threshold"], 0.50)
                self.assertFalse(result["can_start_harvest"])
                self.assertTrue(result["requires_live_star_offset_and_occupancy_calibration"])
                self.assertTrue(result["needs_overlay_and_field_postcondition"])

    def test_real_qq_offsets_survive_diagnostics_without_click_authority(self):
        # 2026-10-31 controlled QQ harvest: three real stars at these
        # window-local points; all were outside the planting-safe 2x2 gates.
        capture = self.capture("qq")
        stars = [(262, 566), (342, 608), (342, 525)]
        detected = self.detected(*(self.item(capture, x, y, 0.6) for x, y in stars))
        anchors = {"anchors": {"onekey_harvest": {"template": "unused"}},
                   "matching": {"default_scales": [1.0]}}
        with patch("farm_vision.match_anchor", return_value={"matched": True,
                   "local_center": [297, 826], "score": 0.91}), \
             patch("farm_vision.locate_pickables", return_value=detected):
            result = probe_harvest(capture, anchors, "qq", self.layout)
        self.assertEqual(len(result["raw_pickable_candidates"]), 3)
        self.assertEqual(len(result["pickables"]), 0)
        self.assertEqual(result["ignored_outside_special_centers"], 3)
        self.assertFalse(result["can_start_harvest"])

    def test_io_composition_remains_read_only(self):
        capture = self.capture("qq")
        handle = WindowHandle(123, 456, capture.frame)
        probe = {"pickables": [], "can_start_harvest": False}
        with patch("farm_io.find_farm_window", return_value=handle) as registry, \
             patch("farm_io.capture_window", return_value=capture) as grab, \
             patch("farm_io.probe_harvest", return_value=probe) as vision:
            result = probe_window_harvest("qq", self.layout, {}, Path("/tmp/registry"))
        self.assertEqual(registry.call_count, 1)
        self.assertEqual(grab.call_count, 1)
        vision.assert_called_once_with(capture, {}, "qq", self.layout)
        self.assertEqual(result["harvest"], probe)
        self.assertEqual(result["field_alignment"]["code"], "FIELD_COLOR_REQUIRED")
        self.assertFalse(result["field_alignment"]["can_authorize_clicks"])
        self.assertEqual(result["click_count"], 0)
        self.assertEqual(result["llm_round_trips"], 0)


if __name__ == "__main__":
    unittest.main()
