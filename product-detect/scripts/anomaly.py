#!/usr/bin/env python3
"""
Anomaly detection for KGOS YOLO+text product recognition pipeline.

Formalises the gating logic from text50_eval.py into typed anomaly reports.
Each Anomaly records a reason, severity, and whether LLM escalation is needed.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import ocr_verify


class AnomalyType(str, Enum):
    YOLO_EXTRA_NOT_IN_TEXT = "YOLO_EXTRA_NOT_IN_TEXT"
    TEXT_UNRESOLVED = "TEXT_UNRESOLVED"
    NO_VISUAL_SUBTYPE_SUPPORT = "NO_VISUAL_SUBTYPE_SUPPORT"
    NO_OCR_SIGNAL = "NO_OCR_SIGNAL"
    COUNT_MISMATCH = "COUNT_MISMATCH"


class Severity(str, Enum):
    INFO = "info"
    WARN = "warn"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Anomaly:
    type: AnomalyType
    severity: Severity
    message: str
    product: str = ""
    yolo_qty: int = 0
    text_qty: int = 0

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "severity": self.severity.value,
            "message": self.message,
            "product": self.product,
            "yolo_qty": self.yolo_qty,
            "text_qty": self.text_qty,
        }


@dataclass
class AnomalyReport:
    image: str
    yolo_counts: Counter
    text_counts: ocr_verify.TextCounts
    anomalies: list[Anomaly] = field(default_factory=list)

    @property
    def needs_escalation(self) -> bool:
        return any(a.severity in (Severity.HIGH, Severity.CRITICAL) for a in self.anomalies)

    @property
    def has_no_ocr(self) -> bool:
        return any(a.type == AnomalyType.NO_OCR_SIGNAL for a in self.anomalies)

    def to_dict(self) -> dict:
        return {
            "image": self.image,
            "anomalies": [a.to_dict() for a in self.anomalies],
            "needs_escalation": self.needs_escalation,
        }

    def to_llm_prompt(self) -> str:
        lines = [
            f"图片: {self.image}",
            f"YOLO 检测结果: {dict(self.yolo_counts)}",
            "异常信号:",
        ]
        for a in self.anomalies:
            lines.append(f"  [{a.severity.upper()}] {a.type.value}: {a.message}")
        lines.append(
            "\n请逐类列出图中每种商品的名称和数量，"
            "格式：[{\"name\": \"ERP标准商品名\", \"qty\": N}, ...]"
        )
        return "\n".join(lines)


def detect(
    image: str,
    yolo_counts: Counter,
    text_counts: ocr_verify.TextCounts,
    *,
    mismatch_threshold: float = 0.30,
) -> AnomalyReport:
    """Return an AnomalyReport for one image inference result."""
    report = AnomalyReport(image=image, yolo_counts=yolo_counts, text_counts=text_counts)
    anomalies = report.anomalies

    has_text = bool(text_counts.exact or text_counts.ambiguous)

    if not has_text:
        anomalies.append(Anomaly(
            type=AnomalyType.NO_OCR_SIGNAL,
            severity=Severity.HIGH,
            message="图片无可解析文字，无法进行文字交叉验证",
        ))

    resolved_from_text, unresolved_items = ocr_verify.resolve_supported_text_counts(
        text_counts, yolo_counts
    )

    for unresolved in unresolved_items:
        parts = unresolved.rsplit(" ", 1)
        name = parts[0] if len(parts) > 1 else unresolved
        qty = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0

        in_ambiguous = name in ocr_verify.ambiguous_groups()
        anomaly_type = (
            AnomalyType.NO_VISUAL_SUBTYPE_SUPPORT if in_ambiguous else AnomalyType.TEXT_UNRESOLVED
        )
        anomalies.append(Anomaly(
            type=anomaly_type,
            severity=Severity.HIGH,
            message=f"文字提到 '{name}' 但 YOLO 无对应子品支持，无法落到 ERP 标准名",
            product=name,
            text_qty=qty,
        ))

    all_text_products = set(text_counts.exact) | set(resolved_from_text)
    for name, qty in yolo_counts.items():
        if has_text and name not in all_text_products:
            anomalies.append(Anomaly(
                type=AnomalyType.YOLO_EXTRA_NOT_IN_TEXT,
                severity=Severity.WARN,
                message=f"YOLO 检出 '{name}'×{qty} 但文字中无对应记录，可能误检",
                product=name,
                yolo_qty=qty,
            ))

    for name, text_qty in text_counts.exact.items():
        yolo_qty = yolo_counts.get(name, 0)
        if yolo_qty > 0:
            ratio = abs(yolo_qty - text_qty) / max(yolo_qty, text_qty)
            if ratio > mismatch_threshold:
                anomalies.append(Anomaly(
                    type=AnomalyType.COUNT_MISMATCH,
                    severity=Severity.WARN,
                    message=f"'{name}': YOLO={yolo_qty} 文字={text_qty}，差异 {ratio:.0%}",
                    product=name,
                    yolo_qty=yolo_qty,
                    text_qty=text_qty,
                ))

    return report


def detect_batch(records: list[dict], yolo_by_image: dict[str, Counter]) -> list[AnomalyReport]:
    reports = []
    for record in records:
        image = record["image"]
        text = record.get("text", "")
        text_counts = ocr_verify.parse_text_counts(text)
        yolo = yolo_by_image.get(image, Counter())
        reports.append(detect(image, yolo, text_counts))
    return reports


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run anomaly detection on text50 records")
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=PROJECT_ROOT / "docs/text50_ground_truth.json",
    )
    args = parser.parse_args()

    gt_path = args.ground_truth
    if not gt_path.exists():
        gt_path = PROJECT_ROOT / "datasets/kgos_real_text50/ground_truth.json"

    raw = json.loads(gt_path.read_text(encoding="utf-8"))
    records = raw["images"] if "images" in raw else raw
    escalation_count = 0
    for image_name, record in records.items():
        text = record.get("text", "")
        text_counts = ocr_verify.parse_text_counts(text)
        yolo_counts = Counter()
        report = detect(image_name, yolo_counts, text_counts)
        if report.needs_escalation:
            escalation_count += 1
            print(f"[ESCALATE] {image_name}:")
            for a in report.anomalies:
                if a.severity in (Severity.HIGH, Severity.CRITICAL):
                    print(f"  {a.type.value}: {a.message}")

    print(f"\n需要升级处理: {escalation_count}/{len(records)} 张")
