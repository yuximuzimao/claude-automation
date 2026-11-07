#!/usr/bin/env python3
"""Apply ordinary fertilizer once from the already aligned farm home screen."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import tempfile

import numpy as np
from PIL import Image

from anchor_locator import load_gray, normalized_cross_correlation


ROOT = Path(__file__).resolve().parents[1]
CHECKBOX_WIDTH, CHECKBOX_HEIGHT = 36, 34
TICK_THRESHOLD = 0.92


class FertilizerStop(RuntimeError):
    pass


def tick_score(region, template):
    if region.shape != (CHECKBOX_HEIGHT, CHECKBOX_WIDTH):
        raise FertilizerStop("INVALID_CHECKBOX_CAPTURE")
    scores = normalized_cross_correlation(region, template)
    if scores is None:
        raise FertilizerStop("INVALID_TICK_TEMPLATE")
    return float(scores.max())


def fertilize_once(click, capture_checkbox, land, checkbox, fertilizer, template):
    click(land, 350)
    score = tick_score(capture_checkbox(), template)
    if score < TICK_THRESHOLD:
        click(checkbox, 180)
        score = tick_score(capture_checkbox(), template)
        if score < TICK_THRESHOLD:
            raise FertilizerStop("CHECKBOX_NOT_CONFIRMED")
    click(fertilizer, 0)
    return score


def farm_canvas(window, size, sidebar_width):
    width, height = size
    actual_width = window["width"]
    if window["height"] != height or actual_width not in (width, width + sidebar_width):
        raise FertilizerStop("WINDOW_SIZE_CHANGED")
    return {
        "x": window["x"] + actual_width - width,
        "y": window["y"],
        "width": width,
        "height": height,
    }


def checkbox_capture(canvas, checkbox):
    x = canvas["x"] + checkbox[0] - CHECKBOX_WIDTH // 2
    y = canvas["y"] + checkbox[1] - CHECKBOX_HEIGHT // 2
    if x != round(x) or y != round(y):
        raise FertilizerStop("NONINTEGRAL_CAPTURE_ORIGIN")
    size = (CHECKBOX_WIDTH, CHECKBOX_HEIGHT)
    rect = f"{round(x)},{round(y)},{size[0]},{size[1]}"
    with tempfile.TemporaryDirectory(prefix="farm-fertilizer-") as directory:
        path = Path(directory) / "checkbox.png"
        subprocess.run(
            ["/usr/sbin/screencapture", "-x", f"-R{rect}", str(path)],
            capture_output=True, check=True, timeout=5,
        )
        with Image.open(path) as image:
            if image.size == tuple(2 * dimension for dimension in size):
                image = image.resize(size, Image.Resampling.LANCZOS)
            if image.size != size:
                raise FertilizerStop("INVALID_CHECKBOX_CAPTURE")
            return np.asarray(image.convert("L"), dtype=np.float32)


def click_batch(helper, mode, target, actions):
    result = subprocess.run(
        [str(helper), mode],
        input=json.dumps({**target, "actions": actions}),
        text=True, capture_output=True, timeout=5,
    )
    reply = json.loads(result.stdout)
    if not isinstance(reply, dict):
        raise FertilizerStop("UNEXPECTED_CLICK_HELPER_RESULT")
    if result.returncode:
        raise FertilizerStop(reply.get("code", "CLICK_HELPER_FAILED"))
    expected = ("clicks_sent_unverified", 1) if mode == "--execute" else ("preflight_ok_no_click", 0)
    if (reply.get("status"), reply.get("click_count")) != expected:
        raise FertilizerStop("UNEXPECTED_CLICK_HELPER_RESULT")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("qq", "wechat"), required=True)
    parser.add_argument("--execute", action="store_true", help="Post clicks. Default is a no-click preflight.")
    parser.add_argument("--registry", type=Path, default=ROOT / "_sandbox/farm_window_registry")
    parser.add_argument("--click-helper", type=Path, default=ROOT / "_sandbox/farm_click_batch")
    args = parser.parse_args()

    try:
        platform = args.platform
        layout = json.loads((ROOT / "data/ui-layout.json").read_text())
        anchors = json.loads((ROOT / "data/ui-anchors.json").read_text())
        config = layout["platforms"][platform]
        land = config["confirmed_land_centers"]["points"][0][0]
        view = anchors["fixed_points"]["scenes"]["fertilizer-switch"]["views"]["onekey"]
        points = {point["id"]: point[platform] for point in view["points"]}
        checkbox = points["onekey-fertilizer"]
        fertilizer = points["ordinary-fertilizer"]
        template = load_gray(ROOT / "assets/ui" / f"{platform}-fertilizer-onekey-tick.png")

        registry = subprocess.run(
            [str(args.registry), "--platform", platform],
            capture_output=True, text=True, check=True, timeout=5,
        )
        windows = [w for w in json.loads(registry.stdout)["windows"] if w["title"] == "QQ经典农场"]
        if len(windows) != 1:
            raise FertilizerStop("FARM_WINDOW_NOT_UNIQUE")
        window = windows[0]
        sidebar_width = config.get("embedded_canvas", {}).get("left_sidebar_width", 0)
        canvas = farm_canvas(window, view["size"][platform], sidebar_width)
        target = {key: window[key] for key in ("window_id", "pid", "owner", "title")}
        target["window_frame"] = {key: window[key] for key in ("x", "y", "width", "height")}
        target["frame"] = canvas

        def click(point, delay):
            click_batch(args.click_helper, "--execute", target, [
                {"x": point[0], "y": point[1], "delay_ms": delay},
            ])

        if args.execute:
            score = fertilize_once(
                click, lambda: checkbox_capture(canvas, checkbox),
                land, checkbox, fertilizer, template,
            )
            result = {"status": "fertilizer_click_sent", "checkbox_score": round(score, 3)}
        else:
            click_batch(args.click_helper, "--preflight", target, [
                {"x": x, "y": y, "delay_ms": 0} for x, y in (land, checkbox, fertilizer)
            ])
            result = {"status": "preflight_ok_no_click"}
        print(json.dumps(result))
        return 0
    except (FertilizerStop, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "stopped", "reason": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
