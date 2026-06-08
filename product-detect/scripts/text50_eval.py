#!/usr/bin/env python3
"""
Evaluate YOLO-first text correction on the KGOS text50 ground-truth set.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import ocr_verify, nms_sweep


EVALUATED_STATUSES = {"labeled", "auto_labeled"}
SKIPPED_STATUSES = {"pending", "ambiguous"}


def counter_from_items(items: list[dict]) -> Counter:
    counts: Counter = Counter()
    for item in items:
        name = item["name"].strip()
        qty = int(item["qty"])
        if qty > 0:
            counts[name] += qty
    return counts


def exact_match(expected: Counter, predicted: Counter) -> bool:
    return Counter(expected) == Counter(predicted)


def metric_row(exact: int, total: int) -> dict:
    return {
        "exact": exact,
        "total": total,
        "accuracy": exact / total if total else 0.0,
    }


def gated_text_correction(yolo_counts: Counter, text_counts: ocr_verify.TextCounts) -> tuple[Counter, list[str], list[str]]:
    gated = Counter(text_counts.exact)
    unresolved: list[str] = []
    blocked: list[str] = []

    resolved_ambiguous, ambiguous_unresolved = ocr_verify.resolve_supported_text_counts(
        ocr_verify.TextCounts(exact=Counter(), ambiguous=text_counts.ambiguous),
        yolo_counts,
    )
    gated.update(resolved_ambiguous)
    unresolved.extend(ambiguous_unresolved)

    if not text_counts.exact and not text_counts.ambiguous:
        return Counter(yolo_counts), unresolved, blocked

    for name, qty in yolo_counts.items():
        if name not in gated:
            blocked.append(f"{name} {qty}")

    return gated, unresolved, blocked


def evaluate_records(records: dict, yolo_by_image: dict[str, Counter]) -> dict:
    status_counts = {"total": len(records), "labeled": 0, "pending": 0, "ambiguous": 0}
    yolo_exact = 0
    text_exact = 0
    merged_exact = 0
    gated_exact = 0
    evaluated_total = 0
    rows = []

    for image_name in sorted(records):
        record = records[image_name]
        status = record.get("status", "pending")
        if status not in status_counts:
            status_counts[status] = 0
        status_counts[status] += 1

        if status not in EVALUATED_STATUSES:
            rows.append({
                "image": image_name,
                "status": status,
                "expected": {},
                "yolo": dict(yolo_by_image.get(image_name, Counter())),
                "text_only": {},
                "merged": {},
                "gated": {},
                "exact": {"yolo": None, "text": None, "merged": None, "gated": None},
                "unresolved": record.get("unresolved", []),
                "blocked": [],
            })
            continue

        expected = counter_from_items(record.get("items", []))
        yolo_counts = yolo_by_image.get(image_name, Counter())
        text_counts = ocr_verify.parse_text_counts(record.get("text", ""))
        text_only, text_unresolved = ocr_verify.count_text_only(text_counts)
        merged, merged_unresolved = ocr_verify.merge_text_corrections(yolo_counts, text_counts)
        gated, gated_unresolved, blocked = gated_text_correction(yolo_counts, text_counts)

        yolo_ok = exact_match(expected, yolo_counts)
        text_ok = exact_match(expected, text_only)
        merged_ok = exact_match(expected, merged)
        gated_ok = exact_match(expected, gated)
        yolo_exact += int(yolo_ok)
        text_exact += int(text_ok)
        merged_exact += int(merged_ok)
        gated_exact += int(gated_ok)
        evaluated_total += 1

        rows.append({
            "image": image_name,
            "status": status,
            "expected": dict(expected),
            "yolo": dict(yolo_counts),
            "text_only": dict(text_only),
            "merged": dict(merged),
            "gated": dict(gated),
            "exact": {"yolo": yolo_ok, "text": text_ok, "merged": merged_ok, "gated": gated_ok},
            "unresolved": gated_unresolved or record.get("unresolved", []),
            "blocked": blocked,
        })

    return {
        "sample_counts": status_counts,
        "metrics": {
            "yolo": metric_row(yolo_exact, evaluated_total),
            "text": metric_row(text_exact, evaluated_total),
            "merged": metric_row(merged_exact, evaluated_total),
            "gated": metric_row(gated_exact, evaluated_total),
        },
        "rows": rows,
    }


def load_ground_truth(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["images"]


def run_yolo_counts(model_path: Path, image_dir: Path, image_names: list[str], conf: float, iou: float) -> dict[str, Counter]:
    from ultralytics import YOLO

    model = YOLO(str(model_path), task="detect")
    yolo_by_image: dict[str, Counter] = {}
    for image_name in image_names:
        image_path = image_dir / image_name
        if not image_path.exists():
            yolo_by_image[image_name] = Counter()
            continue
        prediction = model(
            str(image_path),
            conf=conf,
            iou=iou,
            imgsz=640,
            device="cpu",
            verbose=False,
        )[0]
        yolo_by_image[image_name] = nms_sweep.count_yolo_result(prediction, model.names)
    return yolo_by_image


def render_report(result: dict, model_path: Path, ground_truth_path: Path, conf: float, iou: float) -> str:
    sample_counts = result["sample_counts"]
    lines = [
        "# Text50 Evaluation Report",
        "",
        f"- Ground truth: `{ground_truth_path}`",
        f"- Model: `{model_path}`",
        f"- conf={conf:.2f}, iou={iou:.2f}",
        "- Policy: pending and ambiguous images are excluded from exact-match accuracy.",
        "- Decision rule: continue only if YOLO+text improves exact-match accuracy and unresolved/false-positive cases are inspectable.",
        "",
        "## Sample Counts",
        "",
        "| total | labeled | pending | ambiguous |",
        "|---:|---:|---:|---:|",
        f"| {sample_counts.get('total', 0)} | {sample_counts.get('labeled', 0)} | "
        f"{sample_counts.get('pending', 0)} | {sample_counts.get('ambiguous', 0)} |",
        "",
        "## Exact Match",
        "",
        "| Mode | Exact | Total | Accuracy |",
        "|---|---:|---:|---:|",
    ]
    for label, key in [
        ("YOLO-only", "yolo"),
        ("text-only", "text"),
        ("YOLO+text", "merged"),
        ("YOLO+text gated", "gated"),
    ]:
        metric = result["metrics"][key]
        lines.append(
            f"| {label} | {metric['exact']} | {metric['total']} | {metric['accuracy']:.3f} |"
        )

    lines.extend([
        "",
        "## Per Image",
        "",
        "| image | status | expected | yolo | text-only | yolo+text | gated | exact | unresolved | blocked |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ])
    for row in result["rows"]:
        lines.append(
            f"| `{row['image']}` | {row['status']} | {row['expected']} | {row['yolo']} | "
            f"{row['text_only']} | {row['merged']} | {row['gated']} | {row['exact']} | "
            f"{row['unresolved']} | {row['blocked']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    root = PROJECT_ROOT
    parser = argparse.ArgumentParser(description="Evaluate text50 YOLO-first text correction")
    _gt_default = root / "docs/text50_ground_truth.json"
    if not _gt_default.exists():
        _gt_default = root / "datasets/kgos_real_text50/ground_truth.json"
    parser.add_argument("--ground-truth", type=Path, default=_gt_default)
    parser.add_argument("--image-dir", type=Path, default=root / "datasets/kgos_real_golden_candidates_v1/images")
    parser.add_argument("--model", type=Path, default=root / "runs/kgos_yolov8s_train7/weights/best.pt")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--iou", type=float, default=0.70)
    parser.add_argument("--output", type=Path, default=root / "docs/text50-evaluation-report.md")
    args = parser.parse_args()

    records = load_ground_truth(args.ground_truth)
    yolo_by_image = run_yolo_counts(
        args.model,
        args.image_dir,
        list(records.keys()),
        conf=args.conf,
        iou=args.iou,
    )
    result = evaluate_records(records, yolo_by_image)
    rendered = render_report(result, args.model, args.ground_truth, args.conf, args.iou)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {args.output}")
    for label, key in [
        ("YOLO-only", "yolo"),
        ("text-only", "text"),
        ("YOLO+text", "merged"),
        ("YOLO+text gated", "gated"),
    ]:
        metric = result["metrics"][key]
        print(f"{label}: exact={metric['exact']}/{metric['total']} accuracy={metric['accuracy']:.3f}")
    print(
        f"Samples: labeled={result['sample_counts'].get('labeled', 0)} "
        f"pending={result['sample_counts'].get('pending', 0)} "
        f"ambiguous={result['sample_counts'].get('ambiguous', 0)}"
    )


if __name__ == "__main__":
    main()
