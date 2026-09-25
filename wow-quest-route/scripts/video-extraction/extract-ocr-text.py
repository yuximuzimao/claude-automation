#!/usr/bin/env python3
"""Convert Vision OCR output into compact per-frame text for manual review."""

from __future__ import annotations

import re
import sys
from pathlib import Path

LINE_RE = re.compile(
    r"^(?P<x>\d+\.\d+)\s+(?P<y>\d+\.\d+)\s+(?P<w>\d+\.\d+)\s+(?P<h>\d+\.\d+)\t(?P<text>.*)$"
)


def main() -> int:
    if len(sys.argv) not in {3, 4}:
        raise SystemExit("usage: extract-ocr-text.py <input-ocr> <output-text> [min-height]")

    source = Path(sys.argv[1])
    target = Path(sys.argv[2])
    min_height = float(sys.argv[3]) if len(sys.argv) == 4 else 0.0

    output: list[str] = []
    for raw_line in source.read_text(encoding="utf-8").splitlines():
        if raw_line.startswith("=== "):
            output.append(raw_line)
            continue
        match = LINE_RE.match(raw_line)
        if not match:
            continue
        if float(match.group("h")) < min_height:
            continue
        text = match.group("text").strip()
        if text:
            output.append(text)

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(output) + "\n", encoding="utf-8")
    print(f"lines={len(output)} output={target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
