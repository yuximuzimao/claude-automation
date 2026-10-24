"""Apply reviewed coverage decisions to legacy Silver evidence refs.

Legacy Silver units predated the explicit full|partial coverage field. This module
only migrates refs that currently omit coverage and requires a one-for-one reviewed
decision set, so a future schema cleanup cannot silently invent "full".
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from .quality import WORK, sha256_file

DEFAULT_SILVER = WORK / "silver-knowledge-v1.json"
DEFAULT_REVIEW = WORK / "legacy-silver-coverage-reviewed-v1.json"
DEFAULT_AUDIT = WORK / "legacy-silver-coverage-apply-v1.json"


def apply_reviewed_legacy_coverage(silver: dict, review: dict) -> tuple[dict, dict]:
    if review.get("status") != "reviewed_legacy_silver_coverage":
        raise ValueError("unexpected legacy Silver coverage review status")

    result = copy.deepcopy(silver)
    units = {str(u.get("knowledge_id") or ""): u for u in result.get("units", [])}

    missing: set[tuple[str, str]] = set()
    for kid, unit in units.items():
        for ref in unit.get("evidence_refs", []):
            card = ref.get("card_id")
            if card and "coverage" not in ref:
                missing.add((kid, str(card)))

    decisions: dict[tuple[str, str], dict] = {}
    for row in review.get("items", []):
        kid = str(row.get("knowledge_id") or "")
        card = str(row.get("card_id") or "")
        coverage = str(row.get("coverage") or "")
        key = (kid, card)
        if not kid or not card or coverage not in {"full", "partial"}:
            raise ValueError(f"invalid legacy coverage decision: {row}")
        if key in decisions:
            raise ValueError(f"duplicate legacy coverage decision: {kid}: {card}")
        decisions[key] = row

    missing_decisions = sorted(missing - set(decisions))
    stale_decisions = sorted(set(decisions) - missing)
    if missing_decisions:
        raise ValueError(
            f"legacy coverage refs missing reviewed decisions: {missing_decisions[:10]}"
        )
    if stale_decisions:
        raise ValueError(
            f"review contains refs that are not legacy-missing coverage: {stale_decisions[:10]}"
        )

    applied = 0
    by_coverage = {"full": 0, "partial": 0}
    for kid, card in sorted(missing):
        unit = units[kid]
        matches = [
            ref
            for ref in unit.get("evidence_refs", [])
            if str(ref.get("card_id") or "") == card
        ]
        if len(matches) != 1:
            raise ValueError(
                f"legacy coverage requires exactly one evidence ref: {kid}: {card}: {len(matches)}"
            )
        coverage = str(decisions[(kid, card)]["coverage"])
        matches[0]["coverage"] = coverage
        applied += 1
        by_coverage[coverage] += 1

    remaining = [
        (str(unit.get("knowledge_id") or ""), str(ref.get("card_id") or ""))
        for unit in result.get("units", [])
        for ref in unit.get("evidence_refs", [])
        if ref.get("card_id") and "coverage" not in ref
    ]
    if remaining:
        raise ValueError(f"legacy coverage remains after apply: {remaining[:10]}")

    audit = {
        "schema_version": 1,
        "status": "legacy_silver_coverage_applied",
        "counts": {
            "legacy_refs_before": len(missing),
            "reviewed_decisions": len(decisions),
            "applied": applied,
            "full": by_coverage["full"],
            "partial": by_coverage["partial"],
            "legacy_refs_after": len(remaining),
        },
    }
    return result, audit


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--silver", type=Path, default=DEFAULT_SILVER)
    p.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    p.add_argument("--out", type=Path, default=DEFAULT_SILVER)
    p.add_argument("--audit-out", type=Path, default=DEFAULT_AUDIT)
    args = p.parse_args()

    source = _load(args.silver)
    review = _load(args.review)
    result, audit = apply_reviewed_legacy_coverage(source, review)
    audit["inputs"] = {
        "silver_before_sha256": sha256_file(args.silver),
        "review_sha256": sha256_file(args.review),
    }
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    audit["output_sha256"] = sha256_file(args.out)
    args.audit_out.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    main()
