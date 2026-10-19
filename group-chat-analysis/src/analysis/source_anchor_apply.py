"""Promote semantically reviewed source-anchor proposals into verified overlay."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .quality import WORK

DEFAULT_PROPOSALS = WORK / "source-anchor-backfill-proposals-v1.json"
DEFAULT_DECISIONS = WORK / "source-anchor-review-decisions-v1.json"
DEFAULT_VERIFIED = WORK / "verified-source-anchors-v1.json"
SOURCE_DIR = WORK / "full-history-chunks"


def validate_segments(date: str, segments: list[dict]) -> None:
    if not segments:
        raise ValueError("verified anchor must have segments")
    for seg in segments:
        path = SOURCE_DIR / date / seg["file"]
        if not path.exists():
            raise ValueError(f"source file missing: {path}")
        line_count = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        start, end = int(seg["start_line"]), int(seg["end_line"])
        if start < 1 or end < start or end > line_count:
            raise ValueError(f"invalid source range {path}:{start}-{end}")


def apply_reviews(proposals: dict, decisions: dict, verified: dict) -> tuple[dict, int]:
    proposal_map = {x["card_id"]: x for x in proposals.get("proposals", [])}
    anchors = dict(verified.get("anchors", {}))
    added = 0
    for card_id, decision in decisions.get("decisions", {}).items():
        if decision.get("status") != "verified":
            continue
        item = proposal_map.get(card_id)
        if not item:
            raise ValueError(f"reviewed card missing from current proposals: {card_id}")
        if not item.get("candidates"):
            raise ValueError(f"reviewed card has no candidate source: {card_id}")
        top = item["candidates"][0]
        date = item["date"]
        # Semantic review may narrow/expand the retrieval window to exact supporting lines,
        # or combine multiple same-day evidence segments. Retrieval is recall, not truth.
        segments = decision.get("segments_override") or top["segments"]
        validate_segments(date, segments)
        proposed = {
            "date": date,
            "segments": segments,
            "verification": {
                "status": "verified",
                "review_batch": decisions.get("review_batch", ""),
                "reviewer": decision.get("reviewer", ""),
                "retrieval_score": top.get("score"),
                "retrieval_margin": top.get("margin_from_second"),
            },
        }
        if card_id in anchors:
            existing = anchors[card_id]
            if existing.get("date") != proposed["date"] or existing.get("segments") != proposed["segments"]:
                raise ValueError(f"refuse to overwrite different verified anchor: {card_id}")
            continue
        anchors[card_id] = proposed
        added += 1
    output = dict(verified)
    output["schema_version"] = max(1, int(output.get("schema_version", 1)))
    output["status"] = "verified_backfill"
    output["anchors"] = dict(sorted(anchors.items()))
    output["verified_count"] = len(output["anchors"])
    return output, added


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--proposals", type=Path, default=DEFAULT_PROPOSALS)
    p.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    p.add_argument("--verified", type=Path, default=DEFAULT_VERIFIED)
    args = p.parse_args()
    proposals = json.loads(args.proposals.read_text(encoding="utf-8"))
    decisions = json.loads(args.decisions.read_text(encoding="utf-8"))
    verified = json.loads(args.verified.read_text(encoding="utf-8")) if args.verified.exists() else {"schema_version": 1, "anchors": {}}
    output, added = apply_reviews(proposals, decisions, verified)
    args.verified.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"added": added, "verified_count": output["verified_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
