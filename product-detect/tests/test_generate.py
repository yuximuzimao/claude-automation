import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import generate


class GenerateRulesTest(unittest.TestCase):
    def test_visible_labels_use_uncovered_alpha_and_drop_low_visibility(self):
        base = np.zeros((100, 100), dtype=bool)
        base[20:80, 10:50] = True
        occluder = np.zeros((100, 100), dtype=bool)
        occluder[20:80, 30:50] = True

        labels = generate.visible_labels_from_masks(
            [
                generate.PlacedMask(class_id=0, mask=base),
                generate.PlacedMask(class_id=1, mask=occluder),
            ],
            canvas_size=100,
            min_visible_ratio=0.35,
        )

        self.assertEqual(len(labels), 2)
        self.assertEqual(labels[0][0], 0)
        self.assertAlmostEqual(labels[0][1], 0.20)
        self.assertAlmostEqual(labels[0][2], 0.50)
        self.assertAlmostEqual(labels[0][3], 0.20)
        self.assertAlmostEqual(labels[0][4], 0.60)

        heavy_occluder = np.zeros((100, 100), dtype=bool)
        heavy_occluder[20:80, 15:50] = True
        labels = generate.visible_labels_from_masks(
            [
                generate.PlacedMask(class_id=0, mask=base),
                generate.PlacedMask(class_id=1, mask=heavy_occluder),
            ],
            canvas_size=100,
            min_visible_ratio=0.35,
        )

        self.assertEqual([label[0] for label in labels], [1])

    def test_single_business_val_generation_keeps_plain_white_background(self):
        asset = Image.new("RGBA", (40, 80), (200, 30, 30, 255))
        assets = {"测试商品": (0, asset)}

        img, labels = generate.generate_one(
            assets,
            canvas_size=128,
            profile=generate.Profile.BUSINESS_VAL,
            scene_type=generate.SceneType.SINGLE,
        )

        self.assertEqual(img.mode, "RGB")
        self.assertEqual(img.getpixel((0, 0)), (255, 255, 255))
        self.assertEqual(len(labels), 1)

    def test_business_val_dataset_writes_all_images_to_isolated_val_split(self):
        asset = Image.new("RGBA", (40, 80), (20, 120, 200, 255))
        assets = {"测试商品": (0, asset)}

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "kgos_business_val"
            generate.write_dataset(
                "kgos",
                assets,
                count=3,
                out_dir=out_dir,
                preview=False,
                profile=generate.Profile.BUSINESS_VAL,
            )

            self.assertEqual(len(list((out_dir / "images" / "val").glob("*.jpg"))), 3)
            self.assertEqual(len(list((out_dir / "labels" / "val").glob("*.txt"))), 3)
            self.assertEqual(len(list((out_dir / "images" / "train").glob("*.jpg"))), 0)
            self.assertIn("val: images/val", (out_dir / "data.yaml").read_text())

    def test_weak_class_weights_target_current_business_failures(self):
        expected = {
            "黑咖体验装": 3.0,
            "酵素4.0体验装": 3.0,
            "腰围卡尺": 2.5,
            "冰霸杯": 2.0,
            "KGO手提袋": 1.8,
        }

        for class_name, weight in expected.items():
            self.assertEqual(generate.CLASS_FREQ_WEIGHTS[class_name], weight)


if __name__ == "__main__":
    unittest.main()
