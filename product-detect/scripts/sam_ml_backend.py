#!/usr/bin/env python3
"""
SAM ML Backend for Label Studio
启动：conda run -n yolov8 python scripts/sam_ml_backend.py
端口：9090
"""

import os
import sys
import numpy as np
from PIL import Image
from label_studio_ml.model import LabelStudioMLBase

SAM_CHECKPOINT = os.path.join(os.path.dirname(__file__), "../models/sam/sam_vit_b_01ec64.pth")
MODEL_TYPE = "vit_b"


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

            # 没有 prompt 时返回空，等用户点击触发 interactive 模式
            results.append({"result": [], "score": 0.0})

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
