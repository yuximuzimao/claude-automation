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
OVERLAP_MAX_IOU = 0.05      # 允许的最大重叠比例（IoU）—— 仅用于非遮挡模式
MAX_PLACE_ATTEMPTS = 60     # 单个产品最多尝试放置次数
VAL_RATIO = 0.15            # 验证集比例

# 遮挡增强：60% 的图使用遮挡布局（产品叠压）
OCCLUSION_PROB = 0.30
# 遮挡模式下允许的最大 IoU（温和叠压，贴近真实）
OCCLUSION_MAX_IOU = 0.35
# 标注框最小宽高比，防止极窄/极扁框（维C泡腾片 AR=0.216 根因）
MIN_BBOX_AR = 0.35

# 类别别名合并（当前无需合并，随机杯子已有独立素材图）
CLASS_ALIASES = {}

# ── 训练改进配置（第四次训练：针对验证集弱项）────────────────────────────────────
# 弱项类的出现频率权重倍数（相对于普通类 = 1.0）
# 依据：eval_errors.py 验证集分析结果（2026-05-28）
CLASS_FREQ_WEIGHTS = {
    # v4 tight_bbox 受害者（极端窄框），需要大幅补量
    "维C泡腾片": 3.0,
    # v4 仍低于平均的弱项
    "阻断片": 2.0,
    "随机杯子": 2.0,
    "随行杯": 2.0,
    "益生菌": 2.0,
    # v4 退步的杯子类
    "马克杯": 1.5,
    "摇摇杯": 1.3,
    # 持续偏弱
    "黑茶-茉莉花茶味": 1.5,
    "一次性吸管袋": 1.5,
}



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


def clamp_bbox_ar(x_c: float, y_c: float, w_n: float, h_n: float,
                  min_ar: float = MIN_BBOX_AR) -> tuple:
    """防止极端宽高比标注框。tight_bbox 对窄长产品（维C泡腾片 AR=0.22）
    会生成极难学习的窄框。低于 MIN_BBOX_AR 时对称扩展宽度/高度。"""
    if w_n > 0 and h_n > 0:
        ar = w_n / h_n
        if ar < min_ar:
            w_n = h_n * min_ar  # 扩展宽度
        elif 1.0 / ar < min_ar:
            h_n = w_n * min_ar  # 扩展高度
    return x_c, y_c, min(w_n, 1.0), min(h_n, 1.0)


def tight_bbox_from_alpha(resized: Image.Image, paste_x: int, paste_y: int,
                          canvas_size: int) -> tuple | None:
    """从贴上画布的 RGBA 图，计算实际可见内容的紧密边界框。
    解决问题：产品图透明留白导致标注框偏大（阻断片 mAP50-95=0.913 根因）。
    返回 (x_c, y_c, w_n, h_n) 归一化坐标，或 None（无可见像素）。
    """
    alpha = np.array(resized)[:, :, 3]
    rows = np.any(alpha > 20, axis=1)
    cols = np.any(alpha > 20, axis=0)
    if not rows.any():
        return None
    rmin, rmax = int(np.where(rows)[0][0]), int(np.where(rows)[0][-1])
    cmin, cmax = int(np.where(cols)[0][0]), int(np.where(cols)[0][-1])

    abs_x1 = paste_x + cmin
    abs_y1 = paste_y + rmin
    abs_x2 = paste_x + cmax + 1
    abs_y2 = paste_y + rmax + 1

    x_c = (abs_x1 + abs_x2) / 2 / canvas_size
    y_c = (abs_y1 + abs_y2) / 2 / canvas_size
    w_n = (abs_x2 - abs_x1) / canvas_size
    h_n = (abs_y2 - abs_y1) / canvas_size

    return (
        min(max(x_c, 0.0), 1.0),
        min(max(y_c, 0.0), 1.0),
        min(w_n, 1.0),
        min(h_n, 1.0),
    )


def weighted_sample_classes(asset_names: list, n: int) -> list:
    """按 CLASS_FREQ_WEIGHTS 加权采样 n 个不重复类别。"""
    weights = [CLASS_FREQ_WEIGHTS.get(name, 1.0) for name in asset_names]
    total = sum(weights)
    probs = [w / total for w in weights]
    chosen = []
    remaining = list(zip(asset_names, probs))
    for _ in range(min(n, len(asset_names))):
        names_r, probs_r = zip(*remaining)
        total_r = sum(probs_r)
        norm = [p / total_r for p in probs_r]
        pick = random.choices(names_r, weights=norm, k=1)[0]
        chosen.append(pick)
        remaining = [(nm, pr) for nm, pr in remaining if nm != pick]
        if not remaining:
            break
    return chosen


# ── 核心生成逻辑 ───────────────────────────────────────────────────────────────

def load_assets(brand_dir: Path) -> dict:
    """
    加载品牌素材目录下的所有图片。
    自动识别背景类型：
      - PNG 含真实透明像素 → 直接使用 alpha 通道
      - JPG 或白底 PNG → 自动去白底
    返回: {class_name: (class_id, rgba_image)}
    """
    supported = {".jpg", ".jpeg", ".png", ".webp"}
    # 先过滤出图片文件再 enumerate，保证 class_id 从 0 连续递增
    image_paths = sorted(
        p for p in brand_dir.iterdir()
        if p.suffix.lower() in supported and not p.name.startswith(("_", "."))
    )
    # 先建名称→class_id 映射，处理别名合并
    # 第一遍：分配 class_id（别名不单独占 id）
    name_to_id = {}
    cid = 0
    for path in image_paths:
        name = path.stem
        if name in CLASS_ALIASES:
            continue  # 别名不分配新 id，后面映射到目标 id
        name_to_id[name] = cid
        cid += 1
    # 别名 → 映射到目标 id
    for alias, target in CLASS_ALIASES.items():
        if target in name_to_id:
            name_to_id[alias] = name_to_id[target]

    assets = {}
    for path in image_paths:
        name = path.stem
        if name not in name_to_id:
            continue
        img = Image.open(path).convert("RGBA")
        arr = np.array(img)
        has_real_transparency = bool((arr[:, :, 3] < 255).any())
        if not has_real_transparency:
            img = remove_white_bg(img)
        assets[name] = (name_to_id[name], img)
    return assets


def generate_one(assets: dict, canvas_size: int = CANVAS_SIZE) -> tuple:
    """
    生成一张合成组合图。
    60% 概率启用遮挡模式（产品大量叠压，更贴近真实组合图）。

    返回:
        (PIL.Image, labels)
        labels: [(class_id, x_c, y_c, w_n, h_n), ...]  YOLOv8 格式，归一化
    """
    # 背景：80% 纯白，20% 加轻微噪声（防帆布袋/新年礼袋白底过拟合）
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (255, 255, 255, 255))
    if random.random() < 0.20:
        bg_arr = np.full((canvas_size, canvas_size, 4), 255, dtype=np.uint8)
        noise = np.random.randint(-12, 13, (canvas_size, canvas_size, 3), dtype=np.int16)
        bg_arr[:, :, :3] = np.clip(bg_arr[:, :, :3].astype(np.int16) + noise, 200, 255).astype(np.uint8)
        canvas = Image.fromarray(bg_arr, "RGBA")

    labels = []
    placed_boxes = []

    occlusion_mode = random.random() < OCCLUSION_PROB
    max_iou = OCCLUSION_MAX_IOU if occlusion_mode else OVERLAP_MAX_IOU

    asset_names = list(assets.keys())

    # 真实组合图特征：多品种概率更高，按频率权重加权采样
    n_types = random.choices([1, 2, 3, 4], weights=[25, 35, 25, 15])[0]
    n_types = min(n_types, len(assets))
    chosen_classes = weighted_sample_classes(asset_names, n_types)

    placements = []
    for cls_name in chosen_classes:
        # 遮挡模式下数量更多（更密集）
        if occlusion_mode:
            count = random.choices([1, 2, 3, 4, 5, 6, 7, 8], weights=[15, 20, 20, 15, 10, 8, 7, 5])[0]
        else:
            count = random.choices([1, 2, 3, 4, 5, 6, 7], weights=[30, 25, 20, 10, 7, 5, 3])[0]
        for _ in range(count):
            placements.append(cls_name)
    random.shuffle(placements)

    # 遮挡模式：产品按随机 z 顺序叠压，后放的覆盖先放的
    # 标注框仍记录每个产品的真实位置（包括被遮挡的）
    n_total = len(placements)
    if n_total == 1:
        scale_range = (0.45, 0.75)
    elif n_total <= 3:
        scale_range = (0.28, 0.52)
    elif n_total <= 6:
        scale_range = (0.20, 0.38)
    else:
        scale_range = (0.14, 0.26)

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

        placed = False
        for attempt in range(MAX_PLACE_ATTEMPTS):
            x = random.randint(0, max(0, canvas_size - pw))
            y = random.randint(0, max(0, canvas_size - ph))
            box = (x, y, x + pw, y + ph)

            overlap = any(iou(box, pb) > max_iou for pb in placed_boxes)

            # 遮挡模式：更快放弃寻找非重叠位置，允许叠压
            force_threshold = 15 if occlusion_mode else 30
            if not overlap or attempt >= force_threshold:
                canvas.paste(resized, (x, y), resized)
                placed_boxes.append(box)

                # 用实际可见像素的紧密框代替整体 paste 框
                # 修复阻断片等产品透明留白导致的 mAP50-95 低问题
                tight = tight_bbox_from_alpha(resized, x, y, canvas_size)
                if tight is None:
                    # 回退到 paste 框
                    tight = (
                        min(max((x + pw / 2) / canvas_size, 0.0), 1.0),
                        min(max((y + ph / 2) / canvas_size, 0.0), 1.0),
                        min(pw / canvas_size, 1.0),
                        min(ph / canvas_size, 1.0),
                    )
                # AR clipping 防极端宽高比
                tight = clamp_bbox_ar(*tight, MIN_BBOX_AR)
                labels.append((class_id, *tight))
                placed = True
                break

        if not placed:
            pass

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

    # class_names：去重 + 按 id 排序（别名不重复出现）
    id_to_name = {}
    for name, (cid, _) in assets.items():
        if name in CLASS_ALIASES:
            continue  # 别名不单独出现在 names 列表里
        id_to_name[cid] = name
    class_names = [id_to_name[i] for i in sorted(id_to_name)]

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
