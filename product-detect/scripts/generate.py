#!/usr/bin/env python3
"""
合成训练数据生成器

用真实单品素材图生成 YOLOv8 格式训练集。生成规则面向 KGOS 白底业务图：
单品白底、混放无遮挡、混放遮挡，不引入 AI 生图或虚构商品外观。

用法:
    python scripts/generate.py --brand kgos --count 4000 --profile train
    python scripts/generate.py --brand kgos --count 600 --profile business-val
    python scripts/generate.py --brand kgos --preview
"""

import argparse
import json
import random
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance


# ── 配置 ──────────────────────────────────────────────────────────────────────

CANVAS_SIZE = 1280
WHITE_THRESHOLD = 235
OVERLAP_MAX_IOU = 0.05
MAX_PLACE_ATTEMPTS = 80
VAL_RATIO = 0.15
MIN_VISIBLE_RATIO = 0.35
ALPHA_THRESHOLD = 20

SCENE_RATIOS = {
    "single": 0.20,
    "mixed_clean": 0.35,
    "mixed_occluded": 0.45,
}

OCCLUSION_BUCKETS = (
    (0.15, 0.30),
    (0.30, 0.50),
    (0.50, 0.65),
)

# 类别别名合并（当前无需合并，随机杯子已有独立素材图）
CLASS_ALIASES = {}

# 当前业务弱项导向权重。不存在于某品牌素材目录的类会自然忽略。
CLASS_FREQ_WEIGHTS = {
    "黑咖体验装": 3.0,
    "酵素4.0体验装": 3.0,
    "腰围卡尺": 2.5,
    "冰霸杯": 2.0,
    "KGO手提袋": 1.8,
}

WEAK_CLASS_NAMES = tuple(CLASS_FREQ_WEIGHTS.keys())

SIMILAR_CLASS_GROUPS = {
    "黑咖体验装": ("美式咖啡", "生椰拿铁"),
    "酵素4.0体验装": ("酵素4.0",),
    "冰霸杯": ("随行杯", "摇摇杯", "马克杯", "随机杯子"),
    "KGO手提袋": ("帆布袋", "新年礼袋"),
}


class Profile(str, Enum):
    TRAIN = "train"
    BUSINESS_VAL = "business-val"


class SceneType(str, Enum):
    SINGLE = "single"
    MIXED_CLEAN = "mixed_clean"
    MIXED_OCCLUDED = "mixed_occluded"


@dataclass(frozen=True)
class InstanceSpec:
    class_name: str
    role: str = "normal"


@dataclass(frozen=True)
class PlacedMask:
    class_id: int
    mask: np.ndarray


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def remove_white_bg(img: Image.Image, threshold: int = WHITE_THRESHOLD) -> Image.Image:
    """将白色背景替换为透明（RGBA），保留产品主体。"""
    img = img.convert("RGBA")
    arr = np.array(img, dtype=np.uint8)
    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
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
    """训练集轻微调整商品亮度/对比度；business-val 不使用。"""
    if random.random() < 0.4:
        img = ImageEnhance.Brightness(img).enhance(random.uniform(0.85, 1.15))
    if random.random() < 0.3:
        img = ImageEnhance.Contrast(img).enhance(random.uniform(0.9, 1.1))
    return img


def weighted_sample_classes(asset_names: list, n: int) -> list:
    """按 CLASS_FREQ_WEIGHTS 加权采样 n 个不重复类别。"""
    weights = [CLASS_FREQ_WEIGHTS.get(name, 1.0) for name in asset_names]
    chosen = []
    remaining = list(zip(asset_names, weights))
    for _ in range(min(n, len(asset_names))):
        names_r, weights_r = zip(*remaining)
        pick = random.choices(names_r, weights=weights_r, k=1)[0]
        chosen.append(pick)
        remaining = [(nm, wt) for nm, wt in remaining if nm != pick]
        if not remaining:
            break
    return chosen


def scene_sequence_for_count(count: int) -> list[SceneType]:
    """按 20/35/45 生成固定比例场景序列，避免小数据集比例漂移过大。"""
    if count <= 0:
        return []
    single_count = round(count * SCENE_RATIOS[SceneType.SINGLE.value])
    clean_count = round(count * SCENE_RATIOS[SceneType.MIXED_CLEAN.value])
    occluded_count = count - single_count - clean_count
    scenes = (
        [SceneType.SINGLE] * single_count
        + [SceneType.MIXED_CLEAN] * clean_count
        + [SceneType.MIXED_OCCLUDED] * occluded_count
    )
    random.shuffle(scenes)
    return scenes


def choose_scene_type() -> SceneType:
    return random.choices(
        [SceneType.SINGLE, SceneType.MIXED_CLEAN, SceneType.MIXED_OCCLUDED],
        weights=[
            SCENE_RATIOS[SceneType.SINGLE.value],
            SCENE_RATIOS[SceneType.MIXED_CLEAN.value],
            SCENE_RATIOS[SceneType.MIXED_OCCLUDED.value],
        ],
        k=1,
    )[0]


def bbox_from_mask(mask: np.ndarray, canvas_size: int) -> tuple | None:
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    if not rows.any() or not cols.any():
        return None

    y1, y2 = int(np.where(rows)[0][0]), int(np.where(rows)[0][-1]) + 1
    x1, x2 = int(np.where(cols)[0][0]), int(np.where(cols)[0][-1]) + 1

    return (
        ((x1 + x2) / 2) / canvas_size,
        ((y1 + y2) / 2) / canvas_size,
        (x2 - x1) / canvas_size,
        (y2 - y1) / canvas_size,
    )


def visible_labels_from_masks(
    instances: list[PlacedMask],
    canvas_size: int,
    min_visible_ratio: float = MIN_VISIBLE_RATIO,
) -> list[tuple]:
    """
    根据最终叠放关系计算每个目标的可见 alpha bbox。

    instances 顺序就是粘贴顺序：后面的目标在前景，会遮挡前面的目标。
    可见面积低于 min_visible_ratio 的目标不写 label。
    """
    labels = []
    later_union = np.zeros((canvas_size, canvas_size), dtype=bool)

    reversed_labels = []
    for instance in reversed(instances):
        original_area = int(instance.mask.sum())
        if original_area <= 0:
            later_union |= instance.mask
            continue

        visible_mask = instance.mask & ~later_union
        visible_area = int(visible_mask.sum())
        later_union |= instance.mask

        if visible_area / original_area < min_visible_ratio:
            continue

        bbox = bbox_from_mask(visible_mask, canvas_size)
        if bbox is None:
            continue
        reversed_labels.append((instance.class_id, *bbox))

    for label in reversed(reversed_labels):
        labels.append(label)
    return labels


def mask_on_canvas(resized: Image.Image, x: int, y: int, canvas_size: int) -> np.ndarray:
    alpha = np.array(resized)[:, :, 3] > ALPHA_THRESHOLD
    mask = np.zeros((canvas_size, canvas_size), dtype=bool)
    h, w = alpha.shape
    mask[y:y + h, x:x + w] = alpha
    return mask


def scale_range_for_scene(scene_type: SceneType, n_total: int) -> tuple[float, float]:
    if scene_type == SceneType.SINGLE:
        return (0.45, 0.72)
    if n_total <= 3:
        return (0.28, 0.52)
    if n_total <= 6:
        return (0.20, 0.38)
    return (0.14, 0.27)


def random_position(canvas_size: int, pw: int, ph: int, role: str = "normal") -> tuple[int, int]:
    margin = max(8, int(canvas_size * 0.04))
    max_x = max(0, canvas_size - pw)
    max_y = max(0, canvas_size - ph)

    if role == "edge":
        if random.random() < 0.5:
            x = random.choice([margin, max(margin, max_x - margin)])
            y = random.randint(margin, max(margin, max_y - margin))
        else:
            x = random.randint(margin, max(margin, max_x - margin))
            y = random.choice([margin, max(margin, max_y - margin)])
        return min(max(x, 0), max_x), min(max(y, 0), max_y)

    if role in {"center", "background", "foreground"}:
        cx = random.randint(int(canvas_size * 0.38), int(canvas_size * 0.62))
        cy = random.randint(int(canvas_size * 0.38), int(canvas_size * 0.62))
        return min(max(cx - pw // 2, 0), max_x), min(max(cy - ph // 2, 0), max_y)

    x = random.randint(margin, max(margin, max_x - margin))
    y = random.randint(margin, max(margin, max_y - margin))
    return min(max(x, 0), max_x), min(max(y, 0), max_y)


def occluding_position(
    canvas_size: int,
    pw: int,
    ph: int,
    target_box: tuple[int, int, int, int],
    bucket: tuple[float, float],
) -> tuple[int, int]:
    """为遮挡场景生成一个与既有目标有可控重叠的前景位置。"""
    tx1, ty1, tx2, ty2 = target_box
    target_w, target_h = tx2 - tx1, ty2 - ty1
    coverage = random.uniform(*bucket)
    overlap_w = max(1, int(min(pw, target_w) * coverage ** 0.5))
    overlap_h = max(1, int(min(ph, target_h) * coverage ** 0.5))

    left_min = max(0, tx1 - pw + overlap_w)
    left_max = min(canvas_size - pw, tx2 - overlap_w)
    top_min = max(0, ty1 - ph + overlap_h)
    top_max = min(canvas_size - ph, ty2 - overlap_h)

    if left_min > left_max or top_min > top_max:
        return random_position(canvas_size, pw, ph, role="center")

    return random.randint(left_min, left_max), random.randint(top_min, top_max)


def build_scene_specs(assets: dict, scene_type: SceneType) -> list[InstanceSpec]:
    asset_names = list(assets.keys())
    if not asset_names:
        return []

    if scene_type == SceneType.SINGLE or len(asset_names) == 1:
        return [InstanceSpec(weighted_sample_classes(asset_names, 1)[0])]

    if scene_type == SceneType.MIXED_CLEAN:
        n_types = min(random.randint(2, min(6, len(asset_names))), len(asset_names))
        total = random.randint(max(3, n_types), min(8, max(3, n_types * 2)))
        chosen = weighted_sample_classes(asset_names, n_types)
        placements = chosen[:]
        while len(placements) < total:
            placements.append(random.choice(chosen))
        random.shuffle(placements)
        return [InstanceSpec(name) for name in placements]

    n_types = min(random.randint(2, min(6, len(asset_names))), len(asset_names))
    total = random.randint(max(3, n_types), 12)
    chosen = weighted_sample_classes(asset_names, n_types)

    available_weak = [name for name in WEAK_CLASS_NAMES if name in assets]
    anchor_weak = random.choice(available_weak) if available_weak else None
    if anchor_weak and anchor_weak not in chosen:
        chosen[-1] = anchor_weak

    if anchor_weak:
        similar_candidates = [
            name for name in SIMILAR_CLASS_GROUPS.get(anchor_weak, ())
            if name in assets and name not in chosen
        ]
        if similar_candidates and len(chosen) < n_types:
            chosen.append(random.choice(similar_candidates))
        elif similar_candidates and random.random() < 0.7:
            chosen[0] = random.choice(similar_candidates)

    placements = chosen[:]
    while len(placements) < total:
        placements.append(random.choice(chosen))

    random.shuffle(placements)
    specs = [InstanceSpec(name) for name in placements]

    if anchor_weak:
        role = random.choice(["foreground", "background", "edge", "center"])
        anchor_idx = next((i for i, spec in enumerate(specs) if spec.class_name == anchor_weak), None)
        if anchor_idx is not None:
            spec = InstanceSpec(anchor_weak, role=role)
            specs.pop(anchor_idx)
            if role == "background":
                specs.insert(0, spec)
            elif role == "foreground":
                specs.append(spec)
            else:
                specs.insert(random.randrange(len(specs) + 1), spec)

    return specs


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
    image_paths = sorted(
        p for p in brand_dir.iterdir()
        if p.suffix.lower() in supported and not p.name.startswith(("_", "."))
    )

    name_to_id = {}
    cid = 0
    for path in image_paths:
        name = path.stem
        if name in CLASS_ALIASES:
            continue
        name_to_id[name] = cid
        cid += 1

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
        if not bool((arr[:, :, 3] < 255).any()):
            img = remove_white_bg(img)
        assets[name] = (name_to_id[name], img)
    return assets


def place_instances(
    assets: dict,
    specs: list[InstanceSpec],
    canvas_size: int,
    scene_type: SceneType,
    profile: Profile,
) -> tuple[Image.Image, list[PlacedMask]]:
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (255, 255, 255, 255))
    placed_masks = []
    placed_boxes = []
    scale_range = scale_range_for_scene(scene_type, len(specs))

    for index, spec in enumerate(specs):
        class_id, asset_img = assets[spec.class_name]
        item_img = asset_img.copy()
        if profile == Profile.TRAIN:
            item_img = apply_augmentation(item_img)

        scale = random.uniform(*scale_range)
        pw = max(10, int(canvas_size * scale))
        ph = max(10, int(pw * item_img.height / item_img.width))
        if ph > canvas_size:
            ph = int(canvas_size * random.uniform(0.45, 0.85))
            pw = max(10, int(ph * item_img.width / item_img.height))
        if pw > canvas_size:
            pw = int(canvas_size * random.uniform(0.45, 0.85))
            ph = max(10, int(pw * item_img.height / item_img.width))

        resized = item_img.resize((pw, ph), Image.LANCZOS)
        placed = False
        role = spec.role

        for attempt in range(MAX_PLACE_ATTEMPTS):
            if scene_type == SceneType.MIXED_OCCLUDED and placed_boxes and (
                attempt < MAX_PLACE_ATTEMPTS * 0.65 or role in {"foreground", "background"}
            ):
                target_box = random.choice(placed_boxes)
                x, y = occluding_position(canvas_size, pw, ph, target_box, random.choice(OCCLUSION_BUCKETS))
            else:
                x, y = random_position(canvas_size, pw, ph, role=role)

            box = (x, y, x + pw, y + ph)
            if scene_type != SceneType.MIXED_OCCLUDED:
                overlap = any(iou(box, pb) > OVERLAP_MAX_IOU for pb in placed_boxes)
                if overlap:
                    continue

            canvas.paste(resized, (x, y), resized)
            placed_masks.append(PlacedMask(class_id=class_id, mask=mask_on_canvas(resized, x, y, canvas_size)))
            placed_boxes.append(box)
            placed = True
            break

        if not placed and scene_type != SceneType.MIXED_CLEAN:
            x, y = random_position(canvas_size, pw, ph, role=role)
            canvas.paste(resized, (x, y), resized)
            placed_masks.append(PlacedMask(class_id=class_id, mask=mask_on_canvas(resized, x, y, canvas_size)))
            placed_boxes.append((x, y, x + pw, y + ph))

    return canvas, placed_masks


def generate_one(
    assets: dict,
    canvas_size: int = CANVAS_SIZE,
    profile: Profile | str = Profile.TRAIN,
    scene_type: SceneType | str | None = None,
) -> tuple:
    """
    生成一张合成图。

    返回:
        (PIL.Image, labels)
        labels: [(class_id, x_c, y_c, w_n, h_n), ...]  YOLOv8 格式，归一化
    """
    profile = Profile(profile)
    scene_type = SceneType(scene_type) if scene_type is not None else choose_scene_type()
    specs = build_scene_specs(assets, scene_type)
    canvas, placed_masks = place_instances(assets, specs, canvas_size, scene_type, profile)
    labels = visible_labels_from_masks(placed_masks, canvas_size)
    return canvas.convert("RGB"), labels


# ── 数据集输出 ─────────────────────────────────────────────────────────────────

def class_names_from_assets(assets: dict) -> list[str]:
    id_to_name = {}
    for name, (cid, _) in assets.items():
        if name in CLASS_ALIASES:
            continue
        id_to_name[cid] = name
    return [id_to_name[i] for i in sorted(id_to_name)]


def write_data_yaml(out_dir: Path, class_names: list[str]) -> Path:
    yaml_path = out_dir / "data.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(f"path: {out_dir.resolve()}\n")
        f.write("train: images/train\n")
        f.write("val: images/val\n\n")
        f.write(f"nc: {len(class_names)}\n")
        f.write("names:\n")
        for name in class_names:
            f.write(f"  - {name}\n")
    return yaml_path


def write_class_map(out_dir: Path, assets: dict):
    class_map = {v[0]: k for k, v in assets.items() if k not in CLASS_ALIASES}
    with open(out_dir / "class_map.json", "w", encoding="utf-8") as f:
        json.dump(class_map, f, ensure_ascii=False, indent=2)


def write_dataset(
    brand: str,
    assets: dict,
    count: int,
    out_dir: Path,
    preview: bool = False,
    profile: Profile | str = Profile.TRAIN,
):
    """生成完整数据集并写入 YOLOv8 目录格式。"""
    profile = Profile(profile)

    if preview:
        count = min(count, 10)
        print(f"[preview 模式] 只生成 {count} 张，输出到 {out_dir}/preview/")
        out_images = out_dir / "preview"
        out_images.mkdir(parents=True, exist_ok=True)
        for i, scene_type in enumerate(scene_sequence_for_count(count)):
            img, _ = generate_one(assets, profile=profile, scene_type=scene_type)
            img.save(out_images / f"preview_{i:04d}_{scene_type.value}.jpg", quality=92)
        print(f"预览图已保存到 {out_images}，请人工确认效果后再正式生成")
        return

    for split in ["train", "val"]:
        (out_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (out_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

    class_names = class_names_from_assets(assets)
    print(f"类别数: {len(class_names)}")
    print(f"生成 profile: {profile.value}")

    if profile == Profile.BUSINESS_VAL:
        split_plan = [("val", count)]
        print(f"生成业务验收验证集 {count} 张（全部写入 val，不参与训练随机切分）")
    else:
        val_count = int(count * VAL_RATIO)
        train_count = count - val_count
        split_plan = [("train", train_count), ("val", val_count)]
        print(f"生成训练集 {train_count} 张 + 默认验证集 {val_count} 张，共 {count} 张")

    for split, n in split_plan:
        scenes = scene_sequence_for_count(n)
        scene_counts = {scene.value: scenes.count(scene) for scene in SceneType}
        print(
            f"  {split} 场景: single={scene_counts['single']} "
            f"mixed_clean={scene_counts['mixed_clean']} "
            f"mixed_occluded={scene_counts['mixed_occluded']}"
        )
        for i, scene_type in enumerate(scenes):
            img, labels = generate_one(assets, profile=profile, scene_type=scene_type)
            stem = f"{split}_{i:05d}"
            img.save(out_dir / "images" / split / f"{stem}.jpg", quality=92)

            label_lines = [f"{cls} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}"
                           for cls, xc, yc, w, h in labels]
            with open(out_dir / "labels" / split / f"{stem}.txt", "w", encoding="utf-8") as f:
                f.write("\n".join(label_lines))

            if (i + 1) % 100 == 0 or i == n - 1:
                print(f"  {split}: {i + 1}/{n}")

    yaml_path = write_data_yaml(out_dir, class_names)
    write_class_map(out_dir, assets)

    print(f"\n完成！数据集已写入 {out_dir}")
    print(f"  data.yaml: {yaml_path}")
    print(f"  类别映射: {out_dir / 'class_map.json'}")


# ── 入口 ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="合成训练数据生成器")
    parser.add_argument("--brand", required=True, choices=["kgos", "hee"],
                        help="品牌名称，对应 assets/<brand>/ 目录")
    parser.add_argument("--count", type=int, default=1200,
                        help="生成图片总数（默认 1200；KGOS 新训练建议 4000，business-val 建议 600）")
    parser.add_argument("--profile", choices=[profile.value for profile in Profile],
                        default=Profile.TRAIN.value,
                        help="train=训练集；business-val=独立业务验收验证集")
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="自定义输出目录；默认 train 写 datasets/<brand>，business-val 写 datasets/<brand>_business_val")
    parser.add_argument("--preview", action="store_true",
                        help="预览模式：只生成 10 张确认效果")
    parser.add_argument("--seed", type=int, default=42,
                        help="随机种子（默认 42，固定可复现）")
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    project_root = Path(__file__).parent.parent
    brand_dir = project_root / "assets" / args.brand
    profile = Profile(args.profile)
    default_out = args.brand if profile == Profile.TRAIN else f"{args.brand}_business_val"
    out_dir = args.out_dir if args.out_dir is not None else project_root / "datasets" / default_out

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
        weight = CLASS_FREQ_WEIGHTS.get(name, 1.0)
        weight_note = f", weight={weight}" if weight != 1.0 else ""
        print(f"  [{cid:02d}] {name}  ({img.width}×{img.height}{weight_note})")

    write_dataset(args.brand, assets, args.count, out_dir, args.preview, profile=profile)


if __name__ == "__main__":
    main()
