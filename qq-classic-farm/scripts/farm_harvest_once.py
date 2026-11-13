#!/usr/bin/env python3
"""Harvest recorded four-plot crops at confirmed points, then use one-key harvest."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from time import sleep

from farm_capture import FarmCapture
from farm_daily_clicks import farm_target
from farm_fertilize_once import FertilizerStop, capture_region, click_batch
from farm_geometry import WindowFrame
from farm_level_up import dismiss_level_up
from farm_plant_once import read_plan
from farm_vision import match_anchor


ROOT = Path(__file__).resolve().parents[1]
HARVEST_SETTLE_SECONDS = 2.8


def special_points(plots, recognition):
    """Use only directly confirmed points; never derive clicks from land centers."""
    registered = recognition.get("special_click_points", {})
    points = []
    for plot in plots:
        point = registered.get(f"{plot:02}")
        if (not isinstance(point, list) or len(point) != 2
                or any(type(v) not in (int, float) for v in point)
                or not (0 < point[0] < 603 and 0 < point[1] < 1111)):
            raise ValueError(f"SPECIAL_HARVEST_POINT_NOT_VALIDATED_{plot:02}")
        points.append(tuple(point))
    return points


def validate_planted_plan(path, platform, layout, anchors, *, full_field=False):
    """Validate immediately after record writing; execution reuses this as a guard."""
    if path is None:
        raise ValueError("PLANTED_RECORD_REQUIRED_REWRITE")
    if path.resolve() == (ROOT / "data/operation-plan.json").resolve():
        raise ValueError("NEXT_PLANTING_PLAN_IS_NOT_A_PLANTED_RECORD")
    # Keep the existing complete plan format; no missing platform/default repair.
    for selected in ("qq", "wechat"):
        read_plan(path, selected, layout["plot_policy"])
    record = json.loads(path.read_text(encoding="utf-8"))
    planting = record[platform]["planting"]
    special = planting["special"]
    ordinary = ([planting["ordinary"]] if planting["ordinary"] else [])
    ordinary += planting.get("ordinary_after_exhaustion", [])
    for item in special + ordinary:
        if not isinstance(item.get("seed_name"), str) or not item["seed_name"].strip():
            raise ValueError("PLANTED_SEED_NAME_REQUIRED_REWRITE")
        if type(item.get("quantity")) is not int or item["quantity"] <= 0:
            raise ValueError("PLANTED_QUANTITY_REQUIRED_REWRITE")
    if any(item["quantity"] != 1 for item in special):
        raise ValueError("EACH_SPECIAL_ENTRY_MUST_RECORD_ONE_SEED")
    occupied = 4 * len(special) + sum(item["quantity"] for item in ordinary)
    if not 1 <= occupied <= 24 or (full_field and occupied != 24):
        raise ValueError("PLANTED_FIELD_QUANTITY_MISMATCH_REWRITE")
    plots = [item["plot"] for item in special]
    points = special_points(plots, anchors["anchors"]["onekey_harvest"]["platforms"][platform])
    return plots, points


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
    parser.add_argument("--ordinary-only", action="store_true", help="Explicitly confirm no four-plot crops (e.g. radish cycle).")
    parser.add_argument("--mature-confirmed", action="store_true", help="Natural maturity reached, or last-stage fertilizer completed successfully.")
    parser.add_argument("--check-plan", action="store_true", help="Offline planted-record validation; no window or input.")
    parser.add_argument("--execute", action="store_true", help="Post clicks. Default is a no-click preflight.")
    parser.add_argument("--registry", type=Path, default=ROOT / "_sandbox/farm_window_registry")
    parser.add_argument("--click-helper", type=Path, default=ROOT / "_sandbox/farm_click_batch")
    args = parser.parse_args()
    special_clicks = 0
    ordinary_click_sent = False

    try:
        platform = args.platform
        layout = json.loads((ROOT / "data/ui-layout.json").read_text())
        anchors = json.loads((ROOT / "data/ui-anchors.json").read_text())
        spec = anchors["anchors"]["onekey_harvest"]
        scales = anchors["matching"]["default_scales"]
        recognition = spec["platforms"][platform]
        if args.check_plan and not args.planted_plan:
            raise ValueError("CHECK_PLAN_REQUIRES_PLANTED_RECORD")
        if args.check_plan and args.execute:
            raise ValueError("CHECK_PLAN_CANNOT_EXECUTE")
        if bool(args.planted_plan) == args.ordinary_only:
            raise ValueError("CHOOSE_PLANTED_RECORD_OR_EXPLICIT_ORDINARY_ONLY")
        plots, stars = (validate_planted_plan(args.planted_plan, platform, layout, anchors, full_field=args.check_plan)
                        if args.planted_plan else ([], []))
        if args.check_plan:
            print(json.dumps({"status": "planted_record_ok_no_click", "special_plots": plots,
                              "special_points": stars}))
            return 0
        if stars and not args.mature_confirmed:
            raise ValueError("MATURITY_PRECONDITION_REQUIRED")

        frame, target = farm_target(args.registry, platform, layout)

        def capture(rect):
            return capture_region(target["frame"], rect)

        def locate_hand():
            return hand_point(capture, frame, recognition["hand_rect"], spec, scales)

        def action(point, delay=0):
            return {"x": point[0], "y": point[1], "delay_ms": delay}

        def check_level_up():
            if platform == 'qq':
                dismiss_level_up(capture, lambda point, delay: click_batch(
                    args.click_helper, '--execute', target, [action(point, delay)]))

        hand, score = locate_hand()
        result = {"status": "preflight_ok_no_click", "button_score": round(score, 3), "special_plots": plots}
        if args.execute:
            for star in stars:
                click_batch(args.click_helper, "--execute", target, [action(star, 220)])
                special_clicks += 1
                check_level_up()
            if stars:
                hand, score = locate_hand()
            click_batch(args.click_helper, "--execute", target, [action(hand)])
            ordinary_click_sent = True
            sleep(HARVEST_SETTLE_SECONDS)
            check_level_up()
            result.update(status="harvest_click_sent_unverified", button_score=round(score, 3),
                          special_clicks_sent=special_clicks, settle_seconds=HARVEST_SETTLE_SECONDS)
        else:
            click_batch(args.click_helper, "--preflight", target, [action(point) for point in (*stars, hand)])
        print(json.dumps(result))
        return 0
    except (FertilizerStop, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "rejected_rewrite_required" if args.check_plan else "stopped",
                          "reason": str(exc), "special_clicks_sent": special_clicks,
                          "ordinary_click_sent": ordinary_click_sent},
                         ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
