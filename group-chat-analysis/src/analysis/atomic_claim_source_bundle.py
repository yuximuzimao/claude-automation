"""Create deterministic source bundles for atomic-claim extraction."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .quality import WORK

SOURCE_DIR = WORK / "full-history-chunks"


def read_segments(date: str, segments: list[dict]) -> list[str]:
    out: list[str] = []
    for seg in segments:
        path = SOURCE_DIR / date / seg["file"]
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for n in range(int(seg["start_line"]), int(seg["end_line"]) + 1):
            if 1 <= n <= len(lines):
                out.append(f"{seg['file']}:{n} | {lines[n-1]}")
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=12)
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--out", type=Path, default=WORK / "atomic-claim-source-bundle-v1.md")
    args = p.parse_args()

    queue = json.loads((WORK / "atomic-claim-work-queue-v1.json").read_text(encoding="utf-8"))
    verified = json.loads((WORK / "verified-source-anchors-v1.json").read_text(encoding="utf-8"))
    anchors = verified.get("anchors", {})

    selected = []
    eligible_seen = 0
    for item in queue.get("items", []):
        if item.get("lane") != "ready_from_high_anchor":
            continue
        anchor = anchors.get(item["card_id"])
        if not anchor:
            continue
        if eligible_seen < args.offset:
            eligible_seen += 1
            continue
        eligible_seen += 1
        selected.append((item, anchor))
        if len(selected) >= args.limit:
            break

    lines = [
        "# Atomic Claim Source Bundle",
        "",
        f"- count: {len(selected)}",
        "- contract: Topic Card text is hint only; canonical lines below are source truth.",
        "",
    ]
    for item, anchor in selected:
        lines += [
            f"## {item['card_id']} — {item['title_hint']}",
            f"- date: {item['date']}",
            f"- old_summary_hint: {item['semantic_summary_hint']}",
            f"- source_segments: {json.dumps(anchor.get('segments', []), ensure_ascii=False)}",
            "- canonical_source:",
            "~~~text",
            *read_segments(anchor["date"], anchor["segments"]),
            "~~~",
            "",
        ]

    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"count": len(selected), "out": str(args.out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
