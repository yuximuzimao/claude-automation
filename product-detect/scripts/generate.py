#!/usr/bin/env python3
"""
合成训练数据生成器

用单品素材图自动生成 YOLOv8 格式训练集，无需人工标注。

用法:
    python scripts/generate.py --brand kgos --count 1200
    python scripts/generate.py --brand kgos --count 1200 --preview  # 只生成前10张看效果
"""

import os
import sys
import json
import random
import argparse
import shutil
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np


# ── 配置 ──────────────────────────────────────────────────────────────────────

CANVAS_SIZE = 1280
WHITE_THRESHOLD = 235       # 白底识别阈值（高于此值的 RGB 视为背景）
OVERLAP_MAX_IOU = 0.05      # 允许的最大重叠比例（IoU）
MAX_PLACE_ATTEMPTS = 60     # 单个产品最多尝试放置次数
VAL_RATIO = 0.15            # 验证集比例


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def remove_white_bg(img: Image.Image, threshold: int = WHITE_THRESHOLD) -> Image.Image:
    """将白色背景替换为透明（RGBA），保留产品主体。"""
    img = img.convert("RGBA")
    arr = np.array(img, dtype=np.uint8)
    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
    # 三通道都高于阈值 = 白底
    mask = (r > threshold) & (g > threshold) & (b > threshold)
    arr[:, :, 3] = np.where(mask, 0, a)
    return Image.fromarray(arr)


def iou(box1, box2) -> float:
    """计算两个 box 的 IoU，box 格式为 (x1, y1, x2, y2)。"""
    ix1, iy1 = max(box1[0], box2[0]), max(box1[1], box2[1])
    ix2, iy2 = min(box1[2], box2[2]), min(box1[3], box2[3])
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    a1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    a2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    return inter / (a1 + a2 - inter)


def apply_augmentation(img: Image.Image) -> Image.Image:
    """轻微增强（亮度/对比度），模拟真实组合图的细微差异。"""
    if random.random() < 0.4:
        factor = random.uniform(0.85, 1.15)
        img = ImageEnhance.Brightness(img).enhance(factor)
    if random.random() < 0.3:
        factor = random.uniform(0.9, 1.1)
        img = ImageEnhance.Contrast(img).enhance(factor)
    return img


# ── 核心生成逻辑 ───────────────────────────────────────────────────────────────

def load_assets(brand_dir: Path) -> dict:
    """
    加载品牌素材目录下的所有图片。
    返回: {class_name: (class_id, rgba_image)}
    """
    supported = {".jpg", ".jpeg", ".png", ".webp"}
    assets = {}
    for i, path in enumerate(sorted(brand_dir.iterdir())):
        if path.suffix.lower() not in supported:
            continue
        img = Image.open(path).convert("RGBA")
        # 如果是 JPG（无透明通道），去白底
        if path.suffix.lower() in {".jpg", ".jpeg"}:
            img = remove_white_bg(img)
        class_name = path.stem  # 文件名（不含后缀）作为类别名
        assets[class_name] = (i, img)
    return assets


def generate_one(assets: dict, canvas_size: int = CANVAS_SIZE) -> tuple:
    """
    生成一张合成组合图。

    返回:
        (PIL.Image, labels)
        labels: [(class_id, x_c, y_c, w_n, h_n), ...]  YOLOv8 格式，归一化
    """
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (255, 255, 255, 255))
    labels = []
    placed_boxes = []

    # 随机决定本图出现的产品种类数（1-3种）和每种的数量
    n_types = random.choices([1, 2, 3], weights=[40, 40, 20])[0]
    n_types = min(n_types, len(assets))
    chosen_classes = random.sample(list(assets.keys()), n_types)

    placements = []
    for cls_name in chosen_classes:
        # 同类数量：1-7件，偏向少量
        count = random.choices([1, 2, 3, 4, 5, 6, 7], weights=[30, 25, 20, 10, 7, 5, 3])[0]
        for _ in range(count):
            placements.append(cls_name)
    random.shuffle(placements)

    # 根据总件数决定单件缩放比例
    n_total = len(placements)
    if n_total == 1:
        scale_range = (0.45, 0.75)
    elif n_total <= 3:
        scale_range = (0.30, 0.50)
    elif n_total <= 6:
        scale_range = (0.22, 0.35)
    else:
        scale_range = (0.15, 0.25)

    for cls_name in placements:
        class_id, asset_img = assets[cls_name]
        asset_img = apply_augmentation(asset_img.copy())

        scale = random.uniform(*scale_range)
        pw = int(canvas_size * scale)
        aspect = asset_img.height / asset_img.width
        ph = int(pw * aspect)
        ph = max(ph, 10)
        pw = max(pw, 10)

        resized = asset_img.resize((pw, ph), Image.LANCZOS)

        # 寻找非重叠位置
        placed = False
        for attempt in range(MAX_PLACE_ATTEMPTS):
            x = random.randint(0, max(0, canvas_size - pw))
            y = random.randint(0, max(0, canvas_size - ph))
            box = (x, y, x + pw, y + ph)

            overlap = any(iou(box, pb) > OVERLAP_MAX_IOU for pb in placed_boxes)

            # 30次尝试后允许轻微重叠，60次后强制放置
            if not overlap or attempt >= 30:
                canvas.paste(resized, (x, y), resized)
                placed_boxes.append(box)

                x_c = (x + pw / 2) / canvas_size
                y_c = (y + ph / 2) / canvas_size
                w_n = pw / canvas_size
                h_n = ph / canvas_size
                labels.append((class_id, x_c, y_c, w_n, h_n))
                placed = True
                break

        if not placed:
            pass  # 跳过这个，不影响其他

    return canvas.convert("RGB"), labels


# ── 数据集输出 ─────────────────────────────────────────────────────────────────

def write_dataset(brand: str, assets: dict, count: int, out_dir: Path, preview: bool = False):
    """生成完整数据集并写入 YOLOv8 目录格式。"""

    if preview:
        count = min(count, 10)
        print(f"[preview 模式] 只生成 {count} 张，输出到 {out_dir}/preview/")
        out_images = out_dir / "preview"
        out_images.mkdir(parents=True, exist_ok=True)
        for i in range(count):
            img, _ = generate_one(assets)
            img.save(out_images / f"preview_{i:04d}.jpg", quality=92)
        print(f"预览图已保存到 {out_images}，请人工确认效果后再正式生成")
        return

    # 正式输出
    for split in ["train", "val"]:
        (out_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (out_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

    val_count = int(count * VAL_RATIO)
    train_count = count - val_count

    class_names = [name for name, _ in sorted(assets.items(), key=lambda x: x[1][0])]

    print(f"生成训练集 {train_count} 张 + 验证集 {val_count} 张，共 {count} 张")
    print(f"类别数: {len(class_names)}")

    for split, n in [("train", train_count), ("val", val_count)]:
        for i in range(n):
            img, labels = generate_one(assets)
            stem = f"{split}_{i:05d}"
            img.save(out_dir / "images" / split / f"{stem}.jpg", quality=92)

            label_lines = [f"{cls} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}"
                           for cls, xc, yc, w, h in labels]
            with open(out_dir / "labels" / split / f"{stem}.txt", "w") as f:
                f.write("\n".join(label_lines))

            if (i + 1) % 100 == 0 or i == n - 1:
                print(f"  {split}: {i+1}/{n}")

    # 写 data.yaml
    yaml_path = out_dir / "data.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(f"path: {out_dir.resolve()}\n")
        f.write("train: images/train\n")
        f.write("val: images/val\n\n")
        f.write(f"nc: {len(class_names)}\n")
        f.write("names:\n")
        for name in class_names:
            f.write(f"  - {name}\n")

    # 写类别映射 JSON（供推理时用）
    class_map = {i: name for i, (name, _) in
                 enumerate(sorted(assets.items(), key=lambda x: x[1][0]))}
    # 重建正确映射
    class_map = {v[0]: k for k, v in assets.items()}
    with open(out_dir / "class_map.json", "w", encoding="utf-8") as f:
        json.dump(class_map, f, ensure_ascii=False, indent=2)

    print(f"\n完成！数据集已写入 {out_dir}")
    print(f"  data.yaml: {yaml_path}")
    print(f"  类别映射: {out_dir / 'class_map.json'}")


# ── 入口 ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="合成训练数据生成器")
    parser.add_argument("--brand", required=True, choices=["kgos", "hee"],
                        help="品牌名称，对应 assets/<brand>/ 目录")
    parser.add_argument("--count", type=int, default=1200,
                        help="生成图片总数（默认 1200）")
    parser.add_argument("--preview", action="store_true",
                        help="预览模式：只生成 10 张确认效果")
    parser.add_argument("--seed", type=int, default=42,
                        help="随机种子（默认 42，固定可复现）")
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    project_root = Path(__file__).parent.parent
    brand_dir = project_root / "assets" / args.brand
    out_dir = project_root / "datasets" / args.brand

    if not brand_dir.exists():
        print(f"错误：找不到素材目录 {brand_dir}")
        print(f"请将 {args.brand} 品牌的单品素材图放入该目录，每张图以产品名命名")
        print(f"示例: assets/{args.brand}/益生菌.jpg")
        sys.exit(1)

    assets = load_assets(brand_dir)
    if not assets:
        print(f"错误：{brand_dir} 中没有找到图片文件")
        sys.exit(1)

    print(f"加载素材 {len(assets)} 个类别:")
    for name, (cid, img) in sorted(assets.items(), key=lambda x: x[1][0]):
        print(f"  [{cid:02d}] {name}  ({img.width}×{img.height})")

    write_dataset(args.brand, assets, args.count, out_dir, args.preview)


if __name__ == "__main__":
    main()
