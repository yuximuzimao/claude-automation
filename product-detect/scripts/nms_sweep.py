#!/usr/bin/env python3
"""
NMS/conf joint sweep for KGOS dense-layout detection.

The report compares expected product counts with YOLO detections. Business-
distinct flavors must remain separate when they map to separate SKUs.
"""

import argparse
import json
import random
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


PRODUCT_MAPPING_FEATURES = (
    Path(__file__).resolve().parents[2]
    / "product-mapping"
    / "data"
    / "products"
    / "kgos"
    / "features.json"
)


@dataclass(frozen=True)
class CountMetrics:
    total_expected: int
    total_detected: int
    total_correct: int

    @property
    def recall(self) -> float:
        if self.total_expected == 0:
            return 0.0
        return self.total_correct / self.total_expected

    @property
    def precision(self) -> float:
        if self.total_detected == 0:
            return 0.0
        return self.total_correct / self.total_detected


@dataclass(frozen=True)
class SweepResult:
    iou: float
    conf: float
    metrics: CountMetrics
    per_image: list[dict]


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def load_standard_name_map() -> dict[str, str]:
    features = json.loads(PRODUCT_MAPPING_FEATURES.read_text(encoding="utf-8"))
    return {short_name: item["erpName"] for short_name, item in features.items()}


def standard_name(name: str) -> str:
    clean = name.strip()
    return load_standard_name_map().get(clean, clean)


def parse_expected_cell(cell: str) -> Counter:
    counts: Counter = Counter()
    for part in cell.split("+"):
        text = re.sub(r"（.*?）", "", part).strip()
        match = re.match(r"(.+?)\s+(\d+)$", text)
        if not match:
            continue
        name, count = match.groups()
        counts[standard_name(name)] += int(count)
    return counts


def parse_gift13_expectations(report_text: str) -> dict[str, Counter]:
    expectations: dict[str, Counter] = {}
    for line in report_text.splitlines():
        if not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        image_name = cells[0].strip("`")
        if not image_name.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        expectations[image_name] = parse_expected_cell(cells[1])
    return expectations


def load_class_names(data_yaml: Path) -> list[str]:
    names: list[str] = []
    in_names = False
    for line in data_yaml.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == "names:":
            in_names = True
            continue
        if in_names and stripped.startswith("- "):
            names.append(stripped[2:].strip())
        elif in_names and stripped and not stripped.startswith("- "):
            break
    if not names:
        raise ValueError(f"No class names found in {data_yaml}")
    return names


def count_label_file(label_path: Path, class_names: list[str]) -> Counter:
    counts: Counter = Counter()
    if not label_path.exists():
        return counts
    for line in label_path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if not fields:
            continue
        class_id = int(fields[0])
        counts[standard_name(class_names[class_id])] += 1
    return counts


def compare_counts(expected: Counter, detected: Counter) -> CountMetrics:
    total_expected = sum(expected.values())
    total_detected = sum(detected.values())
    total_correct = sum(min(expected[name], detected[name]) for name in expected)
    return CountMetrics(total_expected, total_detected, total_correct)


def load_eval_items(
    gift_images_dir: Path,
    gift_report: Path,
    business_data_yaml: Path,
    business_sample_size: int,
    seed: int,
) -> list[dict]:
    class_names = load_class_names(business_data_yaml)
    business_root = business_data_yaml.parent

    report_text = gift_report.read_text(encoding="utf-8")
    gift_expected = parse_gift13_expectations(report_text)
    items = []
    for image_name, expected in sorted(gift_expected.items()):
        image_path = gift_images_dir / image_name
        if image_path.exists():
            items.append({
                "subset": "gift13",
                "image": image_path,
                "expected": expected,
            })

    business_images = sorted((business_root / "images" / "val").glob("*.jpg"))
    rng = random.Random(seed)
    sampled = business_images[:]
    rng.shuffle(sampled)
    for image_path in sorted(sampled[:business_sample_size]):
        label_path = business_root / "labels" / "val" / f"{image_path.stem}.txt"
        items.append({
            "subset": "business-val",
            "image": image_path,
            "expected": count_label_file(label_path, class_names),
        })

    if not items:
        raise ValueError("No evaluation items found")
    return items


def count_yolo_result(result, names: dict[int, str] | list[str]) -> Counter:
    counts: Counter = Counter()
    for cls in result.boxes.cls:
        class_id = int(cls)
        name = names[class_id] if isinstance(names, list) else names[class_id]
        counts[standard_name(name)] += 1
    return counts


def run_sweep(model_path: Path, items: list[dict], ious: list[float], confs: list[float]) -> list[SweepResult]:
    from ultralytics import YOLO

    model = YOLO(str(model_path), task="detect")
    results: list[SweepResult] = []
    for iou in ious:
        for conf in confs:
            per_image = []
            expected_total: Counter = Counter()
            detected_total: Counter = Counter()
            for item in items:
                prediction = model(
                    str(item["image"]),
                    conf=conf,
                    iou=iou,
                    imgsz=640,
                    device="cpu",
                    verbose=False,
                )[0]
                detected = count_yolo_result(prediction, model.names)
                expected = item["expected"]
                metrics = compare_counts(expected, detected)
                expected_total.update(expected)
                detected_total.update(detected)
                per_image.append({
                    "subset": item["subset"],
                    "image": item["image"].name,
                    "expected": dict(expected),
                    "detected": dict(detected),
                    "recall": metrics.recall,
                    "precision": metrics.precision,
                })
            results.append(SweepResult(
                iou=iou,
                conf=conf,
                metrics=compare_counts(expected_total, detected_total),
                per_image=per_image,
            ))
    return results


def fmt_ratio(value: float) -> str:
    return f"{value:.3f}"


def render_heatmap(results: list[SweepResult], ious: list[float], confs: list[float], metric: str) -> str:
    by_pair = {(result.iou, result.conf): result for result in results}
    lines = ["| iou \\ conf | " + " | ".join(f"{conf:.2f}" for conf in confs) + " |"]
    lines.append("|---|" + "|".join("---:" for _ in confs) + "|")
    for iou in ious:
        cells = []
        for conf in confs:
            result = by_pair[(iou, conf)]
            value = getattr(result.metrics, metric)
            cells.append(fmt_ratio(value))
        lines.append(f"| {iou:.2f} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_report(results: list[SweepResult], items: list[dict], ious: list[float], confs: list[float]) -> str:
    best = max(results, key=lambda result: (result.metrics.recall, result.metrics.precision))
    lines = [
        "# NMS + Conf Sweep Report",
        "",
        "Date: 2026-06-04",
        "",
        "## Dataset",
        "",
        f"- Images: {len(items)} total",
        f"- gift13: {sum(1 for item in items if item['subset'] == 'gift13')}",
        f"- business-val: {sum(1 for item in items if item['subset'] == 'business-val')}",
        "- Counting standard: product-mapping `recognition.items` format, compared as `{name: erpName, qty}` set equality.",
        "- Standard names come from `product-mapping/data/products/kgos/features.json` `erpName` values.",
        "- Business-distinct flavors stay separate. Example: `KGOS玉米浓汤味玉米片 30g×5 + KGOS香菜牛肉味玉米片 30g×5` is not equivalent to `玉米片×10`.",
        "",
        "## Best Setting",
        "",
        f"- iou={best.iou:.2f}, conf={best.conf:.2f}",
        f"- recall={best.metrics.recall:.3f}",
        f"- precision={best.metrics.precision:.3f}",
        f"- total_expected={best.metrics.total_expected}",
        f"- total_detected={best.metrics.total_detected}",
        f"- total_correct={best.metrics.total_correct}",
        "",
        "## Recall Heatmap",
        "",
        render_heatmap(results, ious, confs, "recall"),
        "",
        "## Precision Heatmap",
        "",
        render_heatmap(results, ious, confs, "precision"),
        "",
        "## Full Matrix",
        "",
        "| iou | conf | expected | detected | correct | recall | precision |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for result in sorted(results, key=lambda r: (r.iou, r.conf)):
        lines.append(
            f"| {result.iou:.2f} | {result.conf:.2f} | "
            f"{result.metrics.total_expected} | {result.metrics.total_detected} | "
            f"{result.metrics.total_correct} | {result.metrics.recall:.3f} | "
            f"{result.metrics.precision:.3f} |"
        )

    lines.extend([
        "",
        "## Best Setting Per-Image Detail",
        "",
        "| subset | image | expected | detected | recall | precision |",
        "|---|---|---|---|---:|---:|",
    ])
    for row in best.per_image:
        lines.append(
            f"| {row['subset']} | `{row['image']}` | {row['expected']} | "
            f"{row['detected']} | {row['recall']:.3f} | {row['precision']:.3f} |"
        )
    lines.append("")
    return "\n".join(lines)


def parse_float_list(raw: str) -> list[float]:
    return [float(part.strip()) for part in raw.split(",") if part.strip()]


def main() -> None:
    root = project_root()
    parser = argparse.ArgumentParser(description="Sweep YOLO NMS iou and confidence thresholds")
    parser.add_argument("--model", type=Path, default=root / "runs/kgos_yolov8s_train6/weights/best.pt")
    parser.add_argument("--gift-images", type=Path, default=root / "datasets/kgos_real_golden_gift13/images")
    parser.add_argument("--gift-report", type=Path, default=root / "docs/real-golden-gift13-train6-report.md")
    parser.add_argument("--business-data", type=Path, default=root / "datasets/kgos_business_val/data.yaml")
    parser.add_argument("--business-sample-size", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ious", default="0.3,0.4,0.5,0.6,0.7")
    parser.add_argument("--confs", default="0.25,0.35,0.45")
    parser.add_argument("--output", type=Path, default=root / "docs/nms-sweep-report.md")
    args = parser.parse_args()

    ious = parse_float_list(args.ious)
    confs = parse_float_list(args.confs)
    items = load_eval_items(
        gift_images_dir=args.gift_images,
        gift_report=args.gift_report,
        business_data_yaml=args.business_data,
        business_sample_size=args.business_sample_size,
        seed=args.seed,
    )
    results = run_sweep(args.model, items, ious, confs)
    report = render_report(results, items, ious, confs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    best = max(results, key=lambda result: (result.metrics.recall, result.metrics.precision))
    print(f"Wrote {args.output}")
    print(f"Best: iou={best.iou:.2f} conf={best.conf:.2f} recall={best.metrics.recall:.3f} precision={best.metrics.precision:.3f}")


if __name__ == "__main__":
    main()
