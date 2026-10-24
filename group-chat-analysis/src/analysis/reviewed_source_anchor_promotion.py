"""Promote canonical source refs from reviewed semantic work into card anchors.

The Atomic Claim and reviewed no-claim registries already contain canonical file/line
source_refs.  When an old Topic Card still reports source_anchor_confidence=none,
those reviewed refs are stronger evidence than re-running fuzzy retrieval.  This
module merges only such reviewed refs into the private verified-source overlay and
never overwrites an existing verified anchor.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from .quality import WORK, sha256_file

DEFAULT_CANDIDATES = WORK / "silver-candidates-v1.json"
DEFAULT_VERIFIED = WORK / "verified-source-anchors-v1.json"
DEFAULT_ATOMIC = WORK / "atomic-claims-reviewed-v1.json"
DEFAULT_NO_CLAIM = WORK / "atomic-claim-no-claim-reviewed-v1.json"


def _segments_from_refs(
    refs: list[dict], expected_date: str
) -> tuple[list[dict], list[str]]:
    """Return same-day card anchors; keep cross-day refs at claim level only."""
    raw: set[tuple[str, int, int]] = set()
    cross_dates: set[str] = set()
    for ref in refs:
        date = str(ref.get("date") or "")
        file = str(ref.get("file") or "")
        try:
            start = int(ref.get("start_line"))
            end = int(ref.get("end_line"))
        except (TypeError, ValueError):
            raise ValueError(f"invalid canonical source ref: {ref}") from None
        if not file or start < 1 or end < start:
            raise ValueError(f"invalid canonical source ref: {ref}")
        if date != expected_date:
            if date:
                cross_dates.add(date)
            continue
        raw.add((file, start, end))

    merged: list[dict] = []
    for file, start, end in sorted(raw):
        if (
            merged
            and merged[-1]["file"] == file
            and start <= merged[-1]["end_line"] + 1
        ):
            merged[-1]["end_line"] = max(merged[-1]["end_line"], end)
        else:
            merged.append({"file": file, "start_line": start, "end_line": end})
    return merged, sorted(cross_dates)


def build_promoted_anchors(
    candidates: dict,
    verified: dict,
    reviewed_atomic: dict,
    reviewed_no_claim: dict,
) -> tuple[dict, dict]:
    result = copy.deepcopy(verified)
    anchors = result.setdefault("anchors", {})

    candidate_map = {
        str(row["card_id"]): row
        for row in candidates.get("candidates", [])
        if row.get("card_id")
    }
    missing_anchor_ids = {
        card_id
        for card_id, row in candidate_map.items()
        if row.get("source_anchor_confidence", "none") == "none"
    }

    refs_by_card: dict[str, list[dict]] = {}
    origins: dict[str, str] = {}
    for row in reviewed_atomic.get("items", []):
        card = str(row.get("card") or "")
        if not card:
            continue
        refs = [
            ref
            for claim in row.get("claims", [])
            for ref in claim.get("source_refs", [])
        ]
        refs_by_card[card] = refs
        origins[card] = "reviewed_atomic_claims"

    for row in reviewed_no_claim.get("cards", []):
        card = str(row.get("card_id") or "")
        if not card:
            continue
        if card in refs_by_card:
            raise ValueError(f"card exists in both reviewed claim and no-claim registries: {card}")
        refs_by_card[card] = list(row.get("source_refs", []))
        origins[card] = "reviewed_no_claim"

    promoted = 0
    no_refs = []
    cross_day_supplemental: dict[str, list[str]] = {}
    already_verified = 0
    reviewed_missing = 0
    for card_id in sorted(missing_anchor_ids):
        if card_id not in refs_by_card:
            continue
        reviewed_missing += 1
        if card_id in anchors:
            already_verified += 1
            continue
        candidate = candidate_map[card_id]
        refs = refs_by_card[card_id]
        if not refs:
            no_refs.append(card_id)
            continue
        date = str(candidate.get("date") or "")
        segments, cross_dates = _segments_from_refs(refs, date)
        if cross_dates:
            cross_day_supplemental[card_id] = cross_dates
        if not segments:
            no_refs.append(card_id)
            continue
        anchors[card_id] = {
            "date": date,
            "segments": segments,
            "verification": {
                "status": "verified",
                "review_batch": "reviewed-canonical-lineage-v1",
                "reviewer": "semantic_review_registry",
                "source": origins[card_id],
                "retrieval_score": None,
                "retrieval_margin": None,
            },
        }
        promoted += 1

    result["schema_version"] = 1
    result["status"] = "verified_backfill"
    result["method"] = "combined_manual_and_reviewed_canonical_lineage"
    result["notes"] = (
        "已有人工核验来源保持不变；新增定位直接来自 reviewed Atomic Claim / "
        "reviewed no-claim 的 canonical source_refs。只补来源血缘，不改变语义、"
        "Silver归属或用户已阅状态。"
    )
    counts = {
        "existing_anchors_before": len(verified.get("anchors", {})),
        "candidate_missing_before": len(missing_anchor_ids),
        "reviewed_missing_candidates": reviewed_missing,
        "promoted_from_reviewed_canonical_refs": promoted,
        "reviewed_missing_without_source_refs": len(no_refs),
        "already_verified": already_verified,
        "anchors_after": len(anchors),
        "candidate_missing_after_promotion": len(missing_anchor_ids) - promoted - already_verified,
    }
    audit = {
        "counts": counts,
        "without_source_refs": no_refs,
        "cross_day_supplemental_refs": cross_day_supplemental,
    }
    return result, audit


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--verified", type=Path, default=DEFAULT_VERIFIED)
    parser.add_argument("--atomic", type=Path, default=DEFAULT_ATOMIC)
    parser.add_argument("--no-claim", type=Path, default=DEFAULT_NO_CLAIM)
    parser.add_argument("--out", type=Path, default=DEFAULT_VERIFIED)
    parser.add_argument(
        "--audit-out",
        type=Path,
        default=WORK / "reviewed-source-anchor-promotion-v1.json",
    )
    args = parser.parse_args()

    result, audit = build_promoted_anchors(
        _load(args.candidates),
        _load(args.verified),
        _load(args.atomic),
        _load(args.no_claim),
    )
    audit["schema_version"] = 1
    audit["status"] = "reviewed_canonical_source_anchor_promotion"
    audit["inputs"] = {
        "candidates": sha256_file(args.candidates),
        "verified_before": sha256_file(args.verified),
        "atomic": sha256_file(args.atomic),
        "no_claim": sha256_file(args.no_claim),
    }
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.audit_out.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": audit["status"],
        "counts": audit["counts"],
        "without_source_refs": audit["without_source_refs"],
        "out": str(args.out),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
