"""Offline, read-only M1 replay of two user-labeled farm screenshots.

Usage: python3 scripts/farm_clean_replay.py --platform qq
       --reference path/to/known-clean.png --current path/to/candidate.png
No game window access, state updates, or click authorization.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from farm_capture import FarmCapture, CaptureStop
from farm_clean_field import CleanFieldStop, compare_clean_reference
from farm_geometry import WindowFrame

ROOT = Path(__file__).resolve().parents[1]


def load_replay(path: Path, platform: str, layout: dict) -> FarmCapture:
    width, height = layout["platforms"][platform]["baseline_window_size"]
    owner = "QQ小程序" if platform == "qq" else "微信"
    with Image.open(path) as img:
        rgb = np.asarray(img.convert("RGB"), dtype=np.uint8)
        gray = np.asarray(img.convert("L"), dtype=np.float32)
    return FarmCapture(WindowFrame(owner, "QQ经典农场", 0, 0, width, height),
                       gray, rgb=rgb)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True, choices=("qq", "wechat"))
    parser.add_argument("--reference", type=Path, required=True,
                        help="User-labeled fully clean screenshot, same platform")
    parser.add_argument("--current", type=Path, required=True)
    args = parser.parse_args()
    try:
        layout = json.loads((ROOT / "data/ui-layout.json").read_text(encoding="utf-8"))
        reference = load_replay(args.reference, args.platform, layout)
        current = load_replay(args.current, args.platform, layout)
        result = compare_clean_reference(current, reference, args.platform, layout)
    except (OSError, ValueError, KeyError, CaptureStop, CleanFieldStop) as exc:
        print(json.dumps({"status": "stopped",
                          "code": getattr(exc, "code", "REPLAY_INPUT_INVALID"),
                          "detail": str(exc),
                          "can_authorize_clicks": False}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
