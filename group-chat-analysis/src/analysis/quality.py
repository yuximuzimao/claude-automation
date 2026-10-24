"""只读质量门禁：扫描完整候选索引、Silver 来源覆盖与输入血缘。

结构门禁不宣称证明语义正确。报告仅写 ID/计数/哈希，不复制群聊正文。
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "runtime" / "analysis-work"
CARD_RE = re.compile(r"^##\s+(T-\d{8}-\d+|SUP-[A-Z0-9-]+|AGG-[A-Z0-9-]+)\b", re.M)
KINDS = {"mechanism", "ordered_route", "comparison", "strategy", "sample", "dynamic_signal"}
COVERAGE = {"full", "partial"}
DATE_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_ids(topic_dir: Path) -> set[str]:
    ids: set[str] = set()
    for path in sorted(topic_dir.glob("*.md")):
        ids.update(CARD_RE.findall(path.read_text(encoding="utf-8")))
    return ids


def semantic_coverage_dates(chunks_dir: Path, topic_dir: Path) -> dict:
    """Report Bronze dates that have not entered the Topic candidate layer yet."""
    bronze_dates = sorted(
        path.name for path in chunks_dir.iterdir()
        if path.is_dir() and DATE_NAME_RE.fullmatch(path.name)
    ) if chunks_dir.exists() else []
    topic_dates = sorted(
        path.stem for path in topic_dir.glob("*.md")
        if DATE_NAME_RE.fullmatch(path.stem)
    )
    bronze = set(bronze_dates)
    topics = set(topic_dates)
    return {
        "bronze_dates": bronze_dates,
        "topic_candidate_dates": topic_dates,
        "missing_topic_candidate_dates": sorted(bronze - topics),
        "orphan_topic_candidate_dates": sorted(topics - bronze),
    }


def assess(candidates: dict, silver: dict, known_source_ids: set[str]) -> dict:
    issues: list[dict] = []
    def issue(severity: str, code: str, item: str = "") -> None:
        issues.append({"severity": severity, "code": code, "id": item})

    rows = candidates.get("candidates")
    units = silver.get("units")
    if not isinstance(rows, list) or not isinstance(units, list):
        raise ValueError("candidates and silver units must be arrays")
    seen_cards: set[str] = set()
    seen_units: set[str] = set()
    candidate_map: dict[str, dict] = {}
    all_full: dict[str, set[str]] = collections.defaultdict(set)
    by_card: dict[str, list[dict]] = collections.defaultdict(list)
    state_counts = collections.Counter()
    normalized_state_counts = collections.Counter()
    anchor_counts: collections.Counter[str] = collections.Counter()
    unlinked_full = 0
    anchor_reasons: collections.Counter[str] = collections.Counter()

    for card in rows:
        if not isinstance(card, dict):
            issue("error", "invalid_candidate_type")
            continue
        card_id = card.get("card_id")
        if not isinstance(card_id, str) or not card_id.strip():
            issue("error", "missing_candidate_id")
            continue
        if card_id in seen_cards:
            issue("error", "duplicate_candidate_id", card_id)
        seen_cards.add(card_id)
        candidate_map[card_id] = card
        if not card.get("title") or not card.get("semantic_summary"):
            issue("warning", "incomplete_candidate_context", card_id)
        if not card.get("date"):
            issue("warning", "missing_candidate_date", card_id)
        if card.get("silver_status") not in {"full", "partial", "unabsorbed"}:
            issue("error", "invalid_candidate_status", card_id)
        state_counts[card.get("silver_status", "<missing>")] += 1
        normalized_status = card.get("normalized_status", card.get("silver_status"))
        if normalized_status not in {"full", "partial", "unabsorbed"}:
            issue("error", "invalid_normalized_status", card_id)
        normalized_state_counts[normalized_status or "<missing>"] += 1
        if "source_anchor_confidence" in card:
            confidence = card["source_anchor_confidence"]
            anchor_counts[str(confidence)] += 1
            if confidence == "none":
                anchor_reasons[str(card.get("source_anchor_reason") or "unspecified")] += 1
                if card.get("silver_status") == "full":
                    unlinked_full += 1

    if len(rows) != candidates.get("source_queue_count"):
        issue("error", "candidate_count_mismatch")

    for unit in units:
        if not isinstance(unit, dict):
            issue("error", "invalid_unit_type")
            continue
        uid = unit.get("knowledge_id")
        if not isinstance(uid, str) or not uid.strip():
            issue("error", "missing_unit_id")
            continue
        if uid in seen_units:
            issue("error", "duplicate_unit_id", uid)
        seen_units.add(uid)
        for key in ("subject", "question", "canonical_facts"):
            if not unit.get(key):
                issue("error", "missing_" + key, uid)
        if unit.get("kind") not in KINDS:
            issue("error", "unknown_silver_kind", uid)
        if not isinstance(unit.get("structured"), dict):
            issue("error", "invalid_silver_structure", uid)
        refs = unit.get("evidence_refs")
        if not isinstance(refs, list) or not refs:
            issue("error", "no_silver_evidence", uid)
            continue
        seen_ref: set[str] = set()
        for ref in refs:
            # 早期 Silver 使用 external 描述外部核验；它不是 topic card。
            if not ref.get("card_id") and ref.get("external"):
                if not ref.get("url") and not ref.get("source_id"):
                    issue("warning", "external_source_no_locator", uid)
                continue
            card_id = ref.get("card_id")
            if not isinstance(card_id, str) or not card_id:
                issue("error", "missing_source_ref", uid)
                continue
            if card_id in seen_ref:
                issue("error", "repeated_ref_in_unit", uid + ":" + card_id)
            seen_ref.add(card_id)
            raw_coverage = ref.get("coverage")
            if raw_coverage is None:
                issue("warning", "legacy_implicit_full", uid + ":" + card_id)
            elif raw_coverage not in COVERAGE:
                issue("error", "invalid_coverage", uid + ":" + card_id)
            if card_id not in known_source_ids and card_id not in candidate_map and not card_id.startswith(("SUP-", "AGG-")):
                issue("error", "unknown_source_card", uid + ":" + card_id)
            coverage = ref.get("coverage", "full")
            by_card[card_id].append({"knowledge_id": uid, "coverage": coverage, "role": ref.get("role", "")})
            if coverage == "full":
                all_full[card_id].add(uid)
        if unit.get("initial_state") == "queue" and not any(card_id in candidate_map for card_id in seen_ref):
            issue("warning", "queue_unit_no_current_candidate", uid)

    if anchor_counts.get("none", 0):
        issue("warning", "source_anchors_need_backfill")

    for card_id, owners in all_full.items():
        if len(owners) > 1:
            issue("warning", "multi_unit_full_coverage", card_id)

    for card_id, card in candidate_map.items():
        refs = by_card.get(card_id, [])
        expected = "full" if any(r["coverage"] == "full" for r in refs) else ("partial" if refs else "unabsorbed")
        if card.get("silver_status") != expected:
            issue("error", "coverage_state_mismatch", card_id)
        expected_normalized = "full" if expected == "full" or card.get("dossier_refs") else expected
        if card.get("normalized_status", card.get("silver_status")) != expected_normalized:
            issue("error", "normalized_coverage_state_mismatch", card_id)
        if sorted((r.get("knowledge_id"), r.get("coverage"), r.get("role")) for r in card.get("silver_refs", [])) != sorted(
            (r.get("knowledge_id"), r.get("coverage"), r.get("role")) for r in refs
        ):
            issue("error", "candidate_ref_index_mismatch", card_id)

    return {
        "contract": "analysis-quality-v1",
        "result": "FAIL" if any(i["severity"] == "error" for i in issues) else "PASS_WITH_WARNINGS" if issues else "PASS",
        "counts": {
            "source_candidates": len(rows),
            "candidate_states": dict(sorted(state_counts.items())),
            "normalized_candidate_states": dict(sorted(normalized_state_counts.items())),
            "source_anchor_confidence": dict(sorted(anchor_counts.items())),
            "source_anchor_missing_reasons": dict(sorted(anchor_reasons.items())),
            "full_sources_without_direct_anchor": unlinked_full,
            "silver_units": len(units),
            "silver_distinct_full_sources": len(all_full),
            "source_cards_indexed": len(known_source_ids),
        },
        "quality": {
            "errors": sum(i["severity"] == "error" for i in issues),
            "warnings": sum(i["severity"] == "warning" for i in issues),
            "by_code": dict(sorted(collections.Counter(i["code"] for i in issues).items())),
        },
        "publication": {
            "ready": False,
            "blockers": [
                "未完成独立留出集上的语义合并质量评估",
                *(["存在缺少可靠原文定位的候选"] if anchor_counts.get("none", 0) else []),
                *(["旧来源覆盖字段未显式迁移"] if any(i["code"] == "legacy_implicit_full" for i in issues) else []),
                *(["存在硬性结构错误"] if any(i["severity"] == "error" for i in issues) else []),
            ],
            "reason": "本阶段只运行数据结构扫描；不得据此宣称端到端语义质量达标。",
        },
        "issues": issues,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--candidates", type=Path, default=WORK / "silver-candidates-v1.json")
    p.add_argument("--silver", type=Path, default=WORK / "silver-knowledge-v1.json")
    p.add_argument("--topic-dir", type=Path, default=WORK / "topic-cards-v1")
    p.add_argument("--chunks-dir", type=Path, default=WORK / "full-history-chunks")
    p.add_argument("--corrections", type=Path, default=WORK / "semantic-correction-queue-v1.json")
    p.add_argument("--report", type=Path, default=WORK / "data-quality-baseline-v1.json")
    args = p.parse_args()
    report = assess(
        json.loads(args.candidates.read_text(encoding="utf-8")),
        json.loads(args.silver.read_text(encoding="utf-8")),
        source_ids(args.topic_dir),
    )
    coverage = semantic_coverage_dates(args.chunks_dir, args.topic_dir)
    report["semantic_coverage"] = coverage
    report["counts"]["bronze_dates"] = len(coverage["bronze_dates"])
    report["counts"]["topic_candidate_dates"] = len(coverage["topic_candidate_dates"])
    report["counts"]["missing_topic_candidate_dates"] = len(coverage["missing_topic_candidate_dates"])
    if coverage["missing_topic_candidate_dates"]:
        report["issues"].append({
            "severity": "warning",
            "code": "bronze_dates_missing_topic_candidates",
            "id": ",".join(coverage["missing_topic_candidate_dates"]),
        })
        report["quality"]["warnings"] += 1
        report["quality"]["by_code"]["bronze_dates_missing_topic_candidates"] = 1
        report["quality"]["by_code"] = dict(sorted(report["quality"]["by_code"].items()))
        if report["result"] == "PASS":
            report["result"] = "PASS_WITH_WARNINGS"
        report["publication"]["blockers"].append("存在已完成 Bronze 日包尚未进入 Topic candidate / Atomic claim 语义覆盖")
    if coverage["orphan_topic_candidate_dates"]:
        report["issues"].append({
            "severity": "error",
            "code": "topic_candidate_date_without_bronze_source",
            "id": ",".join(coverage["orphan_topic_candidate_dates"]),
        })
        report["quality"]["errors"] += 1
        report["quality"]["by_code"]["topic_candidate_date_without_bronze_source"] = 1
        report["quality"]["by_code"] = dict(sorted(report["quality"]["by_code"].items()))
        report["result"] = "FAIL"
        report["publication"]["blockers"].append("存在 Topic candidate 日期缺失对应 Bronze 来源")

    correction_count = 0
    correction_total = 0
    correction_resolved = 0
    if args.corrections.exists():
        correction_doc = json.loads(args.corrections.read_text(encoding="utf-8"))
        correction_issues = correction_doc.get("issues", [])
        correction_total = len(correction_issues)
        correction_resolved = sum(
            bool((issue.get("resolution") or {}).get("resolved"))
            for issue in correction_issues
        )
        correction_count = correction_total - correction_resolved
        report["counts"]["semantic_correction_queue"] = correction_count
        report["counts"]["semantic_correction_total"] = correction_total
        report["counts"]["semantic_correction_resolved"] = correction_resolved
        if correction_count:
            report["publication"]["blockers"].append("存在待纠正的语义抽取卡，不得作为自动聚类真值")
    report["inputs"] = {
        "candidates_sha256": sha256_file(args.candidates),
        "silver_sha256": sha256_file(args.silver),
        "semantic_corrections_sha256": sha256_file(args.corrections) if args.corrections.exists() else None,
        "source_inventory": str(args.topic_dir.name),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("result", "counts", "quality")}, ensure_ascii=False))
    return 1 if report["result"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
