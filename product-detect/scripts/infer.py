#!/usr/bin/env python3
"""
生产推理模块

用于替换 product-mapping 中的 LLM 识图调用。
输出格式兼容现有流程。

用法（命令行测试）:
    python scripts/infer.py --brand kgos --image path/to/combo.jpg

调用方式（集成）:
    from scripts.infer import ProductDetector
    detector = ProductDetector("kgos")
    result = detector.identify("path/to/combo.jpg")
    # result: [{"name": "益生菌", "count": 2}, {"name": "维C泡腾片", "count": 1}]
"""

import json
import argparse
from pathlib import Path
from collections import Counter
from ultralytics import YOLO


class ProductDetector:
    """
    单例缓存模型，避免重复加载（每次推理约 0.5-2 秒）。
    """

    _instances: dict = {}

    def __new__(cls, brand: str):
        if brand not in cls._instances:
            instance = super().__new__(cls)
            instance._initialized = False
            cls._instances[brand] = instance
        return cls._instances[brand]

    def __init__(self, brand: str):
        if self._initialized:
            return

        project_root = Path(__file__).parent.parent
        model_path = project_root / "models" / f"{brand}_best.onnx"

        if not model_path.exists():
            # 回退到 .pt 格式
            pt_paths = list((project_root / "runs" / "detect").glob(f"{brand}_*/weights/best.pt"))
            if not pt_paths:
                raise FileNotFoundError(
                    f"找不到 {brand} 的模型文件。\n"
                    f"请先运行: python scripts/train.py --brand {brand}"
                )
            model_path = sorted(pt_paths)[-1]

        self.model = YOLO(str(model_path), task="detect")
        self.brand = brand
        self._initialized = True

    def identify(self, image_path: str, conf: float = 0.40) -> list[dict]:
        """
        识别图片中的产品。

        Args:
            image_path: 图片路径
            conf: 置信度阈值（0.4 是经验值，可按实际效果调整）

        Returns:
            [{"name": "产品名", "count": N}, ...]
            空图或无检测结果返回 []
        """
        results = self.model(image_path, conf=conf, verbose=False)[0]
        names = self.model.names  # {class_id: class_name}

        detected = [names[int(cls)] for cls in results.boxes.cls]
        if not detected:
            return []

        counts = Counter(detected)
        return [{"name": name, "count": cnt} for name, cnt in sorted(counts.items())]

    def identify_with_boxes(self, image_path: str, conf: float = 0.40) -> dict:
        """
        返回详细检测结果（含边界框），用于调试和核查。

        Returns:
            {
                "products": [{"name": ..., "count": N}],
                "detections": [{"name": ..., "conf": 0.92, "box": [x1,y1,x2,y2]}, ...]
            }
        """
        results = self.model(image_path, conf=conf, verbose=False)[0]
        names = self.model.names

        detections = []
        for box, cls, conf_val in zip(
            results.boxes.xyxy, results.boxes.cls, results.boxes.conf
        ):
            detections.append({
                "name": names[int(cls)],
                "conf": round(float(conf_val), 3),
                "box": [round(float(v)) for v in box],
            })

        counts = Counter(d["name"] for d in detections)
        products = [{"name": k, "count": v} for k, v in sorted(counts.items())]

        return {"products": products, "detections": detections}


def main():
    parser = argparse.ArgumentParser(description="产品识别推理")
    parser.add_argument("--brand", required=True, choices=["kgos", "hee"])
    parser.add_argument("--image", required=True, help="组合图路径")
    parser.add_argument("--conf", type=float, default=0.40, help="置信度阈值")
    parser.add_argument("--verbose", action="store_true", help="显示边界框详情")
    args = parser.parse_args()

    detector = ProductDetector(args.brand)

    if args.verbose:
        result = detector.identify_with_boxes(args.image, args.conf)
        print("\n识别结果:")
        for p in result["products"]:
            print(f"  {p['name']}: {p['count']} 件")
        print("\n检测详情:")
        for d in result["detections"]:
            print(f"  {d['name']}  conf={d['conf']}  box={d['box']}")
    else:
        result = detector.identify(args.image, args.conf)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
