from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook
from PIL import Image

from lib.assets import import_asset, verify_catalog
from lib.demo import parse_demo
from lib.jobs import create_job


class AssetWorkflowTests(unittest.TestCase):
    def test_exact_duplicate_is_not_copied_twice(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            brand_dir = root / "data" / "brands" / "demo"
            first = root / "first.png"
            second = root / "second.png"
            Image.new("RGBA", (32, 48), (10, 20, 30, 255)).save(first)
            second.write_bytes(first.read_bytes())

            imported, created = import_asset(
                source=first,
                brand_dir=brand_dir,
                asset_id="demo-product",
                role="product_source",
                description="demo",
            )
            duplicate, duplicate_created = import_asset(
                source=second,
                brand_dir=brand_dir,
                asset_id="ignored-duplicate-id",
                role="product_source",
                description="duplicate",
                move=True,
            )

            self.assertTrue(created)
            self.assertFalse(duplicate_created)
            self.assertEqual(imported["asset_id"], duplicate["asset_id"])
            self.assertFalse(second.exists())
            products = list((brand_dir / "assets" / "products").glob("*.png"))
            self.assertEqual(len(products), 1)
            self.assertEqual(verify_catalog(brand_dir), [])

    def test_catalog_path_is_portable_project_relative(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            brand_dir = root / "data" / "brands" / "demo"
            source = root / "product.png"
            Image.new("RGBA", (16, 16), (255, 0, 0, 128)).save(source)
            entry, _ = import_asset(
                source=source,
                brand_dir=brand_dir,
                asset_id="portable-product",
                role="product_source",
                description="portable",
            )
            self.assertEqual(entry["path"], "data/brands/demo/assets/products/portable-product.png")


class DemoWorkflowTests(unittest.TestCase):
    def test_excel_text_and_layout_are_extracted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workbook_path = Path(temp) / "demo.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "新品预热"
            sheet["A1"] = "IT'S COMING!"
            sheet["A2"] = "新品即将登场"
            sheet.merge_cells("A1:C1")
            sheet.column_dimensions["A"].width = 24
            workbook.save(workbook_path)

            parsed = parse_demo(workbook_path)
            self.assertEqual(parsed["sheets"][0]["title"], "新品预热")
            values = {cell["value"] for cell in parsed["sheets"][0]["cells"]}
            self.assertIn("IT'S COMING!", values)
            self.assertIn("新品即将登场", values)
            self.assertIn("A1:C1", parsed["sheets"][0]["merged_ranges"])


class JobWorkflowTests(unittest.TestCase):
    def test_new_job_uses_default_portrait_canvas(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            job_dir = create_job(Path(temp), brand="yaohei", name="测试任务", job_id="job-001")
            job = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
            self.assertEqual(job["canvas"]["width"], 1080)
            self.assertEqual(job["canvas"]["height"], 1920)
            self.assertEqual(job["canvas"]["aspect_ratio"], "9:16")
            self.assertTrue((job_dir / "brief" / "design-intent.json").exists())
            self.assertTrue((job_dir / "revisions.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
