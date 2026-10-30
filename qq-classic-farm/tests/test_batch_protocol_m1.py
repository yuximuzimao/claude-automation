"""CGEvent batch result decoding tests: no real mouse events."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from farm_harvest import HarvestStop
from farm_io import parse_click_batch_result


class BatchProtocolTests(unittest.TestCase):
    def test_success_means_sent_not_landed(self):
        payload = {"status": "clicks_sent_unverified", "code": None, "click_count": 3}
        self.assertEqual(parse_click_batch_result(json.dumps(payload), 0, 3), 3)

    def test_validation_only_must_never_count_as_execution(self):
        payload = {"status": "validated_no_click", "code": None, "click_count": 0}
        with self.assertRaises(HarvestStop) as caught:
            parse_click_batch_result(json.dumps(payload), 0, 1)
        self.assertEqual(caught.exception.code, "HARVEST_PARTIAL_ACTION")

    def test_helper_failure_preserves_partial_count(self):
        payload = {"status": "stopped", "code": "WINDOW_OCCLUDED", "click_count": 2}
        with self.assertRaises(HarvestStop) as caught:
            parse_click_batch_result(json.dumps(payload), 2, 3)
        self.assertEqual(caught.exception.code, "WINDOW_OCCLUDED")
        self.assertEqual(caught.exception.clicks_sent, 2)

    def test_success_count_mismatch_is_not_verified(self):
        payload = {"status": "clicks_sent_unverified", "click_count": 1}
        with self.assertRaises(HarvestStop) as caught:
            parse_click_batch_result(json.dumps(payload), 0, 3)
        self.assertEqual(caught.exception.code, "HARVEST_PARTIAL_ACTION")
        self.assertEqual(caught.exception.clicks_sent, 1)

    def test_malformed_or_impossible_counts_fail_closed(self):
        for payload in ('not-json', "[]", '{"status":"stopped"}',
                        '{"click_count":true}', '{"click_count":5}',
                        '{"click_count":-1}'):
            with self.subTest(payload=payload):
                with self.assertRaises(HarvestStop) as caught:
                    parse_click_batch_result(payload, 2, 3)
                self.assertEqual(caught.exception.code, "HARVEST_PARTIAL_ACTION")
                self.assertEqual(caught.exception.clicks_sent, 0)


if __name__ == "__main__":
    unittest.main()
