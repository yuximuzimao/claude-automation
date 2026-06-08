import sys
import unittest
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import ocr_verify


class OcrVerifyTest(unittest.TestCase):
    def test_ambiguous_corn_chip_text_corrects_detected_flavors_evenly(self):
        yolo_counts = Counter({
            "KGOS玉米浓汤味玉米片 30g": 2,
            "KGOS香菜牛肉味玉米片 30g": 1,
        })
        text_counts = ocr_verify.parse_text_counts("玉米片 10")

        merged, unresolved = ocr_verify.merge_text_corrections(yolo_counts, text_counts)

        self.assertEqual(merged, Counter({
            "KGOS玉米浓汤味玉米片 30g": 5,
            "KGOS香菜牛肉味玉米片 30g": 5,
        }))
        self.assertEqual(unresolved, [])

    def test_ambiguous_text_does_not_create_concrete_flavor_without_yolo_evidence(self):
        text_counts = ocr_verify.parse_text_counts("玉米片 10")

        merged, unresolved = ocr_verify.merge_text_corrections(Counter(), text_counts)

        self.assertEqual(merged, Counter())
        self.assertEqual(unresolved, ["玉米片 10"])

    def test_exact_text_maps_to_erp_standard_name(self):
        text_counts = ocr_verify.parse_text_counts("腰围卡尺 1")

        self.assertEqual(text_counts.exact, Counter({
            "KGOS 三围尺 150cm": 1,
        }))
        self.assertEqual(text_counts.ambiguous, Counter())

    def test_flavored_nutrition_alias_maps_to_exact_erp_name(self):
        text_counts = ocr_verify.parse_text_counts("莓果营养粉 3")

        self.assertEqual(text_counts.exact, Counter({
            "KGOS蛋白多肽营养强化粉（莓果味） 30g*12": 3,
        }))
        self.assertEqual(text_counts.ambiguous, Counter())

    def test_unflavored_nutrition_alias_stays_ambiguous(self):
        text_counts = ocr_verify.parse_text_counts("营养粉 3")

        self.assertEqual(text_counts.exact, Counter())
        self.assertEqual(text_counts.ambiguous, Counter({
            "营养粉": 3,
        }))

    def test_exact_text_can_raise_yolo_undercount_without_changing_other_items(self):
        yolo_counts = Counter({
            "KGOS益生菌固体饮料 2g*15": 2,
            "KGOS逐光冰霸杯 900ml": 1,
        })
        text_counts = ocr_verify.parse_text_counts("益生菌 6 + 冰霸杯 1")

        merged, unresolved = ocr_verify.merge_text_corrections(yolo_counts, text_counts)

        self.assertEqual(merged, Counter({
            "KGOS益生菌固体饮料 2g*15": 6,
            "KGOS逐光冰霸杯 900ml": 1,
        }))
        self.assertEqual(unresolved, [])

    def test_supported_text_counts_resolve_ambiguous_expected_without_yolo_extras(self):
        support_counts = Counter({
            "KGOS玉米浓汤味玉米片 30g": 4,
            "KGOS香菜牛肉味玉米片 30g": 2,
            "KGOS逐光冰霸杯 900ml": 1,
        })
        text_counts = ocr_verify.parse_text_counts("玉米片 10")

        resolved, unresolved = ocr_verify.resolve_supported_text_counts(text_counts, support_counts)

        self.assertEqual(resolved, Counter({
            "KGOS玉米浓汤味玉米片 30g": 5,
            "KGOS香菜牛肉味玉米片 30g": 5,
        }))
        self.assertEqual(unresolved, [])

    def test_ambiguous_text_with_multiple_subtypes_and_non_divisible_count_is_unresolved(self):
        support_counts = Counter({
            "KGOS灵芝金花黑茶固体饮料（茉莉花茶味）试用装 5g（1g*5）": 1,
            "KGOS灵芝金花黑茶固体饮料（青柑普洱味）试用装 5g（1g*5）": 1,
        })
        text_counts = ocr_verify.parse_text_counts("黑茶体验装 1")

        resolved, unresolved = ocr_verify.resolve_supported_text_counts(text_counts, support_counts)

        self.assertEqual(resolved, Counter())
        self.assertEqual(unresolved, ["黑茶体验装 1"])


if __name__ == "__main__":
    unittest.main()
