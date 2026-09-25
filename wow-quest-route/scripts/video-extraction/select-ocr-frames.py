#!/usr/bin/env python3
"""Select complete OCR frame blocks whose text matches a regular expression."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def split_frames(text: str) -> list[list[str]]:
    frames: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith("=== "):
            if current:
                frames.append(current)
            current = [line]
        elif current:
            current.append(line)
    if current:
        frames.append(current)
    return frames


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", type=Path)
    parser.add_argument("pattern")
    parser.add_argument("sources", nargs="+", type=Path)
    parser.add_argument("--context-frames", type=int, default=1)
    args = parser.parse_args()

    regex = re.compile(args.pattern, re.IGNORECASE)
    output: list[str] = []
    selected_total = 0

    for source in args.sources:
        frames = split_frames(source.read_text(encoding="utf-8"))
        hits = {i for i, frame in enumerate(frames) if regex.search("\n".join(frame))}
        selected: set[int] = set()
        for index in hits:
            for neighbor in range(max(0, index - args.context_frames), min(len(frames), index + args.context_frames + 1)):
                selected.add(neighbor)
        output.append(f"##### SOURCE {source} #####")
        for index in sorted(selected):
            output.extend(frames[index])
            output.append("")
        selected_total += len(selected)

    args.target.parent.mkdir(parents=True, exist_ok=True)
    args.target.write_text("\n".join(output) + "\n", encoding="utf-8")
    print(f"selected_frames={selected_total} output={args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
