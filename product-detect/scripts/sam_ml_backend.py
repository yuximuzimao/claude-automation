#!/usr/bin/env python3
"""
SAM ML Backend for Label Studio
启动：conda run -n yolov8 python scripts/sam_ml_backend.py
端口：9090
"""

import os
import sys
import io
import uuid
from dataclasses import dataclass
import numpy as np
from PIL import Image
from label_studio_ml.model import LabelStudioMLBase

SAM_CHECKPOINT = os.path.join(os.path.dirname(__file__), "../models/sam/sam_vit_b_01ec64.pth")
MODEL_TYPE = "vit_b"
DEFAULT_MASK_LABEL = "object"


@dataclass
class SAMPrompt:
    point_coords: np.ndarray | None = None
    point_labels: np.ndarray | None = None
    box: np.ndarray | None = None
    label_name: str = DEFAULT_MASK_LABEL


def _percent_to_pixel(value: float, size: int) -> float:
    return float(value) * float(size) / 100.0


def _context_results(context):
    if not context:
        return []
    if isinstance(context, dict):
        result = context.get("result") or context.get("results") or []
        return result if isinstance(result, list) else [result]
    if isinstance(context, list):
        return context
    return []


def _label_from_value(value: dict, context: dict | None) -> str:
    if isinstance(context, dict):
        for key in ("selectedLabel", "label", "brushlabel"):
            label = context.get(key)
            if isinstance(label, str) and label:
                return label
            if isinstance(label, dict) and label.get("value"):
                return label["value"]

    for key in ("brushlabels", "rectanglelabels", "keypointlabels", "labels"):
        labels = value.get(key)
        if labels:
            return labels[0]

    return DEFAULT_MASK_LABEL


def extract_sam_prompt(context, image_width: int, image_height: int) -> SAMPrompt | None:
    points = []
    labels = []
    box = None
    label_name = DEFAULT_MASK_LABEL

    context_dict = context if isinstance(context, dict) else None
    for result in _context_results(context):
        value = result.get("value") or {}
        result_type = (result.get("type") or "").lower()
        label_name = _label_from_value(value, context_dict)

        if result_type == "keypointlabels" or "keypointlabels" in value:
            if "x" not in value or "y" not in value:
                continue
            points.append([
                _percent_to_pixel(value["x"], image_width),
                _percent_to_pixel(value["y"], image_height),
            ])
            labels.append(1 if result.get("is_positive", True) else 0)

        if result_type == "rectanglelabels" or "rectanglelabels" in value:
            required = ("x", "y", "width", "height")
            if not all(key in value for key in required):
                continue
            x1 = _percent_to_pixel(value["x"], image_width)
            y1 = _percent_to_pixel(value["y"], image_height)
            x2 = _percent_to_pixel(value["x"] + value["width"], image_width)
            y2 = _percent_to_pixel(value["y"] + value["height"], image_height)
            box = np.array([x1, y1, x2, y2], dtype=float)

    if not points and box is None:
        return None

    return SAMPrompt(
        point_coords=np.array(points, dtype=float) if points else None,
        point_labels=np.array(labels, dtype=int) if labels else None,
        box=box,
        label_name=label_name,
    )


def _bits_to_bytes(bits: str) -> list[int]:
    padded = bits + ("0" * ((8 - len(bits) % 8) % 8))
    return [int(padded[i:i + 8], 2) for i in range(0, len(padded), 8)]


def _base_rle_encode(array: np.ndarray):
    values = np.asarray(array, dtype=np.uint8)
    if len(values) == 0:
        return [], [], []
    changes = np.flatnonzero(values[1:] != values[:-1]) + 1
    starts = np.concatenate(([0], changes))
    ends = np.concatenate((changes, [len(values)]))
    lengths = ends - starts
    run_values = values[starts]
    return lengths, starts, run_values


def encode_brush_rle(flattened_rgba: np.ndarray) -> list[int]:
    values = np.asarray(flattened_rgba, dtype=np.uint8).ravel()
    header = f"{len(values):032b}" + f"{7:05b}" + "".join(f"{size - 1:04b}" for size in (3, 4, 8, 16))
    body = []

    for length, value in zip(_base_rle_encode(values)[0], _base_rle_encode(values)[2]):
        remaining = int(length)
        while remaining > 0:
            chunk = min(remaining, 2**16)
            if chunk == 1:
                body.append("0" + "00" + "000" + f"{int(value):08b}")
            elif chunk <= 8:
                body.append("1" + "00" + f"{chunk - 1:03b}" + f"{int(value):08b}")
            elif chunk <= 16:
                body.append("1" + "01" + f"{chunk - 1:04b}" + f"{int(value):08b}")
            elif chunk <= 256:
                body.append("1" + "10" + f"{chunk - 1:08b}" + f"{int(value):08b}")
            else:
                body.append("1" + "11" + f"{chunk - 1:016b}" + f"{int(value):08b}")
            remaining -= chunk

    return _bits_to_bytes(header + "".join(body))


def mask_to_brush_result(mask, label_name: str, from_name: str = "mask", to_name: str = "image", score: float | None = None):
    mask_array = np.asarray(mask).astype(bool)
    height, width = mask_array.shape
    alpha = np.where(mask_array, 255, 0).astype(np.uint8)
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    rgba[:, :, 3] = alpha

    result = {
        "id": str(uuid.uuid4())[:8],
        "from_name": from_name,
        "to_name": to_name,
        "type": "brushlabels",
        "origin": "prediction",
        "image_rotation": 0,
        "original_width": width,
        "original_height": height,
        "value": {
            "format": "rle",
            "rle": encode_brush_rle(rgba.ravel()),
            "brushlabels": [label_name],
        },
    }
    if score is not None:
        result["score"] = float(score)
    return result


class SAMBackend(LabelStudioMLBase):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.predictor = None  # 懒加载，/setup 能快速返回不超时
        print("[SAM] Backend initialized (model loads on first predict)", flush=True)

    def _ensure_model_loaded(self):
        if self.predictor is None:
            from segment_anything import sam_model_registry, SamPredictor
            print(f"[SAM] Loading model from {SAM_CHECKPOINT}...", flush=True)
            sam = sam_model_registry[MODEL_TYPE](checkpoint=SAM_CHECKPOINT)
            self.predictor = SamPredictor(sam)
            print("[SAM] Model loaded.", flush=True)

    def predict(self, tasks, **kwargs):
        self._ensure_model_loaded()

        results = []
        for task in tasks:
            image_url = task["data"].get("image", "")
            try:
                image = self._load_image(image_url)
            except Exception as e:
                print(f"[SAM] Failed to load image {image_url}: {e}", flush=True)
                results.append({"result": []})
                continue

            img_array = np.array(image.convert("RGB"))
            self.predictor.set_image(img_array)

            prompt = extract_sam_prompt(
                kwargs.get("context"),
                image_width=img_array.shape[1],
                image_height=img_array.shape[0],
            )
            if prompt is None:
                results.append({"result": [], "score": 0.0})
                continue

            masks, scores, _ = self.predictor.predict(
                point_coords=prompt.point_coords,
                point_labels=prompt.point_labels,
                box=prompt.box,
                multimask_output=True,
            )
            best_index = int(np.argmax(scores))
            best_score = float(scores[best_index])
            brush_result = mask_to_brush_result(
                masks[best_index],
                label_name=prompt.label_name,
                from_name="mask",
                to_name="image",
                score=best_score,
            )
            results.append({"result": [brush_result], "score": best_score})

        return results

    def _load_image(self, url: str) -> Image.Image:
        # 处理 Label Studio local-files 路径
        if url.startswith("/data/local-files/"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(url.split("?", 1)[-1])
            rel_path = qs.get("d", [""])[0]
            doc_root = os.environ.get(
                "LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT",
                "/Users/chat/claude/product-detect/datasets"
            )
            full_path = os.path.join(doc_root, rel_path)
            return Image.open(full_path)
        else:
            import urllib.request
            with urllib.request.urlopen(url) as r:
                return Image.open(io.BytesIO(r.read()))


if __name__ == "__main__":
    from label_studio_ml.api import init_app
    app = init_app(model_class=SAMBackend)
    app.run(host="0.0.0.0", port=9090, debug=False)
