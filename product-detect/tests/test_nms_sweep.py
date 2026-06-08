import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import nms_sweep


class NmsSweepTest(unittest.TestCase):
    def test_parse_gift13_report_expected_counts(self):
        report = """
| `6.jpg` | 益生菌 3 + 玉米片-玉米浓汤味 5 + 玉米片-香菜牛肉味 5 | 益生菌 3 + 玉米片-玉米浓汤味 1 | Partial |
| `3.jpg` | 黑茶体验装-茉莉花茶味 1 + 腰围卡尺 1 | 黑茶体验装-茉莉花茶味 1 | Fail |
"""

        counts = nms_sweep.parse_gift13_expectations(report)

        self.assertEqual(counts["6.jpg"], Counter({
            "KGOS益生菌固体饮料 2g*15": 3,
            "KGOS玉米浓汤味玉米片 30g": 5,
            "KGOS香菜牛肉味玉米片 30g": 5,
        }))
        self.assertEqual(counts["3.jpg"], Counter({
            "KGOS灵芝金花黑茶固体饮料（茉莉花茶味）试用装 5g（1g*5）": 1,
            "KGOS 三围尺 150cm": 1,
        }))

    def test_count_label_file_uses_product_mapping_standard_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            label = Path(tmp) / "sample.txt"
            label.write_text(
                "7 0.1 0.1 0.2 0.2\n"
                "8 0.2 0.2 0.2 0.2\n"
                "10 0.3 0.3 0.2 0.2\n",
                encoding="utf-8",
            )

            counts = nms_sweep.count_label_file(
                label,
                [
                    "unused0",
                    "unused1",
                    "unused2",
                    "unused3",
                    "unused4",
                    "unused5",
                    "unused6",
                    "玉米片-玉米浓汤味",
                    "玉米片-香菜牛肉味",
                    "unused9",
                    "益生菌",
                ],
            )

        self.assertEqual(counts, Counter({
            "KGOS玉米浓汤味玉米片 30g": 1,
            "KGOS香菜牛肉味玉米片 30g": 1,
            "KGOS益生菌固体饮料 2g*15": 1,
        }))

    def test_compare_counts_computes_micro_precision_and_recall(self):
        expected = Counter({
            "KGOS玉米浓汤味玉米片 30g": 5,
            "KGOS香菜牛肉味玉米片 30g": 5,
            "KGOS益生菌固体饮料 2g*15": 3,
        })
        detected = Counter({
            "KGOS玉米浓汤味玉米片 30g": 5,
            "KGOS香菜牛肉味玉米片 30g": 2,
            "KGOS益生菌固体饮料 2g*15": 4,
            "KGOS逐光冰霸杯 900ml": 1,
        })

        metrics = nms_sweep.compare_counts(expected, detected)

        self.assertEqual(metrics.total_expected, 13)
        self.assertEqual(metrics.total_detected, 12)
        self.assertEqual(metrics.total_correct, 10)
        self.assertAlmostEqual(metrics.recall, 10 / 13)
        self.assertAlmostEqual(metrics.precision, 10 / 12)


if __name__ == "__main__":
    unittest.main()
