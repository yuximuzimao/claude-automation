#!/usr/bin/env python3
"""Harvest the recorded four-plot crops, if supplied, then use one-key harvest."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from time import sleep

from anchor_locator import load_gray
from farm_capture import FarmCapture
from farm_daily_clicks import farm_target
from farm_fertilize_once import FertilizerStop, capture_region, click_batch, template_center
from farm_geometry import WindowFrame
from farm_plant_once import read_plan
from farm_vision import match_anchor


ROOT = Path(__file__).resolve().parents[1]
HARVEST_SETTLE_SECONDS = 2.8


def special_points(capture, platform, plots, regions):
    if not plots:
        return []
    if any(f"{plot:02}" not in regions for plot in plots):
        raise ValueError("SPECIAL_HARVEST_GROUP_NOT_VALIDATED")

    rectangles = [regions[f"{plot:02}"] for plot in plots]
    left = min(rect[0] for rect in rectangles)
    top = min(rect[1] for rect in rectangles)
    image = capture((left, top, max(rect[2] for rect in rectangles), max(rect[3] for rect in rectangles)))
    points = []
    for plot, (x0, y0, x1, y1) in zip(plots, rectangles):
        template = load_gray(ROOT / "assets/ui/harvest" / f"{platform}-special-{plot:02}.png")
        point = template_center(image[y0-top:y1-top, x0-left:x1-left], template, (x0, y0), 0.88)
        if point is None:
            raise ValueError(f"SPECIAL_PICKABLE_NOT_FOUND_AT_PLOT_{plot:02}")
        points.append(point)
    return points


def hand_point(capture, frame, rect, spec, scales):
    x0, y0, x1, y1 = rect
    local_frame = WindowFrame(frame.owner, frame.title, frame.x + x0, frame.y + y0, x1 - x0, y1 - y0)
    hand = match_anchor(FarmCapture(local_frame, capture(rect)), {**spec, "roi_normalized": [0, 0, 1, 1]}, scales)
    if not hand["matched"]:
        raise ValueError("HARVEST_BUTTON_NOT_FOUND")
    x, y = hand["local_center"]
    return (x + x0, y + y0), hand["score"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("qq", "wechat"), required=True)
    parser.add_argument("--planted-plan", type=Path, help="Plan verified as planted on this field, for four-plot harvest.")
    parser.add_argument("--execute", action="store_true", help="Post clicks. Default is a no-click preflight.")
    parser.add_argument("--registry", type=Path, default=ROOT / "_sandbox/farm_window_registry")
    parser.add_argument("--click-helper", type=Path, default=ROOT / "_sandbox/farm_click_batch")
    args = parser.parse_args()
    special_clicks = 0

    try:
        platform = args.platform
        layout = json.loads((ROOT / "data/ui-layout.json").read_text())
        anchors = json.loads((ROOT / "data/ui-anchors.json").read_text())
        spec = anchors["anchors"]["onekey_harvest"]
        scales = anchors["matching"]["default_scales"]
        recognition = spec["platforms"][platform]
        plots = []
        if args.planted_plan:
            steps, _ = read_plan(args.planted_plan, platform, layout["plot_policy"])
            plots = [plot for plot, _, _, group in steps if group]

        frame, target = farm_target(args.registry, platform, layout)

        def capture(rect):
            return capture_region(target["frame"], rect)

        def locate_hand():
            return hand_point(capture, frame, recognition["hand_rect"], spec, scales)

        def action(point, delay=0):
            return {"x": point[0], "y": point[1], "delay_ms": delay}

        stars = special_points(capture, platform, plots, recognition["special_rects"])
        hand, score = locate_hand()
        result = {"status": "preflight_ok_no_click", "button_score": round(score, 3), "special_plots": plots}
        if args.execute:
            for star in stars:
                click_batch(args.click_helper, "--execute", target, [action(star, 220)])
                special_clicks += 1
            if stars:
                hand, score = locate_hand()
            click_batch(args.click_helper, "--execute", target, [action(hand)])
            sleep(HARVEST_SETTLE_SECONDS)
            result.update(status="harvest_click_sent_unverified", button_score=round(score, 3),
                          special_clicks_sent=special_clicks, settle_seconds=HARVEST_SETTLE_SECONDS)
        else:
            click_batch(args.click_helper, "--preflight", target, [action(point) for point in (*stars, hand)])
        print(json.dumps(result))
        return 0
    except (FertilizerStop, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "stopped", "reason": str(exc), "special_clicks_sent": special_clicks},
                         ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
