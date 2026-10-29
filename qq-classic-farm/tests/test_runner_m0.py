"""M0 pure-state regression suite; no game/window interactions."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from bootstrap_runner_state import make_bootstrap  # noqa: E402
from farm_runner import (RunnerStop, dry_run, load_json, save_state_atomic, validate_plan)  # noqa: E402
from seed_order import (PickerStateError, compute_picker_position,
                        compute_visible_order, consume_confirmed)  # noqa: E402


class RunnerM0Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.order, cls.state = make_bootstrap()
        cls.plan = load_json(ROOT / "examples/run-plan.sample.json")
        cls.layout = load_json(ROOT / "data/ui-layout.json")

    def test_snapshot_positions_both_platforms(self):
        cases = [
            ("qq", "泡泡棉花糖种子", (1, 3)),
            ("qq", "天山红枫种子", (4, 1)),
            ("qq", "紫薇种子", (3, 3)),
            ("wechat", "星语铃花种子", (1, 3)),
            ("wechat", "天山红枫种子", (2, 5)),
            ("wechat", "黄金果种子", (2, 1)),
        ]
        for platform, seed, expected in cases:
            with self.subTest(platform=platform, seed=seed):
                o = self.order["platforms"][platform]["stable_order"]
                q = self.state["platforms"][platform]["quantities"]
                p = compute_picker_position(platform, seed, o, q)
                self.assertEqual((p.page, p.slot), expected)

    def test_zero_stock_left_shift_cross_page(self):
        stable = [f"seed-{i}" for i in range(12)]
        qty = {seed: 1 for seed in stable}
        self.assertEqual(compute_picker_position("qq", "seed-5", stable, qty).as_dict(),
                         {"page": 2, "slot": 1, "visible_index": 5})
        after = consume_confirmed(stable, qty, "seed-2", 1)
        self.assertEqual(after["seed-2"], 0)
        self.assertEqual(compute_picker_position("qq", "seed-5", stable, after).as_dict(),
                         {"page": 1, "slot": 5, "visible_index": 4})
        self.assertEqual(len(stable), 12)
        self.assertEqual(qty["seed-2"], 1)

    def test_every_removal_recalculates_all_page_boundaries(self):
        for size in (5, 6, 10, 11, 22, 33):
            stable = [f"s{i}" for i in range(size)]
            initial = {seed: 1 for seed in stable}
            for removed in stable:
                after = consume_confirmed(stable, initial, removed, 1)
                expected = [seed for seed in stable if seed != removed]
                self.assertEqual(compute_visible_order(stable, after), expected)
                for index, seed in enumerate(expected):
                    pos = compute_picker_position("qq", seed, stable, after)
                    self.assertEqual((pos.page, pos.slot),
                                     (index // 5 + 1, index % 5 + 1))

    def test_known_zero_reappears_at_stable_position(self):
        stable = ["a", "b", "c", "d", "e", "f"]
        q = {"a": 1, "b": 0, "c": 1, "d": 1, "e": 1, "f": 1}
        self.assertEqual(compute_picker_position("wechat", "f", stable, q).page, 1)
        q["b"] = 3
        self.assertEqual(compute_picker_position("wechat", "b", stable, q).slot, 2)
        self.assertEqual(compute_picker_position("wechat", "f", stable, q).page, 2)

    def test_uncalibrated_positive_seed_must_stop(self):
        order = self.order["platforms"]["wechat"]
        self.assertIn("森野甜莓种子", order["historical_zero_candidates_uncalibrated"])
        q = dict(self.state["platforms"]["wechat"]["quantities"])
        q["森野甜莓种子"] = 1
        with self.assertRaises(PickerStateError) as caught:
            compute_visible_order(order["stable_order"], q)
        self.assertEqual(caught.exception.code, "ORDER_SYNC_REQUIRED")

    def test_bad_quantities_and_consumption_refused(self):
        with self.assertRaises(PickerStateError):
            compute_visible_order(["a"], {"a": -1})
        with self.assertRaises(PickerStateError):
            compute_visible_order(["a"], {"a": True})
        with self.assertRaises(PickerStateError) as caught:
            consume_confirmed(["a"], {"a": 2}, "a", 3)
        self.assertEqual(caught.exception.code, "INSUFFICIENT_INVENTORY")

    def test_dry_run_is_pure_and_counts_cells(self):
        before_state = copy.deepcopy(self.state)
        before_plan = copy.deepcopy(self.plan)
        result = dry_run(self.plan, self.order, self.state, self.layout)
        self.assertEqual(result["status"], "dry_run_ok")
        self.assertEqual(result["metrics"]["llm_round_trips"], 0)
        self.assertEqual(result["metrics"]["click_count"], 0)
        self.assertEqual(result["metrics"]["screenshot_count"], 0)
        self.assertFalse(result["persisted"])
        self.assertEqual(self.state, before_state)
        self.assertEqual(self.plan, before_plan)
        self.assertEqual(
            len([e for e in result["events"] if e["phase"] == "PLANT_SPECIAL"]), 5
        )
        self.assertEqual(
            [e["expected_occupied_cells"] for e in result["events"]
             if e["phase"] == "DRY_RUN_POSTCONDITION"], [24, 24]
        )
        self.assertEqual(result["simulated_quantities"]["qq"]["泡泡棉花糖种子"], 18)
        self.assertEqual(result["simulated_quantities"]["qq"]["天山红枫种子"], 6)
        self.assertEqual(result["simulated_quantities"]["wechat"]["星语铃花种子"], 6)
        self.assertEqual(result["simulated_quantities"]["wechat"]["黄金果种子"], 78)
        self.assertEqual(len(result["warnings"]), 2)

    def test_ordinary_shortage_blocks_before_any_real_click(self):
        plan = copy.deepcopy(self.plan)
        plan["cycles"][0]["platforms"]["wechat"]["ordinary"][0]["seed"] = "天山红枫种子"
        with self.assertRaises(PickerStateError) as caught:
            dry_run(plan, self.order, self.state, self.layout)
        self.assertEqual(caught.exception.code, "INSUFFICIENT_INVENTORY")
        self.assertEqual(self.state, RunnerM0Tests.state)

    def test_placement_overlap_and_incomplete_field_stop(self):
        plan = copy.deepcopy(self.plan)
        plan["cycles"][0]["platforms"]["qq"]["special"][0]["placements"][1] = "gold_a"
        with self.assertRaises(RunnerStop) as caught:
            dry_run(plan, self.order, self.state, self.layout)
        self.assertEqual(caught.exception.code, "INVALID_PLACEMENT")
        plan = copy.deepcopy(self.plan)
        plan["cycles"][0]["platforms"]["qq"]["ordinary"][0]["count"] = 11
        with self.assertRaises(RunnerStop):
            dry_run(plan, self.order, self.state, self.layout)

    def test_strategy_ui_fields_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan["cycles"][0]["platforms"]["qq"]["ordinary"][0]["picker_page"] = 4
        with self.assertRaises(RunnerStop) as caught:
            validate_plan(plan)
        self.assertEqual(caught.exception.code, "INVALID_PLAN")

    def test_atomic_write_and_run_next_safety(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "state.json"
            save_state_atomic(p, {"version": 1, "数量": 3})
            self.assertEqual(json.loads(p.read_text())["数量"], 3)
            save_state_atomic(p, {"version": 2, "数量": 0})
            self.assertEqual(json.loads(p.read_text())["数量"], 0)
            self.assertEqual(list(Path(d).glob("*.tmp")), [])
        run = subprocess.run(
            [sys.executable, str(ROOT / "scripts/farm_runner.py"), "run-next"],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(run.returncode, 2)
        self.assertEqual(json.loads(run.stdout)["code"], "RUNNER_NOT_READY")


if __name__ == "__main__":
    unittest.main()
