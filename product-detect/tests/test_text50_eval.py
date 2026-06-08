import sys
import unittest
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import text50_eval


class Text50EvalTest(unittest.TestCase):
    def test_counter_from_items_uses_name_qty_pairs(self):
        counts = text50_eval.counter_from_items([
            {"name": "KGOS玉米浓汤味玉米片 30g", "qty": 5},
            {"name": "KGOS香菜牛肉味玉米片 30g", "qty": 5},
        ])

        self.assertEqual(counts, Counter({
            "KGOS玉米浓汤味玉米片 30g": 5,
            "KGOS香菜牛肉味玉米片 30g": 5,
        }))

    def test_evaluate_records_skips_pending_and_ambiguous_samples(self):
        records = {
            "real_001.jpg": {
                "status": "labeled",
                "text": "腰围卡尺 1",
                "items": [{"name": "KGOS 三围尺 150cm", "qty": 1}],
            },
            "real_002.jpg": {
                "status": "pending",
                "text": "",
                "items": [],
            },
            "real_003.jpg": {
                "status": "ambiguous",
                "text": "黑茶体验装1盒(口味随机)+腰围卡尺1个",
                "items": [],
            },
        }
        yolo_by_image = {
            "real_001.jpg": Counter({"KGOS 三围尺 150cm": 1}),
            "real_002.jpg": Counter({"KGOS益生菌固体饮料 2g*15": 1}),
            "real_003.jpg": Counter({"KGOS灵芝金花黑茶固体饮料（茉莉花茶味）试用装 5g（1g*5）": 1}),
        }

        result = text50_eval.evaluate_records(records, yolo_by_image)

        self.assertEqual(result["sample_counts"], {
            "total": 3,
            "labeled": 1,
            "pending": 1,
            "ambiguous": 1,
        })
        self.assertEqual(result["metrics"]["yolo"]["exact"], 1)
        self.assertEqual(result["metrics"]["yolo"]["total"], 1)

    def test_text_correction_improves_exact_match_when_policy_allows_it(self):
        records = {
            "real_005.jpg": {
                "status": "labeled",
                "text": "玉米片 10",
                "items": [
                    {"name": "KGOS玉米浓汤味玉米片 30g", "qty": 5},
                    {"name": "KGOS香菜牛肉味玉米片 30g", "qty": 5},
                ],
            }
        }
        yolo_by_image = {
            "real_005.jpg": Counter({
                "KGOS玉米浓汤味玉米片 30g": 4,
                "KGOS香菜牛肉味玉米片 30g": 2,
            })
        }

        result = text50_eval.evaluate_records(records, yolo_by_image)

        self.assertEqual(result["metrics"]["yolo"]["exact"], 0)
        self.assertEqual(result["metrics"]["merged"]["exact"], 1)
        self.assertEqual(result["metrics"]["gated"]["exact"], 1)
        self.assertEqual(result["rows"][0]["merged"], {
            "KGOS玉米浓汤味玉米片 30g": 5,
            "KGOS香菜牛肉味玉米片 30g": 5,
        })
        self.assertEqual(result["rows"][0]["unresolved"], [])

    def test_gated_mode_removes_text_unsupported_yolo_extras(self):
        records = {
            "real_004.jpg": {
                "status": "labeled",
                "text": "一次性吸管袋 1 + 腰围卡尺 1",
                "items": [
                    {"name": "KGOS饮料袋 10个/袋", "qty": 1},
                    {"name": "KGOS 三围尺 150cm", "qty": 1},
                ],
            }
        }
        yolo_by_image = {
            "real_004.jpg": Counter({
                "KGOS饮料袋 10个/袋": 1,
                "KGOS 三围尺 150cm": 1,
                "KGOS甘油二酯咖啡固体饮料(美式咖啡风味) 5g*12": 1,
            })
        }

        result = text50_eval.evaluate_records(records, yolo_by_image)

        self.assertEqual(result["metrics"]["gated"]["exact"], 1)
        self.assertEqual(result["rows"][0]["gated"], {
            "KGOS饮料袋 10个/袋": 1,
            "KGOS 三围尺 150cm": 1,
        })
        self.assertEqual(result["rows"][0]["blocked"], [
            "KGOS甘油二酯咖啡固体饮料(美式咖啡风味) 5g*12 1"
        ])

    def test_gated_mode_can_lower_exact_text_overcount(self):
        records = {
            "real_007.jpg": {
                "status": "labeled",
                "text": "一次性吸管袋 3",
                "items": [
                    {"name": "KGOS饮料袋 10个/袋", "qty": 3},
                ],
            }
        }
        yolo_by_image = {
            "real_007.jpg": Counter({"KGOS饮料袋 10个/袋": 4})
        }

        result = text50_eval.evaluate_records(records, yolo_by_image)

        self.assertEqual(result["metrics"]["gated"]["exact"], 1)
        self.assertEqual(result["rows"][0]["gated"], {
            "KGOS饮料袋 10个/袋": 3,
        })


if __name__ == "__main__":
    unittest.main()
