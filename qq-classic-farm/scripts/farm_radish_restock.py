#!/usr/bin/env python3
"""Buy one month of QQ white-radish seeds from the already-open standard farm home."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from time import sleep

from anchor_locator import load_gray

from farm_daily_clicks import farm_target, find_point
from farm_fertilize_once import FertilizerStop, click_batch, capture_region, template_center


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PURCHASES = 37
SHOP_SCROLL = {"from_x": 300, "from_y": 330, "to_x": 300, "to_y": 860, "steps": 24}

MAX_SCROLLS = 10
SCROLL_SETTLE_SECONDS = 1.5
# First card's artwork area only; excludes adjacent cards and the second row.
RADISH_ROI = (35, 320, 165, 396)
RADISH_TEMPLATE = ROOT / "assets/ui/shop/qq-white-radish.png"
RADISH_THRESHOLD = 0.90


def seek_radish(scroll, matches, wait=sleep):
    for count in range(1, MAX_SCROLLS + 1):
        scroll()
        wait(SCROLL_SETTLE_SECONDS)
        if matches():
            return count
    raise FertilizerStop("RADISH_NOT_FOUND_AFTER_10_SCROLLS_AGENT_REQUIRED")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--purchases", type=int, default=DEFAULT_PURCHASES)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--registry", type=Path, default=ROOT / "_sandbox/farm_window_registry")
    parser.add_argument("--click-helper", type=Path, default=ROOT / "_sandbox/farm_click_batch")
    parser.add_argument("--drag-helper", type=Path, default=ROOT / "_sandbox/farm_drag")
    args = parser.parse_args()

    if not 1 <= args.purchases <= 50:
        print(json.dumps({"status": "stopped", "reason": "PURCHASES_MUST_BE_1_TO_50"}))
        return 2

    anchors = json.loads((ROOT / "data/ui-anchors.json").read_text())
    fixed = anchors["fixed_points"]
    shop_scene = fixed["scenes"]["shop"]
    qq_purchase = shop_scene["purchase_dialog"]["white_radish"]
    quantity_each = qq_purchase["max_quantity"]
    summary = {
        "purchases": args.purchases,
        "quantity_each": quantity_each,
        "total_quantity": args.purchases * quantity_each,
    }
    if not args.execute:
        print(json.dumps({"status": "plan_ok_no_click", **summary}))
        return 0

    try:
        layout = json.loads((ROOT / "data/ui-layout.json").read_text())
        _, target = farm_target(args.registry, "qq", layout)
        home_shop = find_point(fixed["home"]["points"], "qq", "shop")
        shop_points = shop_scene["views"]["seeds"]["points"]
        radish_card = find_point(shop_points, "qq", "seed-1-1")
        close_shop = find_point(shop_points, "qq", "close")
        max_button = qq_purchase["max_button"]
        confirm_button = qq_purchase["confirm_button"]

        click_batch(args.click_helper, "--execute", target, [
            {"x": home_shop[0], "y": home_shop[1], "delay_ms": 650},
        ])

        drag_request = {
            key: target[key] for key in ("window_id", "pid", "owner", "title")
        }
        drag_request.update(frame=target["frame"], **SHOP_SCROLL)
        template = load_gray(RADISH_TEMPLATE)

        def scroll():
            drag = subprocess.run(
                [str(args.drag_helper), "--execute"],
                input=json.dumps(drag_request), capture_output=True, text=True, timeout=8,
            )
            if drag.returncode:
                raise RuntimeError(drag.stdout.strip() or drag.stderr.strip() or "RADISH_SHOP_SCROLL_FAILED")
            reply = json.loads(drag.stdout)
            if reply.get("status") != "drag_sent_unverified":
                raise FertilizerStop("UNEXPECTED_DRAG_HELPER_RESULT")

        scrolls = seek_radish(scroll, lambda: template_center(
            capture_region(target["frame"], RADISH_ROI), template,
            RADISH_ROI[:2], RADISH_THRESHOLD,
        ) is not None)

        completed = 0
        for _ in range(args.purchases):
            click_batch(args.click_helper, "--execute", target, [
                {"x": radish_card[0], "y": radish_card[1], "delay_ms": 450},
                {"x": max_button[0], "y": max_button[1], "delay_ms": 280},
                {"x": confirm_button[0], "y": confirm_button[1], "delay_ms": 520},
            ])
            completed += 1

        click_batch(args.click_helper, "--execute", target, [
            {"x": close_shop[0], "y": close_shop[1], "delay_ms": 400},
        ])
        print(json.dumps({
            "status": "radish_restock_clicks_sent",
            "completed_purchases": completed,
            "scrolls_to_radish": scrolls,
            **summary,
        }))
        return 0
    except (FertilizerStop, OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "stopped", "reason": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
