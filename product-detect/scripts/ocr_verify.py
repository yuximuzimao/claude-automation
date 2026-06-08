#!/usr/bin/env python3
"""
Text-correction evaluation for KGOS dense product recognition.

This script is evaluation-only. YOLO detections remain the source for concrete
flavor/spec identity; text can correct counts only when the concrete item is
exact or already supported by YOLO detections.
"""

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import nms_sweep


ALIAS_PATH = PROJECT_ROOT / "data/kgos_text_aliases.json"


@dataclass(frozen=True)
class TextCounts:
    exact: Counter
    ambiguous: Counter


@lru_cache(maxsize=1)
def load_text_aliases() -> dict:
    data = json.loads(ALIAS_PATH.read_text(encoding="utf-8"))
    return {
        "exact_aliases": {
            normalize_text_name(alias): erp_name
            for alias, erp_name in data.get("exact_aliases", {}).items()
        },
        "ambiguous_groups": {
            normalize_text_name(alias): tuple(candidates)
            for alias, candidates in data.get("ambiguous_groups", {}).items()
        },
    }


def exact_aliases() -> dict[str, str]:
    return load_text_aliases()["exact_aliases"]


def ambiguous_groups() -> dict[str, tuple[str, ...]]:
    return load_text_aliases()["ambiguous_groups"]


def normalize_text_name(raw: str) -> str:
    text = re.sub(r"（.*?）", "", raw)
    text = re.sub(r"\(.*?\)", "", text)
    return text.strip()


def split_text_items(text: str) -> list[str]:
    normalized = text.replace("，", "+").replace(",", "+").replace("、", "+")
    return [part.strip() for part in normalized.split("+") if part.strip()]


def parse_text_counts(text: str) -> TextCounts:
    exact: Counter = Counter()
    ambiguous: Counter = Counter()

    for part in split_text_items(text):
        clean = normalize_text_name(part)
        match = re.match(r"(.+?)\s*(?:[xX×*]\s*)?(\d+)\s*(?:包|件|盒|个|袋)?$", clean)
        if not match:
            continue
        name, qty_text = match.groups()
        name = normalize_text_name(name)
        qty = int(qty_text)

        aliases = exact_aliases()
        groups = ambiguous_groups()

        if name in groups:
            ambiguous[name] += qty
            continue

        standard = aliases.get(name, nms_sweep.standard_name(name))
        if standard != name:
            exact[standard] += qty

    return TextCounts(exact=exact, ambiguous=ambiguous)


def distribute_count(total: int, detected_counts: Counter, candidates: list[str]) -> Counter:
    if not candidates:
        return Counter()
    if total % len(candidates) == 0:
        each = total // len(candidates)
        return Counter({candidate: each for candidate in candidates})

    detected_total = sum(detected_counts[candidate] for candidate in candidates)
    if detected_total <= 0:
        return Counter()

    base: Counter = Counter()
    remainders: list[tuple[float, str]] = []
    assigned = 0
    for candidate in candidates:
        raw = total * detected_counts[candidate] / detected_total
        whole = int(raw)
        base[candidate] = whole
        assigned += whole
        remainders.append((raw - whole, candidate))

    for _, candidate in sorted(remainders, reverse=True)[: total - assigned]:
        base[candidate] += 1
    return base


def resolve_supported_text_counts(text_counts: TextCounts, support_counts: Counter) -> tuple[Counter, list[str]]:
    resolved = Counter(text_counts.exact)
    unresolved: list[str] = []

    for group_name, qty in text_counts.ambiguous.items():
        group_candidates = list(ambiguous_groups()[group_name])
        supported_candidates = [
            candidate for candidate in group_candidates
            if support_counts.get(candidate, 0) > 0
        ]
        if not supported_candidates:
            unresolved.append(f"{group_name} {qty}")
            continue
        if len(supported_candidates) > 1 and qty % len(supported_candidates) != 0:
            unresolved.append(f"{group_name} {qty}")
            continue
        resolved.update(distribute_count(qty, support_counts, supported_candidates))

    return resolved, unresolved


def merge_text_corrections(yolo_counts: Counter, text_counts: TextCounts) -> tuple[Counter, list[str]]:
    merged = Counter(yolo_counts)
    unresolved: list[str] = []

    for name, qty in text_counts.exact.items():
        if merged[name] < qty:
            merged[name] = qty

    for group_name, qty in text_counts.ambiguous.items():
        group_candidates = list(ambiguous_groups()[group_name])
        resolved, group_unresolved = resolve_supported_text_counts(
            TextCounts(exact=Counter(), ambiguous=Counter({group_name: qty})),
            yolo_counts,
        )
        if group_unresolved:
            unresolved.append(f"{group_name} {qty}")
            continue

        for candidate in group_candidates:
            if candidate in resolved:
                merged[candidate] = resolved[candidate]

    return merged, unresolved


def parse_visible_caption_rows(report_text: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in report_text.splitlines():
        if not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        image_name = cells[0].strip("`")
        if image_name.lower().endswith((".jpg", ".jpeg", ".png")):
            rows[image_name] = cells[1]
    return rows


def count_text_only(text_counts: TextCounts) -> tuple[Counter, list[str]]:
    return merge_text_corrections(Counter(), text_counts)


def evaluate_items(model_path: Path, items: list[dict], text_by_image: dict[str, str], conf: float, iou: float) -> dict:
    from ultralytics import YOLO

    model = YOLO(str(model_path), task="detect")
    expected_total: Counter = Counter()
    yolo_total: Counter = Counter()
    text_total: Counter = Counter()
    merged_total: Counter = Counter()
    rows = []

    for item in items:
        image_name = item["image"].name
        prediction = model(
            str(item["image"]),
            conf=conf,
            iou=iou,
            imgsz=640,
            device="cpu",
            verbose=False,
        )[0]
        yolo_counts = nms_sweep.count_yolo_result(prediction, model.names)
        text_counts = parse_text_counts(text_by_image.get(image_name, ""))
        expected, expected_unresolved = resolve_supported_text_counts(text_counts, yolo_counts)
        if not expected:
            expected = item["expected"]
        text_only, text_unresolved = count_text_only(text_counts)
        merged, merged_unresolved = merge_text_corrections(yolo_counts, text_counts)

        expected_total.update(expected)
        yolo_total.update(yolo_counts)
        text_total.update(text_only)
        merged_total.update(merged)
        rows.append({
            "image": image_name,
            "expected": dict(expected),
            "yolo": dict(yolo_counts),
            "text_only": dict(text_only),
            "merged": dict(merged),
            "expected_unresolved": expected_unresolved,
            "text_unresolved": text_unresolved,
            "merged_unresolved": merged_unresolved,
        })

    return {
        "metrics": {
            "yolo": nms_sweep.compare_counts(expected_total, yolo_total),
            "text": nms_sweep.compare_counts(expected_total, text_total),
            "merged": nms_sweep.compare_counts(expected_total, merged_total),
        },
        "rows": rows,
    }


def render_report(result: dict, model_path: Path, conf: float, iou: float) -> str:
    lines = [
        "# Text Correction Gift13 Report",
        "",
        f"- Model: `{model_path}`",
        f"- conf={conf:.2f}, iou={iou:.2f}",
        "- Policy: YOLO decides concrete flavor/spec identity; text only corrects counts.",
        "- Ambiguous text without YOLO subtype evidence is listed as unresolved.",
        "- Expected counts are caption-derived and resolved with YOLO subtype support for this trial; unresolved caption parts are not final golden truth.",
        "",
        "## Summary",
        "",
        "| Mode | Expected | Detected | Correct | Recall | Precision |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, key in [("YOLO-only", "yolo"), ("text-only", "text"), ("YOLO+text", "merged")]:
        metrics = result["metrics"][key]
        lines.append(
            f"| {label} | {metrics.total_expected} | {metrics.total_detected} | "
            f"{metrics.total_correct} | {metrics.recall:.3f} | {metrics.precision:.3f} |"
        )

    lines.extend([
        "",
        "## Per Image",
        "",
        "| image | expected | yolo | text-only | yolo+text | expected unresolved | merge unresolved |",
        "|---|---|---|---|---|---|---|",
    ])
    for row in result["rows"]:
        lines.append(
            f"| `{row['image']}` | {row['expected']} | {row['yolo']} | "
            f"{row['text_only']} | {row['merged']} | "
            f"{row['expected_unresolved']} | {row['merged_unresolved']} |"
        )
    lines.append("")
    return "\n".join(lines)


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> None:
    root = project_root()
    parser = argparse.ArgumentParser(description="Evaluate YOLO-first text correction on KGOS gift13")
    parser.add_argument("--model", type=Path, default=root / "runs/kgos_yolov8s_train7/weights/best.pt")
    parser.add_argument("--gift-images", type=Path, default=root / "datasets/kgos_real_golden_gift13/images")
    parser.add_argument("--caption-report", type=Path, default=root / "docs/real-golden-gift13-train6-report.md")
    parser.add_argument("--business-data", type=Path, default=root / "datasets/kgos_business_val/data.yaml")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--iou", type=float, default=0.70)
    parser.add_argument("--output", type=Path, default=root / "docs/text-correction-gift13-report.md")
    args = parser.parse_args()

    report_text = args.caption_report.read_text(encoding="utf-8")
    text_by_image = parse_visible_caption_rows(report_text)
    items = nms_sweep.load_eval_items(
        gift_images_dir=args.gift_images,
        gift_report=args.caption_report,
        business_data_yaml=args.business_data,
        business_sample_size=0,
        seed=42,
    )
    result = evaluate_items(args.model, items, text_by_image, conf=args.conf, iou=args.iou)
    rendered = render_report(result, args.model, args.conf, args.iou)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {args.output}")
    for label, key in [("YOLO-only", "yolo"), ("text-only", "text"), ("YOLO+text", "merged")]:
        metrics = result["metrics"][key]
        print(
            f"{label}: recall={metrics.recall:.3f} precision={metrics.precision:.3f} "
            f"correct={metrics.total_correct}/{metrics.total_expected}"
        )


if __name__ == "__main__":
    main()
