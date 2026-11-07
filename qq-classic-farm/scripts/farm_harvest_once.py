#!/usr/bin/env python3
"""Click the visible global harvest button once from the standard farm home."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from time import sleep

from farm_capture import capture_window
from farm_fertilize_once import FertilizerStop, click_batch, farm_canvas
from farm_geometry import WindowFrame
from farm_vision import match_anchor


ROOT = Path(__file__).resolve().parents[1]
HARVEST_SETTLE_SECONDS = 2.8


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("qq", "wechat"), required=True)
    parser.add_argument("--execute", action="store_true", help="Post one click. Default is a no-click preflight.")
    parser.add_argument("--registry", type=Path, default=ROOT / "_sandbox/farm_window_registry")
    parser.add_argument("--click-helper", type=Path, default=ROOT / "_sandbox/farm_click_batch")
    args = parser.parse_args()

    try:
        platform = args.platform
        layout = json.loads((ROOT / "data/ui-layout.json").read_text())
        anchors = json.loads((ROOT / "data/ui-anchors.json").read_text())
        config = layout["platforms"][platform]
        registry = subprocess.run(
            [str(args.registry), "--platform", platform],
            capture_output=True, text=True, check=True, timeout=5,
        )
        payload = json.loads(registry.stdout)
        windows = [w for w in payload["windows"] if w["title"] == "QQ经典农场"]
        if payload["platform"] != platform or len(windows) != 1:
            raise ValueError("FARM_WINDOW_NOT_UNIQUE_FOR_PLATFORM")
        window = windows[0]
        sidebar_width = config.get("embedded_canvas", {}).get("left_sidebar_width", 0)
        canvas = farm_canvas(window, config["baseline_window_size"], sidebar_width)
        frame = WindowFrame(window["owner"], window["title"], **canvas)
        capture = capture_window(frame, platform, layout)
        hand = match_anchor(
            capture, anchors["anchors"]["onekey_harvest"], anchors["matching"]["default_scales"],
        )
        if not hand["matched"]:
            raise ValueError("HARVEST_BUTTON_NOT_FOUND")
        x, y = hand["local_center"]
        target = {key: window[key] for key in ("window_id", "pid", "owner", "title")}
        target["window_frame"] = {key: window[key] for key in canvas}
        target["frame"] = canvas

        mode = "--execute" if args.execute else "--preflight"
        click_batch(args.click_helper, mode, target, [{"x": x, "y": y, "delay_ms": 0}])
        result = {"status": "preflight_ok_no_click", "button_score": round(hand["score"], 3)}
        if args.execute:
            sleep(HARVEST_SETTLE_SECONDS)
            result.update(status="harvest_click_sent_unverified", settle_seconds=HARVEST_SETTLE_SECONDS)
        print(json.dumps(result))
        return 0
    except (FertilizerStop, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "stopped", "reason": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
