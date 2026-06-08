import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import train


class TrainConfigTest(unittest.TestCase):
    def test_run_name_defaults_to_brand_model_and_allows_override(self):
        self.assertEqual(train.resolve_run_name("kgos", "yolov8s", None), "kgos_yolov8s")
        self.assertEqual(train.resolve_run_name("kgos", "yolov8s", "kgos_yolov8s_train7"), "kgos_yolov8s_train7")

    def test_finetune_train_kwargs_use_train7_hyperparameters(self):
        kwargs = train.build_train_kwargs(
            project_root=Path("/project"),
            data_yaml=Path("/project/datasets/kgos/data.yaml"),
            brand="kgos",
            model_name="yolov8s",
            run_name="kgos_yolov8s_train7",
            epochs=60,
            resume=False,
            finetune=Path("/project/runs/kgos_yolov8s_train6/weights/best.pt"),
        )

        self.assertEqual(kwargs["project"], "/project/runs")
        self.assertEqual(kwargs["name"], "kgos_yolov8s_train7")
        self.assertEqual(kwargs["epochs"], 60)
        self.assertEqual(kwargs["lr0"], 0.002)
        self.assertEqual(kwargs["optimizer"], "AdamW")
        self.assertEqual(kwargs["patience"], 15)
        self.assertEqual(kwargs["mosaic"], 0.8)
        self.assertEqual(kwargs["close_mosaic"], 5)
        self.assertNotIn("resume", kwargs)


if __name__ == "__main__":
    unittest.main()
