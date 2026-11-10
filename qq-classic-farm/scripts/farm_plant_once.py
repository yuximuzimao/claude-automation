#!/usr/bin/env python3
"""Plant the selected platform's local plan from the standard farm home."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from time import sleep

import numpy as np
from PIL import Image

from anchor_locator import load_gray, normalized_cross_correlation
from farm_capture import capture_window
from farm_fertilize_once import FertilizerStop, click_batch, farm_canvas
from farm_geometry import WindowFrame


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = ROOT / "data/operation-plan.json"
TEMPLATES = ROOT / "assets/ui/planting"
DAILY_ACTIONS = ("tasks", "fertilizer_reward", "share")
MATCH_THRESHOLD = 0.90
PICKER_DELAY_MS = 650
PAGE_DELAY_MS = 650
PREVIEW_DELAY_MS = 1200
CONFIRM_DELAY_MS = 1400
ORDINARY_SETTLE_SECONDS = 2.8


def match(image, template, rect):
    """Return the best template's top-left point and score in logical pixels."""
    x0, y0, x1, y1 = rect
    scores = normalized_cross_correlation(image[y0:y1, x0:x1], template)
    if scores is None:
        raise ValueError("INVALID_MATCH_REGION")
    row, col = np.unravel_index(scores.argmax(), scores.shape)
    return (x0 + int(col), y0 + int(row)), float(scores[row, col])


def picker_anchor(image, template, picker):
    point, score = match(image, template, picker["search_rect_xyxy_exclusive"])
    if score < MATCH_THRESHOLD:
        raise ValueError("FIRST_PICKER_PAGE_NOT_FOUND")
    return point


def shifted(point, offset):
    return tuple(a + b for a, b in zip(point, offset))


def checkbox_state(image, point, templates):
    x, y = point
    box = (x - 20, y - 21, x + 20, y + 21)
    states = [state for state in ("on", "off")
              if match(image, templates[state], box)[1] >= MATCH_THRESHOLD]
    if len(states) != 1:
        raise ValueError("ONE_KEY_STATE_UNKNOWN")
    return states[0]


def seed_slot_offset(picker, slot, page_items=5):
    if type(page_items) is not int or not 1 <= page_items <= 5 or not 1 <= slot <= page_items:
        raise ValueError("INVALID_SEED_PAGE_ITEMS_OR_SLOT")
    # Slot is the ordinal within the page, not the fixed five-icon coordinate.
    position = slot - 1 + (5 - page_items) / 2
    left = int(position)
    right = min(left + 1, 4)
    fraction = position - left
    offsets = picker["seed_slot_offsets"]
    return tuple(a + (b - a) * fraction for a, b in zip(offsets[left], offsets[right]))


def plan_page_sizes(path, platform):
    planting = json.loads(path.read_text())[platform]["planting"]
    entries = planting["special"] + ([planting["ordinary"]] if planting["ordinary"] else []) + planting.get("ordinary_after_exhaustion", [])
    return [entry.get("page_items", 5) for entry in entries]


def plant(click, capture, steps, lands, picker, prompt, confirm, templates, page_sizes=None):
    for index, (plot, page, slot, group) in enumerate(steps):
        click(lands[plot], PICKER_DELAY_MS)
        image = capture()
        anchor = picker_anchor(image, templates["page-prefix"], picker)
        if index == 0:
            checkbox = shifted(anchor, picker["checkbox_offset"])
            prompt_rect = prompt["prompt_search_rect"]
            prompt_template = templates["enable-prompt"]
            if checkbox_state(image, checkbox, templates) == "off":
                click(checkbox, PICKER_DELAY_MS)
                if match(capture(), prompt_template, prompt_rect)[1] < MATCH_THRESHOLD:
                    raise ValueError("ONE_KEY_ENABLE_PROMPT_NOT_FOUND")
                click(prompt["confirm_point"], PICKER_DELAY_MS)
                image = capture()
                anchor = picker_anchor(image, templates["page-prefix"], picker)
                checkbox = shifted(anchor, picker["checkbox_offset"])
                if checkbox_state(image, checkbox, templates) != "on":
                    raise ValueError("ONE_KEY_ENABLE_NOT_CONFIRMED")
            if match(image, prompt_template, prompt_rect)[1] >= MATCH_THRESHOLD:
                raise ValueError("ONE_KEY_ENABLE_PROMPT_STILL_OPEN")

        for _ in range(page - 1):
            click(shifted(anchor, picker["next_page_offset"]), PAGE_DELAY_MS)
        click(shifted(anchor, seed_slot_offset(picker, slot, page_sizes[index] if page_sizes else 5)), PREVIEW_DELAY_MS if group else 0)
        if not group:
            sleep(ORDINARY_SETTLE_SECONDS)
            continue

        button = templates["special-confirm"]
        half_h, half_w = (size // 2 for size in button.shape)
        dx, dy = confirm["offset"]
        x = round(sum(lands[p][0] for p in group) / 4 + dx)
        y = round(sum(lands[p][1] for p in group) / 4 + dy)
        margin_x, margin_y = confirm["margin"]
        box = (x - margin_x - half_w, y - margin_y - half_h,
               x + margin_x + half_w, y + margin_y + half_h)
        point, score = match(capture(), button, box)
        if score < MATCH_THRESHOLD:
            raise ValueError(f"SPECIAL_CONFIRM_NOT_FOUND_AT_PLOT_{plot:02}")
        click(shifted(point, (half_w, half_h)), CONFIRM_DELAY_MS)


def planting_steps(special, ordinary, policy, followups=()):
    groups = {entry["entry_plot"]: entry["plots"] for entry in policy["special_2x2"]["direct_entry_map"]}
    forbidden = set(policy["forbidden_single_click"])
    steps = []
    covered = set()
    for plot, page, slot in special:
        group = groups.get(plot)
        if group is None or plot in forbidden or covered.intersection(group):
            raise ValueError(f"INVALID_SPECIAL_ENTRY_{plot:02}")
        steps.append((plot, page, slot, group))
        covered.update(group)
    ordinary_positions = ([ordinary] if ordinary else []) + list(followups)
    for index, position in enumerate(ordinary_positions):
        # Count ordinary selections only; four-plot crops have explicit entries.
        # Preserve the verified single ordinary-only flow (including radish).
        plot = 24 - index if special or followups else 1
        if plot < 1 or plot in forbidden or plot in covered:
            raise ValueError(f"INVALID_ORDINARY_ENTRY_{plot:02}")
        steps.append((plot, *position, None))
    if any(page < 1 or not 1 <= slot <= 5 for _, page, slot, _ in steps):
        raise ValueError("PLAN_REQUIRES_PAGE_AT_LEAST_1_AND_SLOT_1_TO_5")
    return steps


def plan_object(value, keys, name):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(f"{name} must have exactly these fields: {', '.join(keys)}")
    return value


def seed_position(value, keys, name):
    if isinstance(value, dict):
        if "quantity" in value and (type(value["quantity"]) is not int or value["quantity"] <= 0):
            raise ValueError("INVALID_PLANNED_SEED_QUANTITY")
        if "seed_name" in value and not isinstance(value["seed_name"], str):
            raise ValueError("INVALID_PLANNED_SEED_NAME")
        value = {key: item for key, item in value.items() if key not in ("seed_name", "quantity")}
    if isinstance(value, dict) and "page_items" in value:
        count = value["page_items"]
        if type(count) is not int or not 1 <= count <= 5 or not 1 <= value.get("slot", 0) <= count:
            raise ValueError("INVALID_SEED_PAGE_ITEMS_OR_SLOT")
        value = {key: item for key, item in value.items() if key != "page_items"}
    position = plan_object(value, keys, name)
    if any(type(position[key]) is not int for key in keys):
        raise ValueError(f"{name} fields must be integers")
    return tuple(position[key] for key in keys)


def read_plan(path, platform, policy):
    plan = plan_object(json.loads(path.read_text(encoding="utf-8")), ("qq", "wechat"), "plan")
    selected = plan_object(plan[platform], ("planting", "daily"), platform)
    planting = selected["planting"]
    keys = ("special", "ordinary", "ordinary_after_exhaustion") if isinstance(planting, dict) and "ordinary_after_exhaustion" in planting else ("special", "ordinary")
    planting = plan_object(planting, keys, f"{platform}.planting")
    followups = planting.get("ordinary_after_exhaustion", [])
    if not isinstance(followups, list):
        raise ValueError("EXHAUSTION_FOLLOWUPS_MUST_BE_ARRAY")
    if followups and planting["ordinary"] is None:
        raise ValueError("FOLLOWUP_REQUIRES_FIRST_ORDINARY")
    followup_positions = [seed_position(item, ("page", "slot"), f"ordinary_after_exhaustion[{index}]")
                          for index, item in enumerate(followups)]
    daily = plan_object(selected["daily"], DAILY_ACTIONS, f"{platform}.daily")
    if any(type(flag) is not bool for flag in daily.values()):
        raise ValueError(f"{platform}.daily fields must be true or false")
    if not isinstance(planting["special"], list):
        raise ValueError(f"{platform}.planting.special must be an array")
    special = [seed_position(item, ("plot", "page", "slot"), f"{platform}.planting.special[{index}]")
               for index, item in enumerate(planting["special"])]
    ordinary = planting["ordinary"]
    if ordinary is not None:
        ordinary = seed_position(ordinary, ("page", "slot"), f"{platform}.planting.ordinary")
    steps = planting_steps(special, ordinary, policy, followup_positions)
    if followups:
        entries = [planting["ordinary"], *followups]
        quantities = [item.get("quantity") for item in entries]
        capacity = 24 - sum(len(group) for _, _, _, group in steps if group)
        if any(type(q) is not int or q <= 0 for q in quantities) or sum(quantities) != capacity:
            raise ValueError("EXHAUSTION_QUANTITIES_MUST_FILL_REMAINING_FIELD")
    return steps, daily


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("qq", "wechat"), required=True)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN, help="Local operation-plan JSON file.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check-plan", action="store_true", help="Validate the plan without a farm window.")
    mode.add_argument("--execute", action="store_true", help="Post clicks. Default is a no-click preflight.")
    parser.add_argument("--registry", type=Path, default=ROOT / "_sandbox/farm_window_registry")
    parser.add_argument("--click-helper", type=Path, default=ROOT / "_sandbox/farm_click_batch")
    args = parser.parse_args()

    try:
        platform = args.platform
        layout = json.loads((ROOT / "data/ui-layout.json").read_text())
        steps, daily = read_plan(args.plan, platform, layout["plot_policy"])
        page_sizes = plan_page_sizes(args.plan, platform)
        result = {
            "platform": platform,
            "steps": [step[:3] for step in steps],
            "daily_pending": [key for key in DAILY_ACTIONS if daily[key]],
        }
        if args.check_plan or not steps:
            status = "plan_ok_no_click" if args.check_plan else "skipped_no_planting"
            print(json.dumps({"status": status, **result}))
            return 0

        scenes = json.loads((ROOT / "data/ui-anchors.json").read_text())["fixed_points"]["scenes"]
        config = layout["platforms"][platform]
        lands = dict(enumerate((p for row in config["confirmed_land_centers"]["points"] for p in row), 1))
        picker = scenes["planting-switch"]["platforms"][platform]
        prompt = scenes["planting-enable-prompt"]["platforms"][platform]
        special_confirm = scenes["special-confirm"]
        confirm = {
            "offset": special_confirm["platforms"][platform]["coverage_center_to_button_offset_xy"],
            "margin": special_confirm["direct_button_search_margin_xy"],
        }
        templates = {name: load_gray(TEMPLATES / f"{platform}-{name}.png")
                     for name in ("page-prefix", "enable-prompt", "special-confirm")}
        templates.update({state: load_gray(TEMPLATES.parent / "picker" / f"{platform}-one-key-{state}.png")
                          for state in ("on", "off")})

        registry = subprocess.run([str(args.registry), "--platform", platform],
                                  capture_output=True, text=True, check=True, timeout=5)
        payload = json.loads(registry.stdout)
        windows = [w for w in payload["windows"] if w["title"] == "QQ经典农场"]
        if payload["platform"] != platform or len(windows) != 1:
            raise ValueError("FARM_WINDOW_NOT_UNIQUE_FOR_PLATFORM")
        window = windows[0]
        sidebar_width = config.get("embedded_canvas", {}).get("left_sidebar_width", 0)
        canvas = farm_canvas(window, picker["canvas_size"], sidebar_width)
        frame = WindowFrame(window["owner"], window["title"], **canvas)
        target = {key: window[key] for key in ("window_id", "pid", "owner", "title")}
        target.update(frame=canvas, window_frame={key: window[key] for key in canvas})

        def click(point, delay):
            click_batch(args.click_helper, "--execute", target,
                        [{"x": point[0], "y": point[1], "delay_ms": delay}])

        def capture():
            gray = capture_window(frame, platform, layout).gray
            size = (canvas["width"], canvas["height"])
            if gray.shape[::-1] != size:
                gray = np.asarray(Image.fromarray(gray).resize(size, Image.Resampling.LANCZOS))
            return gray

        if args.execute:
            plant(click, capture, steps, lands, picker, prompt, confirm, templates, page_sizes)
            status = "planting_clicks_sent_unverified"
        else:
            click_batch(args.click_helper, "--preflight", target,
                        [{"x": lands[p][0], "y": lands[p][1], "delay_ms": 0} for p, _, _, _ in steps])
            status = "preflight_ok_no_click"
        print(json.dumps({"status": status, **result}))
        return 0
    except (FertilizerStop, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "stopped", "reason": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
