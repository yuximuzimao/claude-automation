#!/usr/bin/env python3
"""Visit consecutive friends, use their shared interaction point once, and return home."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from anchor_locator import load_gray
from farm_daily_clicks import farm_target, find_point, return_home_point
from farm_fertilize_once import FertilizerStop, capture_region, click_batch, template_center


ROOT = Path(__file__).resolve().parents[1]
MAX_VISITS = 100


def interaction_state(image, templates, origin, shared_point):
    centers = [point for template in templates
               if (point := template_center(image, template, origin, 0.88)) is not None]
    if not centers:
        return "no_action"
    x, y = shared_point
    if any(abs(cx - x) <= 28 and abs(cy - y) <= 10 for cx, cy in centers):
        return "action"
    return "shared_point_outside_button"


def sweep(click, read_action, go_home, entry, first_visit, action_point, next_points, limit=MAX_VISITS):
    click(entry, 650)
    click(first_visit, 850)
    interactions = 0
    for index in range(limit):
        state = read_action()
        if state != "action":
            go_home()
            return state, interactions
        click(action_point, 650)
        interactions += 1
        if index + 1 < limit:
            click(next_points[min(index, 2)], 850)
    go_home()
    return "visit_limit", interactions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("qq", "wechat"), required=True)
    parser.add_argument("--execute", action="store_true", help="Post clicks. Default is a no-click preflight.")
    parser.add_argument("--registry", type=Path, default=ROOT / "_sandbox/farm_window_registry")
    parser.add_argument("--click-helper", type=Path, default=ROOT / "_sandbox/farm_click_batch")
    args = parser.parse_args()
    clicks = 0

    try:
        platform = args.platform
        layout = json.loads((ROOT / "data/ui-layout.json").read_text())
        fixed = json.loads((ROOT / "data/ui-anchors.json").read_text())["fixed_points"]
        scenes = fixed["scenes"]
        navigation = scenes["friend-farm-navigation"]
        visits = navigation["views"]
        first = visits["first"]["points"]
        later = visits["next"]["points"]
        entry = find_point(fixed["home"]["points"], platform, "friends")
        first_visit = find_point(scenes["friend-list"]["views"]["first-visit"]["points"], platform, "first-visit")
        shared = find_point(first, platform, "single-action")
        next_points = [find_point(first, platform, name) for name in ("second-friend", "third-friend")]
        next_points.append(find_point(later, platform, "fourth-onward"))
        templates = [load_gray(ROOT / "assets/ui/friends" / f"{platform}-{name}.png") for name in ("steal", "work")]
        strip = navigation["action_strip_xyxy"][platform]
        frame, target = farm_target(args.registry, platform, layout)

        def click(point, delay):
            nonlocal clicks
            x, y = point
            click_batch(args.click_helper, "--execute", target, [{"x": x, "y": y, "delay_ms": delay}])
            clicks += 1

        def read_action():
            return interaction_state(capture_region(target["frame"], strip), templates, strip[:2], shared)

        def go_home():
            click(return_home_point(frame, platform, layout), 800)

        if not args.execute:
            click_batch(args.click_helper, "--preflight", target, [
                {"x": x, "y": y, "delay_ms": 0} for x, y in (entry, first_visit, shared, *next_points)
            ])
            print(json.dumps({"status": "preflight_ok_no_click", "clicks_sent": 0}))
            return 0

        reason, interactions = sweep(click, read_action, go_home, entry, first_visit, shared, next_points)
        status = "return_home_click_sent" if reason == "no_action" else "stopped_return_home_click_sent"
        print(json.dumps({"status": status, "reason": reason, "interaction_clicks": interactions, "clicks_sent": clicks}))
        return 0 if reason == "no_action" else 2
    except (FertilizerStop, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "stopped", "reason": str(exc), "clicks_sent": clicks}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
