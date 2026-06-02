#!/usr/bin/env python3
"""
数据集验证工具

生成数据集后，运行此脚本检查标注是否合理。

用法:
    python scripts/verify.py --brand kgos --samples 20
"""

import random
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def resolve_dataset_dir(project_root: Path, brand: str, dataset: str | None, dataset_dir: Path | None) -> Path:
    """解析要验证的数据集目录。显式路径优先，其次 dataset 名称，最后品牌默认目录。"""
    if dataset_dir is not None:
        return dataset_dir
    return project_root / "datasets" / (dataset or brand)


def draw_boxes(image_path: Path, label_path: Path, class_names: list) -> Image.Image:
    """在图上绘制标注框。"""
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size

    COLORS = [
        "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7",
        "#DDA0DD", "#98D8C8", "#F7DC6F", "#BB8FCE", "#85C1E9",
    ]

    if label_path.exists():
        with open(label_path) as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) != 5:
                    continue
                cls_id, xc, yc, bw, bh = int(parts[0]), *[float(x) for x in parts[1:]]
                x1 = int((xc - bw / 2) * w)
                y1 = int((yc - bh / 2) * h)
                x2 = int((xc + bw / 2) * w)
                y2 = int((yc + bh / 2) * h)
                color = COLORS[cls_id % len(COLORS)]
                draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
                label = class_names[cls_id] if cls_id < len(class_names) else str(cls_id)
                draw.text((x1 + 4, y1 + 2), label, fill=color)

    return img


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand", required=True, choices=["kgos", "hee"])
    parser.add_argument("--dataset", default=None,
                        help="datasets/ 下的数据集目录名，例如 kgos_business_val；默认等于 brand")
    parser.add_argument("--dataset-dir", type=Path, default=None,
                        help="自定义数据集目录，优先级高于 --dataset")
    parser.add_argument("--samples", type=int, default=20, help="抽样验证数量")
    parser.add_argument("--split", default="train", choices=["train", "val"])
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    dataset_dir = resolve_dataset_dir(project_root, args.brand, args.dataset, args.dataset_dir)
    out_dir = dataset_dir / "_verify"
    out_dir.mkdir(exist_ok=True)

    # 读类别名
    yaml_path = dataset_dir / "data.yaml"
    class_names = []
    if yaml_path.exists():
        with open(yaml_path) as f:
            in_names = False
            for line in f:
                if line.strip() == "names:":
                    in_names = True
                elif in_names:
                    name = line.strip().lstrip("- ").strip()
                    if name:
                        class_names.append(name)
                    else:
                        in_names = False

    images_dir = dataset_dir / "images" / args.split
    labels_dir = dataset_dir / "labels" / args.split
    image_files = list(images_dir.glob("*.jpg"))

    if not image_files:
        print(f"找不到图片: {images_dir}")
        return

    samples = random.sample(image_files, min(args.samples, len(image_files)))

    for img_path in samples:
        label_path = labels_dir / (img_path.stem + ".txt")
        annotated = draw_boxes(img_path, label_path, class_names)
        annotated.save(out_dir / img_path.name)

    print(f"已生成 {len(samples)} 张验证图: {out_dir}")
    print("请用图片查看器打开确认标注是否准确")


if __name__ == "__main__":
    main()
