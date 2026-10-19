"""Render a private review queue for source-anchor proposals."""
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
        for n in range(seg["start_line"], seg["end_line"] + 1):
            if 1 <= n <= len(lines):
                out.append(f"{seg['file']}:{n} | {lines[n-1]}")
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--min-score", type=float, default=.07)
    p.add_argument("--include-full", action="store_true")
    p.add_argument("--corrections", type=Path, default=WORK / "semantic-correction-queue-v1.json")
    p.add_argument("--out", type=Path, default=WORK / "source-anchor-review-v1.md")
    args = p.parse_args()

    proposal = json.loads((WORK / "source-anchor-backfill-proposals-v1.json").read_text(encoding="utf-8"))
    candidates = json.loads((WORK / "silver-candidates-v1.json").read_text(encoding="utf-8"))["candidates"]
    by_id = {x["card_id"]: x for x in candidates}
    correction_ids = set()
    if args.corrections.exists():
        correction_doc = json.loads(args.corrections.read_text(encoding="utf-8"))
        correction_ids = {x.get("card_id") for x in correction_doc.get("issues", []) if x.get("card_id")}

    rows = []
    for item in proposal["proposals"]:
        if item["status"] != "review_required" or not item["candidates"]:
            continue
        if item["card_id"] in correction_ids:
            continue
        if item["candidates"][0]["score"] < args.min_score:
            continue
        if not args.include_full and item["silver_status"] == "full":
            continue
        card = by_id[item["card_id"]]
        top = item["candidates"][0]
        rows.append((top["score"], item, card))
    rows.sort(key=lambda x: (-x[0], x[1]["card_id"]))

    text = [
        "# Source Anchor Review Queue",
        "",
        f"- min_score: {args.min_score}",
        f"- include_full: {args.include_full}",
        f"- count: {len(rows)}",
        "- decision: verified / rejected / needs_more_context",
        "",
    ]
    for _, item, card in rows:
        top = item["candidates"][0]
        second = item["candidates"][1] if len(item["candidates"]) > 1 else None
        second_text = f"score={second['score']} time={second['time_range']}" if second else "none"
        text += [
            f"## {item['card_id']} — {card['title']}",
            f"- silver_status: {item['silver_status']}",
            f"- semantic_summary: {card['semantic_summary']}",
            f"- top1: score={top['score']} margin={top.get('margin_from_second')} time={top['time_range']}",
            f"- top2: {second_text}",
            "- candidate_source:",
            "~~~text",
            *read_segments(item["date"], top["segments"]),
            "~~~",
            "",
        ]
    args.out.write_text("\n".join(text), encoding="utf-8")
    print(json.dumps({"out": str(args.out), "count": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
