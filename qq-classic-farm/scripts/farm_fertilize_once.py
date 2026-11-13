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
from farm_level_up import dismiss_level_up


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "assets/ui"


class FertilizerStop(RuntimeError):
    pass


def require_wechat_live():
    try:
        status = (ROOT / "data/wechat-live-status.txt").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        status = None
    if status != "active":
        raise FertilizerStop("WECHAT_FARM_SEALED")


def template_center(region, template, origin, threshold):
    scores = normalized_cross_correlation(region, template)
    if scores is None:
        raise FertilizerStop("INVALID_FERTILIZER_TEMPLATE")
    y, x = np.unravel_index(scores.argmax(), scores.shape)
    if scores[y, x] < threshold:
        return None
    height, width = template.shape
    return (origin[0] + x + width / 2, origin[1] + y + height / 2)


def fertilize_once(click, locate, land, after_work=lambda: None):
    work = locate("work")
    if work is not None:
        click(work, 1000)
        after_work()
    click(land, 350)
    checked, checkbox, fertilizer = locate("panel")
    if not checked:
        click(checkbox, 350)
        confirm = locate("enable_prompt")
        if confirm is None:
            raise FertilizerStop("ONE_KEY_FERTILIZER_PROMPT_NOT_FOUND")
        click(confirm, 350)
        checked, _, fertilizer = locate("panel")
        if not checked:
            raise FertilizerStop("CHECKBOX_NOT_CONFIRMED")
    click(fertilizer, 0)
    return work is not None


def fertilizer_locator(capture, platform, spec, kind="ordinary"):
    templates = {name: load_gray(UI / "fertilizer" / f"{platform}-{name}.png")
                 for name in ("ordinary", "checkbox-off", "enable-prompt")}
    if kind == "organic":
        templates["organic"] = load_gray(UI / "fertilizer" / f"{platform}-organic.png")
    templates["tick"] = load_gray(UI / f"{platform}-fertilizer-onekey-tick.png")
    if platform == "qq":
        templates["work"] = load_gray(UI / "onekey-farm.png")[67:119, 22:78]
    else:
        templates["work"] = load_gray(UI / "fertilizer/wechat-onekey-work.png")

    work_rect = spec["work_rect"]
    prompt_rect = spec["prompt_rect"]
    bucket_rect = spec["organic_bucket_rect"] if kind == "organic" else spec["bucket_rect"]
    checkbox_rect = spec["checkbox_rect"]
    panel_rect = (min(bucket_rect[0], checkbox_rect[0]), min(bucket_rect[1], checkbox_rect[1]),
                  max(bucket_rect[2], checkbox_rect[2]), max(bucket_rect[3], checkbox_rect[3]))

    def panel_match(image, rect, name, threshold):
        x0, y0, x1, y1 = rect
        x, y = panel_rect[:2]
        return template_center(image[y0-y:y1-y, x0-x:x1-x], templates[name], rect[:2], threshold)

    def locate(request):
        if request == "work":
            return template_center(capture(work_rect), templates["work"], work_rect[:2], 0.86)
        if request == "enable_prompt":
            prompt = template_center(capture(prompt_rect), templates["enable-prompt"], prompt_rect[:2], 0.94)
            return spec["confirm_point"] if prompt is not None else None

        image = capture(panel_rect)
        fertilizer = panel_match(image, bucket_rect, kind, 0.90)
        if fertilizer is None:
            raise FertilizerStop(f"{kind.upper()}_FERTILIZER_NOT_FOUND")
        tick = panel_match(image, checkbox_rect, "tick", 0.92)
        unchecked = panel_match(image, checkbox_rect, "checkbox-off", 0.90)
        if (tick is None) == (unchecked is None):
            raise FertilizerStop("FERTILIZER_CHECKBOX_STATE_UNKNOWN")
        return tick is not None, unchecked, fertilizer

    return locate


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


def capture_region(canvas, region):
    x0, y0, x1, y1 = region
    if not (0 <= x0 < x1 <= canvas["width"] and 0 <= y0 < y1 <= canvas["height"]):
        raise FertilizerStop("CAPTURE_REGION_OUTSIDE_WINDOW")
    x, y = canvas["x"] + x0, canvas["y"] + y0
    if x != round(x) or y != round(y):
        raise FertilizerStop("NONINTEGRAL_CAPTURE_ORIGIN")
    size = (x1 - x0, y1 - y0)
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
                raise FertilizerStop("INVALID_REGION_CAPTURE")
            return np.asarray(image.convert("L"), dtype=np.float32)


def click_batch(helper, mode, target, actions, *, wechat_main=False, qq_share=False, managed=False):
    if mode == "--execute" and target["owner"] in ("微信", "WeChat"):
        require_wechat_live()
    command = [str(helper), mode]
    if wechat_main:
        command.append("--wechat-main")
    if qq_share:
        command.append("--qq-share")
    payload = json.dumps({**target, "actions": actions})
    if managed and mode == "--execute":
        from farm_process import run_action
        result = run_action(command, input=payload, timeout=5)
    else:
        result = subprocess.run(command, input=payload, text=True, capture_output=True, timeout=5)
    reply = json.loads(result.stdout)
    if not isinstance(reply, dict):
        raise FertilizerStop("UNEXPECTED_CLICK_HELPER_RESULT")
    if result.returncode:
        raise FertilizerStop(reply.get("code", "CLICK_HELPER_FAILED"))
    expected = ("clicks_sent_unverified", len(actions)) if mode == "--execute" else ("preflight_ok_no_click", 0)
    if (reply.get("status"), reply.get("click_count")) != expected:
        raise FertilizerStop("UNEXPECTED_CLICK_HELPER_RESULT")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("qq", "wechat"), required=True)
    parser.add_argument("--kind", choices=("ordinary", "organic"), default="ordinary")
    parser.add_argument("--execute", action="store_true", help="Post clicks. Default is a no-click preflight.")
    parser.add_argument("--registry", type=Path, default=ROOT / "_sandbox/farm_window_registry")
    parser.add_argument("--click-helper", type=Path, default=ROOT / "_sandbox/farm_click_batch")
    args = parser.parse_args()

    try:
        platform = args.platform
        if args.kind == "organic" and platform != "qq":
            raise FertilizerStop("ORGANIC_TEMPLATE_NOT_VERIFIED_FOR_PLATFORM")
        layout = json.loads((ROOT / "data/ui-layout.json").read_text())
        anchors = json.loads((ROOT / "data/ui-anchors.json").read_text())
        config = layout["platforms"][platform]
        land = config["confirmed_land_centers"]["points"][0][0]
        scene = anchors["fixed_points"]["scenes"]["fertilizer-switch"]
        view = scene["views"]["onekey"]
        points = {point["id"]: point[platform] for point in view["points"]}
        checkbox = points["onekey-fertilizer"]
        fertilizer = points["advanced-fertilizer" if args.kind == "organic" else "ordinary-fertilizer"]

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
            locate = fertilizer_locator(lambda rect: capture_region(canvas, rect), platform, scene["recognition"][platform], args.kind)
            def after_work():
                if platform == "qq":
                    dismiss_level_up(lambda rect: capture_region(canvas, rect), click)

            worked = fertilize_once(click, locate, land, after_work)
            result = {"status": "fertilizer_click_sent", "onekey_work_clicked": worked, "kind": args.kind}
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
