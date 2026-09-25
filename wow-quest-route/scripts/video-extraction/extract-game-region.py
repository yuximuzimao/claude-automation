#!/usr/bin/env python3
"""Extract compact OCR text from the Bilibili video/game region.

Vision OCR coordinates are normalized with a bottom-left origin. The default
bounds exclude the right recommendation column, the top site navigation, and
most content below the player while retaining the game HUD and chat text.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

LINE_RE = re.compile(
    r"^(?P<x>\d+\.\d+)\s+(?P<y>\d+\.\d+)\s+(?P<w>\d+\.\d+)\s+(?P<h>\d+\.\d+)\t(?P<text>.*)$"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--max-x", type=float, default=0.80)
    parser.add_argument("--min-y", type=float, default=0.18)
    parser.add_argument("--max-y", type=float, default=0.96)
    parser.add_argument("--min-height", type=float, default=0.008)
    args = parser.parse_args()

    output: list[str] = []
    frame_lines: list[tuple[float, float, str]] = []

    def flush_frame() -> None:
        nonlocal frame_lines
        # Vision generally returns reading order, but explicit sorting makes the
        # result stable: upper lines first, then left-to-right.
        frame_lines.sort(key=lambda item: (-item[0], item[1]))
        output.extend(text for _, _, text in frame_lines)
        frame_lines = []

    for raw in args.source.read_text(encoding="utf-8").splitlines():
        if raw.startswith("=== "):
            flush_frame()
            output.append(raw)
            continue
        match = LINE_RE.match(raw)
        if not match:
            continue
        x = float(match.group("x"))
        y = float(match.group("y"))
        h = float(match.group("h"))
        text = match.group("text").strip()
        if not text:
            continue
        if x > args.max_x or y < args.min_y or y > args.max_y or h < args.min_height:
            continue
        frame_lines.append((y, x, text))

    flush_frame()
    args.target.parent.mkdir(parents=True, exist_ok=True)
    args.target.write_text("\n".join(output) + "\n", encoding="utf-8")
    print(f"lines={len(output)} output={args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
