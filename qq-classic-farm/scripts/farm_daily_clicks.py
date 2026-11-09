"""Guarded click helper shared by the independent daily farm actions."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from farm_capture import capture_window
from farm_fertilize_once import FertilizerStop, click_batch, farm_canvas
from farm_geometry import WindowFrame
from farm_vision import match_anchor


ROOT = Path(__file__).resolve().parents[1]
RETURN_HOME_REGION = {"qq": (477, 770, 125, 140), "wechat": (501, 800, 123, 145)}


def find_point(points, platform, name):
    point = next((entry[platform] for entry in points if entry["id"] == name), None)
    if point is None:
        raise ValueError(f"POINT_UNAVAILABLE: {platform}/{name}")
    return point


def return_home_point(frame, platform, layout):
    x, y, width, height = RETURN_HOME_REGION[platform]
    result = match_anchor(capture_window(frame, platform, layout), {
        "template": f"assets/ui/daily/{platform}-return-home.png",
        "roi_normalized": [x / frame.width, y / frame.height, width / frame.width, height / frame.height],
        "threshold": 0.90,
    }, [1.0])
    if not result["matched"]:
        raise ValueError("FRIEND_RETURN_HOME_NOT_FOUND")
    return result["local_center"]


def farm_target(registry_binary, platform, layout):
    config = layout["platforms"][platform]
    registry = subprocess.run([str(registry_binary), "--platform", platform],
                              capture_output=True, text=True, check=True, timeout=5)
    payload = json.loads(registry.stdout)
    windows = [window for window in payload["windows"] if window["title"] == "QQ经典农场"]
    if payload["platform"] != platform or len(windows) != 1:
        raise ValueError("FARM_WINDOW_NOT_UNIQUE_FOR_PLATFORM")
    window = windows[0]
    sidebar = config.get("embedded_canvas", {}).get("left_sidebar_width", 0)
    canvas = farm_canvas(window, config["baseline_window_size"], sidebar)
    frame = WindowFrame(window["owner"], window["title"], **canvas)
    target = {key: window[key] for key in ("window_id", "pid", "owner", "title")}
    target.update(frame=canvas, window_frame={key: window[key] for key in canvas})
    return frame, target


def run_daily(description, steps_for):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--platform", required=True, choices=("qq", "wechat"))
    parser.add_argument("--execute", action="store_true", help="Post clicks. Default is a no-click preflight.")
    parser.add_argument("--registry", type=Path, default=ROOT / "_sandbox/farm_window_registry")
    parser.add_argument("--click-helper", type=Path, default=ROOT / "_sandbox/farm_click_batch")
    args = parser.parse_args()

    clicks_sent = 0
    try:
        platform = args.platform
        layout = json.loads((ROOT / "data/ui-layout.json").read_text())
        anchors = json.loads((ROOT / "data/ui-anchors.json").read_text())["fixed_points"]
        steps = steps_for(anchors, platform)
        frame, target = farm_target(args.registry, platform, layout)

        if args.execute:
            for point, delay in steps:
                if point is None:
                    point = return_home_point(frame, platform, layout)
                x, y = point
                click_batch(args.click_helper, "--execute", target, [{"x": x, "y": y, "delay_ms": delay}])
                clicks_sent += 1
            status = "daily_clicks_sent_unverified"
        else:
            click_batch(args.click_helper, "--preflight", target, [
                {"x": point[0], "y": point[1], "delay_ms": 0} for point, _ in steps if point is not None
            ])
            status = "preflight_ok_no_click"
        print(json.dumps({"status": status, "clicks_sent": clicks_sent}))
        return 0
    except (FertilizerStop, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "stopped", "reason": str(exc), "clicks_sent": clicks_sent}, ensure_ascii=False))
        return 2
