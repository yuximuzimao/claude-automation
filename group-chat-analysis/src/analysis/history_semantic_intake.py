"""Build an incremental semantic-intake manifest for Bronze dates missing Topic Cards.

This is a staging/coverage tool only. It never marks a date semantically complete and
never writes into topic-cards-v1. A date becomes covered only after full review and
explicit promotion of its complete Topic Card file.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .quality import WORK, DATE_NAME_RE, sha256_file

HEADER_COUNT_RE = re.compile(r"^message_count:\s*(\d+)\s*$", re.M)


def build_manifest(chunks_dir: Path, topic_dir: Path, previous: dict | None = None) -> dict:
    previous_by_date = {
        row["date"]: row
        for row in (previous or {}).get("dates", [])
        if isinstance(row, dict) and row.get("date")
    }
    bronze_dates = sorted(
        p.name for p in chunks_dir.iterdir()
        if p.is_dir() and DATE_NAME_RE.fullmatch(p.name)
    )
    topic_dates = {
        p.stem for p in topic_dir.glob("*.md")
        if DATE_NAME_RE.fullmatch(p.stem)
    }

    rows = []
    for day in bronze_dates:
        if day in topic_dates:
            continue
        parts = sorted((chunks_dir / day).glob("part-*.md"))
        if not parts:
            raise ValueError(f"Bronze date has no history chunks: {day}")
        first = parts[0].read_text(encoding="utf-8")
        m = HEADER_COUNT_RE.search(first)
        message_count = int(m.group(1)) if m else None
        old = previous_by_date.get(day, {})
        status = old.get("status", "pending")
        if status not in {"pending", "in_progress", "review_complete"}:
            status = "pending"
        rows.append({
            "date": day,
            "status": status,
            "message_count": message_count,
            "parts": [
                {
                    "file": f"full-history-chunks/{day}/{p.name}",
                    "lines": len(p.read_text(encoding="utf-8").splitlines()),
                    "bytes": p.stat().st_size,
                    "sha256": sha256_file(p),
                }
                for p in parts
            ],
            "staging_file": old.get(
                "staging_file",
                f"incremental-topic-cards-v1/{day}.md",
            ),
            "reviewed_through": old.get("reviewed_through"),
            "notes": old.get("notes", []),
        })

    return {
        "schema_version": 1,
        "status": "incremental_semantic_intake",
        "contract": {
            "formal_topic_coverage_requires_promotion": True,
            "staging_file_does_not_count_as_complete": True,
            "source_of_truth": "full-history-chunks",
        },
        "counts": {
            "missing_topic_candidate_dates": len(rows),
            "pending": sum(r["status"] == "pending" for r in rows),
            "in_progress": sum(r["status"] == "in_progress" for r in rows),
            "review_complete": sum(r["status"] == "review_complete" for r in rows),
        },
        "dates": rows,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--chunks-dir", type=Path, default=WORK / "full-history-chunks")
    p.add_argument("--topic-dir", type=Path, default=WORK / "topic-cards-v1")
    p.add_argument("--out", type=Path, default=WORK / "incremental-semantic-intake-v1.json")
    args = p.parse_args()

    previous = None
    if args.out.exists():
        previous = json.loads(args.out.read_text(encoding="utf-8"))
    result = build_manifest(args.chunks_dir, args.topic_dir, previous)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
