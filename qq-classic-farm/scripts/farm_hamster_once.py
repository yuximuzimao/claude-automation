#!/usr/bin/env python3
"""Recognize the merchant hamster at farm home and buy its offer once."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import subprocess

from farm_capture import capture_window
from farm_daily_clicks import ROOT, farm_target, find_point
from farm_fertilize_once import FertilizerStop, click_batch
from farm_vision import match_anchor


SCAN_COUNT = 3


def detect_hamster(capture, probes):
    for _ in range(SCAN_COUNT):
        shot = capture()
        rgb = shot.rgb
        if rgb is None or rgb.shape != (shot.frame.height, shot.frame.width, 3):
            raise ValueError("HAMSTER_REQUIRES_LOGICAL_PIXEL_RGB_CAPTURE")
        if all(tuple(rgb[y, x]) == tuple(color) for x, y, color in probes):
            return True
    return False


def require_screen(capture, platform, name, roi):
    shot = capture()
    x, y, width, height = roi
    result = match_anchor(shot, {
        "template": f"assets/ui/merchant/{platform}-{name}.png",
        "roi_normalized": [x / shot.frame.width, y / shot.frame.height,
                           width / shot.frame.width, height / shot.frame.height],
        "threshold": 0.90,
    }, [1.0])
    if not result["matched"]:
        raise ValueError(f"MERCHANT_{name.upper()}_SCREEN_NOT_FOUND")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("qq", "wechat"), required=True)
    parser.add_argument("--execute", action="store_true", help="Buy on detection. Default only checks for the hamster.")
    parser.add_argument("--registry", type=Path, default=ROOT / "_sandbox/farm_window_registry")
    parser.add_argument("--click-helper", type=Path, default=ROOT / "_sandbox/farm_click_batch")
    args = parser.parse_args()

    clicks_sent = 0
    reward_seen = False
    inventory_pending = ROOT / "data/hamster-inventory-pending.json"
    purchase_attempted = False
    try:
        platform = args.platform
        if args.execute and inventory_pending.exists():
            raise ValueError("HAMSTER_INVENTORY_REFRESH_PENDING")
        layout = json.loads((ROOT / "data/ui-layout.json").read_text())
        scenes = json.loads((ROOT / "data/ui-anchors.json").read_text())["fixed_points"]["scenes"]
        merchant = scenes["merchant"]
        recognition = merchant["recognition"][platform]
        bubble = find_point(merchant["views"]["bubble"]["points"], platform, "hamster-bubble")
        buy = find_point(merchant["views"]["popup"]["points"], platform, "buy")
        blank = find_point(scenes["mall-welfare"]["views"]["reward"]["points"], platform, "dismiss-blank")
        frame, target = farm_target(args.registry, platform, layout)

        def capture():
            return capture_window(frame, platform, layout)

        def click(point, delay):
            nonlocal clicks_sent
            x, y = point
            click_batch(args.click_helper, "--execute", target, [{"x": x, "y": y, "delay_ms": delay}])
            clicks_sent += 1

        if not detect_hamster(capture, recognition["rgb_points"]):
            status = "hamster_not_detected"
        elif not args.execute:
            status = "hamster_detected_no_click"
        else:
            click(bubble, 850)
            require_screen(capture, platform, "buy", recognition["buy_roi"])
            # Persist before purchase: interruption after this point must still
            # route the Agent to a warehouse refresh, never another blind buy.
            pending = {"platform": platform, "status": "purchase_pending_verification",
                       "at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()}
            inventory_pending.write_text(json.dumps(pending, ensure_ascii=False))
            if json.loads(inventory_pending.read_text()) != pending:
                raise ValueError("INVENTORY_PENDING_READBACK_FAILED")
            purchase_attempted = True
            click(buy, 950)
            require_screen(capture, platform, "reward", recognition["reward_roi"])
            reward_seen = True
            click(blank, 450)
            status = "merchant_reward_seen_dismiss_clicked"
        print(json.dumps({"status": status, "clicks_sent": clicks_sent,
                          "inventory_refresh_required": reward_seen,
                          "inventory_pending_file": str(inventory_pending) if reward_seen else None}))
        return 0
    except (FertilizerStop, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "stopped", "reason": str(exc), "clicks_sent": clicks_sent,
                          "reward_seen": reward_seen,
                          "inventory_refresh_required": purchase_attempted or inventory_pending.exists()}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
