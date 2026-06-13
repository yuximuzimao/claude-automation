import sys
import types
import unittest
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

fake_model = types.ModuleType("label_studio_ml.model")


class FakeLabelStudioMLBase:
    def __init__(self, **kwargs):
        self.label_config = kwargs.get("label_config")


fake_model.LabelStudioMLBase = FakeLabelStudioMLBase
fake_package = types.ModuleType("label_studio_ml")
fake_package.model = fake_model
sys.modules.setdefault("label_studio_ml", fake_package)
sys.modules.setdefault("label_studio_ml.model", fake_model)

from scripts import sam_ml_backend


class SAMBackendPromptTest(unittest.TestCase):
    def test_extracts_keypoint_prompt_from_label_studio_context(self):
        context = {
            "result": [
                {
                    "from_name": "prompt_point",
                    "to_name": "image",
                    "type": "keypointlabels",
                    "value": {
                        "x": 25.0,
                        "y": 75.0,
                        "keypointlabels": ["object"],
                    },
                }
            ]
        }

        prompt = sam_ml_backend.extract_sam_prompt(context, image_width=400, image_height=200)

        np.testing.assert_array_equal(prompt.point_coords, np.array([[100.0, 150.0]]))
        np.testing.assert_array_equal(prompt.point_labels, np.array([1]))
        self.assertIsNone(prompt.box)

    def test_extracts_negative_keypoint_prompt(self):
        context = {
            "result": [
                {
                    "type": "keypointlabels",
                    "is_positive": False,
                    "value": {
                        "x": 50.0,
                        "y": 25.0,
                        "keypointlabels": ["object"],
                    },
                }
            ]
        }

        prompt = sam_ml_backend.extract_sam_prompt(context, image_width=200, image_height=400)

        np.testing.assert_array_equal(prompt.point_coords, np.array([[100.0, 100.0]]))
        np.testing.assert_array_equal(prompt.point_labels, np.array([0]))

    def test_extracts_rectangle_prompt_from_label_studio_context(self):
        context = {
            "result": [
                {
                    "from_name": "bbox",
                    "to_name": "image",
                    "type": "rectanglelabels",
                    "value": {
                        "x": 10.0,
                        "y": 20.0,
                        "width": 30.0,
                        "height": 40.0,
                        "rectanglelabels": ["KGOS手提保温壶"],
                    },
                }
            ]
        }

        prompt = sam_ml_backend.extract_sam_prompt(context, image_width=500, image_height=300)

        self.assertIsNone(prompt.point_coords)
        self.assertIsNone(prompt.point_labels)
        np.testing.assert_array_equal(prompt.box, np.array([50.0, 60.0, 200.0, 180.0]))

    def test_builds_brushlabels_result_from_binary_mask(self):
        mask = np.zeros((4, 5), dtype=bool)
        mask[1:3, 2:4] = True

        result = sam_ml_backend.mask_to_brush_result(
            mask,
            label_name="KGOS手提保温壶",
            from_name="mask",
            to_name="image",
            score=0.91,
        )

        self.assertEqual(result["type"], "brushlabels")
        self.assertEqual(result["from_name"], "mask")
        self.assertEqual(result["to_name"], "image")
        self.assertEqual(result["original_width"], 5)
        self.assertEqual(result["original_height"], 4)
        self.assertEqual(result["value"]["format"], "rle")
        self.assertEqual(result["value"]["brushlabels"], ["KGOS手提保温壶"])
        self.assertIsInstance(result["value"]["rle"], list)
        self.assertGreater(len(result["value"]["rle"]), 0)
        self.assertAlmostEqual(result["score"], 0.91)

    def test_predict_uses_prompt_and_returns_mask_suggestion(self):
        backend = sam_ml_backend.SAMBackend()
        backend.predictor = FakePredictor()

        tasks = [{"data": {"image": "/unused/local.png"}}]
        context = {
            "result": [
                {
                    "type": "keypointlabels",
                    "value": {"x": 50.0, "y": 50.0, "keypointlabels": ["object"]},
                }
            ],
            "selectedLabel": "KGOS手提保温壶",
        }
        backend._load_image = lambda url: FakeImage(width=10, height=8)

        predictions = backend.predict(tasks, context=context)

        self.assertEqual(len(predictions), 1)
        self.assertEqual(predictions[0]["score"], 0.87)
        self.assertEqual(len(predictions[0]["result"]), 1)
        result = predictions[0]["result"][0]
        self.assertEqual(result["type"], "brushlabels")
        self.assertEqual(result["value"]["brushlabels"], ["KGOS手提保温壶"])
        np.testing.assert_array_equal(backend.predictor.point_coords, np.array([[5.0, 4.0]]))
        np.testing.assert_array_equal(backend.predictor.point_labels, np.array([1]))


class FakeImage:
    def __init__(self, width, height):
        self.size = (width, height)

    def convert(self, mode):
        return self

    def __array__(self, dtype=None):
        return np.zeros((self.size[1], self.size[0], 3), dtype=np.uint8)


class FakePredictor:
    def __init__(self):
        self.point_coords = None
        self.point_labels = None
        self.box = None

    def set_image(self, image):
        self.image = image

    def predict(self, point_coords=None, point_labels=None, box=None, multimask_output=True):
        self.point_coords = point_coords
        self.point_labels = point_labels
        self.box = box
        masks = np.zeros((3, 8, 10), dtype=bool)
        masks[1, 2:6, 3:8] = True
        scores = np.array([0.11, 0.87, 0.42])
        logits = np.zeros((3, 8, 10), dtype=np.float32)
        return masks, scores, logits


if __name__ == "__main__":
    unittest.main()
