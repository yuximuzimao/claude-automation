"""Apply reviewed Silver publication decisions into candidate artifacts.

This module never overwrites the formal files by default. It emits a candidate
Silver registry and a candidate source-card index, which must pass quality gates
before promotion.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from .quality import WORK, sha256_file

DEFAULT_GATE = WORK / "silver-publication-gate-reviewed-v1.json"
DEFAULT_AUTHORED = WORK / "silver-draft-authored-registry-v1.json"
DEFAULT_FORMAL = WORK / "silver-knowledge-v1.json"
DEFAULT_CANDIDATES = WORK / "silver-candidates-v1.json"
DEFAULT_OVERRIDES = WORK / "silver-publication-evidence-overrides-v1.json"

# These two updates are deliberately narrower than their existing formal units.
# Preserve the old semantic frame and absorb the new evidence/facts into it.
PRESERVE_OLD_CORE = {
    "K-ACCOUNT-CONTROL-RISK-001",
    "K-DK-FROST-BEGINNER-ROTATION-001",
}


def _dedupe_scalars(values: list) -> list:
    out = []
    seen = set()
    for value in values:
        key = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _merge_evidence(old_refs: list[dict], new_refs: list[dict]) -> list[dict]:
    """One source card per unit; full beats partial, existing role stays stable."""
    by_card: dict[str, dict] = {}
    external = []
    for ref in [*old_refs, *new_refs]:
        if not ref.get("card_id"):
            key = json.dumps(ref, ensure_ascii=False, sort_keys=True)
            if all(json.dumps(x, ensure_ascii=False, sort_keys=True) != key for x in external):
                external.append(copy.deepcopy(ref))
            continue
        card = str(ref["card_id"])
        if card not in by_card:
            by_card[card] = copy.deepcopy(ref)
            continue
        current = by_card[card]
        if current.get("coverage", "full") != "full" and ref.get("coverage", "full") == "full":
            current["coverage"] = "full"
        # Prefer the established role when the card already existed on the formal unit.
    return [by_card[k] for k in sorted(by_card)] + external


def _merge_scope(base: dict, extra: dict) -> dict:
    result = copy.deepcopy(base or {})
    for key, value in (extra or {}).items():
        if key not in result:
            result[key] = copy.deepcopy(value)
        elif result[key] == value:
            continue
        elif key == "time_window":
            # Keep both human-readable windows without pretending to normalize them.
            result[key] = " / ".join(_dedupe_scalars([str(result[key]), str(value)]))
        elif key == "context":
            result[key] = "；".join(_dedupe_scalars([str(result[key]), str(value)]))
        else:
            result[f"additional_{key}"] = copy.deepcopy(value)
    return result


def merge_update(old: dict, new: dict) -> dict:
    target_id = str(old["knowledge_id"])
    core = copy.deepcopy(old if target_id in PRESERVE_OLD_CORE else new)
    other = new if target_id in PRESERVE_OLD_CORE else old
    core["knowledge_id"] = target_id
    core["canonical_facts"] = _dedupe_scalars([
        *old.get("canonical_facts", []),
        *new.get("canonical_facts", []),
    ])
    core["evidence_refs"] = _merge_evidence(
        old.get("evidence_refs", []),
        new.get("evidence_refs", []),
    )
    core["search_terms"] = _dedupe_scalars([
        *old.get("search_terms", []),
        *new.get("search_terms", []),
    ])
    core["topics"] = _dedupe_scalars([
        *old.get("topics", []),
        *new.get("topics", []),
    ])
    core["scope"] = _merge_scope(core.get("scope", {}), other.get("scope", {}))
    # Initial queue state remains appropriate for newly expanded knowledge.
    core["initial_state"] = "queue"
    return core


def apply_coverage_overrides(silver: dict, overrides: dict | None) -> int:
    if not overrides:
        return 0
    if overrides.get("status") != "reviewed_silver_publication_evidence_overrides":
        raise ValueError("unexpected evidence override status")
    units = {str(unit["knowledge_id"]): unit for unit in silver.get("units", [])}
    applied = 0
    seen: set[tuple[str, str]] = set()
    for row in overrides.get("items", []):
        kid = str(row.get("knowledge_id") or "")
        card = str(row.get("card_id") or "")
        coverage = str(row.get("coverage") or "")
        key = (kid, card)
        if not kid or not card or coverage not in {"full", "partial"}:
            raise ValueError(f"invalid evidence coverage override: {row}")
        if key in seen:
            raise ValueError(f"duplicate evidence coverage override: {kid}: {card}")
        seen.add(key)
        if kid not in units:
            raise ValueError(f"coverage override references unknown Silver unit: {kid}")
        matches = [
            ref for ref in units[kid].get("evidence_refs", [])
            if ref.get("card_id") == card
        ]
        if len(matches) != 1:
            raise ValueError(
                f"coverage override requires exactly one evidence ref: {kid}: {card}: {len(matches)}"
            )
        matches[0]["coverage"] = coverage
        applied += 1
    return applied


def rebuild_candidate_index(candidates: dict, silver: dict) -> dict:
    result = copy.deepcopy(candidates)
    candidate_map = {
        str(row.get("card_id") or ""): row
        for row in result.get("candidates", [])
        if row.get("card_id")
    }
    refs_by_card: dict[str, list[dict]] = {card: [] for card in candidate_map}

    for unit in silver.get("units", []):
        kid = str(unit.get("knowledge_id") or "")
        for ref in unit.get("evidence_refs", []):
            card = ref.get("card_id")
            if not card:
                continue
            card = str(card)
            if card not in candidate_map:
                # Legacy formal Silver can reference source cards that are valid in
                # the topic-card inventory but predate the current candidate index.
                # They remain on the Silver unit; there is simply no candidate row
                # to receive a reverse silver_refs entry.
                continue
            refs_by_card[card].append({
                "knowledge_id": kid,
                "coverage": ref.get("coverage", "full"),
                "role": ref.get("role", ""),
            })

    for card, row in candidate_map.items():
        refs = sorted(
            refs_by_card[card],
            key=lambda x: (x["knowledge_id"], x["coverage"], x["role"]),
        )
        row["silver_refs"] = refs
        status = (
            "full" if any(ref["coverage"] == "full" for ref in refs)
            else "partial" if refs
            else "unabsorbed"
        )
        row["silver_status"] = status
        row["normalized_status"] = (
            "full" if status == "full" or row.get("dossier_refs") else status
        )

    result["source_queue_count"] = len(result.get("candidates", []))
    return result


def build_publication_candidate(
    formal: dict,
    authored: dict,
    gate: dict,
    candidates: dict,
    coverage_overrides: dict | None = None,
) -> tuple[dict, dict, dict]:
    if gate.get("status") != "reviewed_silver_publication_gate_not_applied":
        raise ValueError("publication gate is not complete/reviewed")
    counts = gate.get("counts", {})
    if int(counts.get("active_work_items", -1)) != 0:
        raise ValueError("publication gate still has active work items")

    authored_map = {
        str((row.get("lineage") or {}).get("group_id") or row.get("group_id") or ""): row["unit"]
        for row in authored.get("items", [])
    }
    candidate_ids = {
        str(row.get("card_id") or "")
        for row in candidates.get("candidates", [])
        if row.get("card_id")
    }
    for gid, unit in authored_map.items():
        for ref in unit.get("evidence_refs", []):
            card = ref.get("card_id")
            if card and str(card) not in candidate_ids:
                raise ValueError(f"authored draft references unindexed candidate card: {gid}: {card}")

    formal_units = [copy.deepcopy(x) for x in formal.get("units", [])]
    formal_by_id = {str(x["knowledge_id"]): i for i, x in enumerate(formal_units)}
    if len(formal_by_id) != len(formal_units):
        raise ValueError("formal Silver has duplicate knowledge ids")

    append_count = update_count = hold_count = 0
    update_targets: set[str] = set()
    for decision in gate.get("items", []):
        gid = str(decision["group_id"])
        if gid not in authored_map:
            raise ValueError(f"missing authored unit for gate group: {gid}")
        action = decision["decision"]
        draft = copy.deepcopy(authored_map[gid])
        if action == "append_new":
            kid = str(draft["knowledge_id"])
            if kid in formal_by_id:
                raise ValueError(f"append_new collides with formal knowledge id: {kid}")
            formal_by_id[kid] = len(formal_units)
            formal_units.append(draft)
            append_count += 1
        elif action == "update_existing":
            target = str(decision.get("target_knowledge_id") or "")
            if target not in formal_by_id:
                raise ValueError(f"update target missing from formal Silver: {target}")
            if target in update_targets:
                raise ValueError(f"formal Silver target updated twice: {target}")
            idx = formal_by_id[target]
            formal_units[idx] = merge_update(formal_units[idx], draft)
            update_targets.add(target)
            update_count += 1
        elif action == "hold":
            hold_count += 1
        else:
            raise ValueError(f"unsupported publication action: {action}")

    expected = {
        "append_new": int(counts.get("append_new", -1)),
        "update_existing": int(counts.get("update_existing", -1)),
        "hold": int(counts.get("hold", -1)),
    }
    actual = {
        "append_new": append_count,
        "update_existing": update_count,
        "hold": hold_count,
    }
    if actual != expected:
        raise ValueError(f"publication decision count mismatch: expected={expected} actual={actual}")

    result = copy.deepcopy(formal)
    result["units"] = formal_units

    # Expand source window from all referenced indexed cards.
    date_map = {
        str(row.get("card_id")): row.get("date")
        for row in candidates.get("candidates", [])
        if row.get("card_id") and row.get("date")
    }
    dates = sorted({
        str(date_map[ref["card_id"]])
        for unit in formal_units
        for ref in unit.get("evidence_refs", [])
        if ref.get("card_id") in date_map
    })
    if dates:
        result["source_window"] = f"{dates[0]}..{dates[-1]}"

    coverage_override_count = apply_coverage_overrides(result, coverage_overrides)
    rebuilt_candidates = rebuild_candidate_index(candidates, result)
    report = {
        "schema_version": 1,
        "status": "silver_publication_candidate_not_promoted",
        "counts": {
            "formal_units_before": len(formal.get("units", [])),
            "append_new": append_count,
            "update_existing": update_count,
            "hold": hold_count,
            "coverage_overrides": coverage_override_count,
            "formal_units_after": len(formal_units),
            "candidate_cards": len(rebuilt_candidates.get("candidates", [])),
            "candidate_full": sum(x.get("silver_status") == "full" for x in rebuilt_candidates.get("candidates", [])),
            "candidate_partial": sum(x.get("silver_status") == "partial" for x in rebuilt_candidates.get("candidates", [])),
            "candidate_unabsorbed": sum(x.get("silver_status") == "unabsorbed" for x in rebuilt_candidates.get("candidates", [])),
        },
        "updated_targets": sorted(update_targets),
    }
    return result, rebuilt_candidates, report


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--gate", type=Path, default=DEFAULT_GATE)
    p.add_argument("--authored", type=Path, default=DEFAULT_AUTHORED)
    p.add_argument("--formal", type=Path, default=DEFAULT_FORMAL)
    p.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    p.add_argument("--coverage-overrides", type=Path, default=DEFAULT_OVERRIDES)
    p.add_argument(
        "--silver-out",
        type=Path,
        default=WORK / "silver-knowledge-publication-candidate-v1.json",
    )
    p.add_argument(
        "--candidates-out",
        type=Path,
        default=WORK / "silver-candidates-publication-candidate-v1.json",
    )
    p.add_argument(
        "--report",
        type=Path,
        default=WORK / "silver-publication-apply-report-v1.json",
    )
    args = p.parse_args()

    formal = json.loads(args.formal.read_text(encoding="utf-8"))
    authored = json.loads(args.authored.read_text(encoding="utf-8"))
    gate = json.loads(args.gate.read_text(encoding="utf-8"))
    candidates = json.loads(args.candidates.read_text(encoding="utf-8"))
    overrides = (
        json.loads(args.coverage_overrides.read_text(encoding="utf-8"))
        if args.coverage_overrides.exists()
        else None
    )
    silver_out, candidates_out, report = build_publication_candidate(
        formal, authored, gate, candidates, overrides
    )
    report["inputs"] = {
        "gate_sha256": sha256_file(args.gate),
        "authored_sha256": sha256_file(args.authored),
        "formal_sha256": sha256_file(args.formal),
        "candidates_sha256": sha256_file(args.candidates),
        "coverage_overrides_sha256": sha256_file(args.coverage_overrides) if args.coverage_overrides.exists() else None,
    }
    args.silver_out.write_text(json.dumps(silver_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.candidates_out.write_text(json.dumps(candidates_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["outputs"] = {
        "silver_sha256": sha256_file(args.silver_out),
        "candidates_sha256": sha256_file(args.candidates_out),
    }
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
