#!/usr/bin/env python3
"""Read-only farm UI probe.

Input is a screenshot of the farm game canvas/window. The script performs no clicks.
It reports:
- dynamic global-action anchors
- fertilizer normal/advanced click candidates
- all current 4-plot “可摘” markers
- all 24 plot centers and prevalidated special-seed 2×2 anchors

The caller remains responsible for state-machine decisions and CGEvent clicks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from anchor_locator import load_gray, normalized_cross_correlation, scaled
from pickable_locator import locate_pickables


ROOT = Path(__file__).resolve().parents[1]


def best_match(image: np.ndarray, template: np.ndarray, roi, scales):
    x, y, w, h = roi
    search = image[y : y + h, x : x + w]
    best = None

    for scale in scales:
        candidate_template = scaled(template, scale)
        scores = normalized_cross_correlation(search, candidate_template)
        if scores is None:
            continue
        iy, ix = np.unravel_index(np.argmax(scores), scores.shape)
        score = float(scores[iy, ix])
        candidate = {
            "score": score,
            "x": int(x + ix),
            "y": int(y + iy),
            "w": int(candidate_template.shape[1]),
            "h": int(candidate_template.shape[0]),
            "center_x": float(x + ix + candidate_template.shape[1] / 2),
            "center_y": float(y + iy + candidate_template.shape[0] / 2),
            "scale": scale,
        }
        if best is None or score > best["score"]:
            best = candidate

    return best


def normalized_roi(spec, width, height):
    x, y, w, h = spec
    return (
        int(round(x * width)),
        int(round(y * height)),
        int(round(w * width)),
        int(round(h * height)),
    )


def grid_centers(layout, width, height):
    ox, oy = layout["normalized_origin"]
    ux, uy = layout["normalized_u_step"]
    vx, vy = layout["normalized_v_step"]

    result = []
    for u in range(6):
        for v in range(4):
            result.append(
                {
                    "u": u,
                    "v": v,
                    "x": (ox + u * ux + v * vx) * width,
                    "y": (oy + u * uy + v * vy) * height,
                }
            )
    return result


def special_2x2_anchors(layout, width, height):
    ox, oy = layout["normalized_origin"]
    ux, uy = layout["normalized_u_step"]
    vx, vy = layout["normalized_v_step"]
    result = []
    for item in layout.get("safe_special_2x2", []):
        u, v = item["anchor_cell"]
        result.append({
            "id": item["id"],
            "grade": item["grade"],
            "anchor_cell": [u, v],
            "x": (ox + u * ux + v * vx) * width,
            "y": (oy + u * uy + v * vy) * height,
            "cells": item["cells"],
        })
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("screenshot", help="farm window/canvas screenshot")
    parser.add_argument("--platform", choices=["qq", "wechat"], required=True)
    args = parser.parse_args()

    image = load_gray(args.screenshot)
    height, width = image.shape

    anchors_cfg = json.loads((ROOT / "data/ui-anchors.json").read_text())
    layout_cfg = json.loads((ROOT / "data/ui-layout.json").read_text())

    baseline_w, baseline_h = layout_cfg["platforms"][args.platform]["baseline_window_size"]
    scale_x = width / baseline_w
    scale_y = height / baseline_h
    if not (0.70 <= scale_x <= 1.40 and 0.70 <= scale_y <= 1.40):
        raise SystemExit(
            f"input {width}x{height} does not look like a cropped {args.platform} farm window; "
            f"baseline is {baseline_w}x{baseline_h}"
        )
    if abs(scale_x - scale_y) / max(scale_x, scale_y) > 0.20:
        raise SystemExit(
            f"non-uniform farm-window scaling is too large: x={scale_x:.3f}, y={scale_y:.3f}"
        )

    scales = anchors_cfg["matching"]["default_scales"]
    detected = {}

    for name, spec in anchors_cfg["anchors"].items():
        template = load_gray(str(ROOT / spec["template"]))
        roi = normalized_roi(spec["roi_normalized"], width, height)
        match = best_match(image, template, roi, scales)
        if match is None:
            detected[name] = {"matched": False, "score": -1.0}
            continue
        match["matched"] = match["score"] >= spec.get(
            "threshold", anchors_cfg["matching"]["default_threshold"]
        )
        detected[name] = match

    fert = detected.get("fertilizer_normal")
    fertilizer_actions = None
    if fert and fert.get("matched"):
        offset = anchors_cfg["anchors"]["fertilizer_normal"]["advanced_from_normal"]
        factor = fert["scale"] if offset.get("multiply_by_match_scale") else 1.0
        fertilizer_actions = {
            "normal": {
                "x": fert["center_x"],
                "y": fert["center_y"],
            },
            "advanced": {
                "x": fert["center_x"] + offset["base_dx_pixels"] * factor,
                "y": fert["center_y"] + offset["base_dy_pixels"] * factor,
            },
        }

    matched_global = [
        name
        for name in ("onekey_farm", "onekey_harvest")
        if detected.get(name, {}).get("matched")
    ]
    pickables = locate_pickables(image)
    harvest_plan = None
    if detected.get("onekey_harvest", {}).get("matched"):
        harvest_plan = {
            "pickable_count": pickables["count"],
            "actions": (
                ["click_all_pickables", "click_global_hand", "wait_3s", "verify_clean_land"]
                if pickables["count"] > 0
                else ["click_global_hand", "wait_3s", "verify_clean_land"]
            ),
        }

    output = {
        "platform": args.platform,
        "image_size": [width, height],
        "anchors": detected,
        "matched_global_actions": matched_global,
        "fertilizer_actions": fertilizer_actions,
        "pickables": pickables,
        "harvest_plan": harvest_plan,
        "grid_centers": grid_centers(
            layout_cfg["platforms"][args.platform], width, height
        ),
        "safe_special_2x2": special_2x2_anchors(
            layout_cfg["platforms"][args.platform], width, height
        ),
    }

    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
