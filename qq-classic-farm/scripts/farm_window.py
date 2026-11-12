#!/usr/bin/env python3
"""Open or close the desktop mini-program through its verified window controls."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from time import monotonic, sleep

from anchor_locator import load_gray
from farm_fertilize_once import (
    FertilizerStop, capture_region, click_batch, farm_canvas, require_wechat_live, template_center,
)


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "assets/ui/window"
FARM_TITLE = "QQ经典农场"
WECHAT_TITLES = {"微信", "WeChat"}
FRAME_KEYS = ("x", "y", "width", "height")


def locate(canvas, name, rect, threshold):
    return template_center(
        capture_region(canvas, rect), load_gray(TEMPLATES / f"{name}.png"), rect[:2], threshold,
    )


def wechat_entry(canvas):
    if locate(canvas, "wechat-recent-header", (384, 80, 478, 123), 0.88) is None:
        return None
    return locate(canvas, "wechat-recent-farm", (399, 115, 967, 185), 0.94)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("open", "close"))
    parser.add_argument("--platform", required=True, choices=("qq", "wechat"))
    parser.add_argument("--execute", action="store_true", help="Operate the mini-program. Default is read-only.")
    parser.add_argument("--registry", type=Path, default=ROOT / "_sandbox/farm_window_registry")
    parser.add_argument("--click-helper", type=Path, default=ROOT / "_sandbox/farm_click_batch")
    args = parser.parse_args()
    platform = args.platform
    mode = "--execute" if args.execute else "--preflight"

    def windows():
        result = subprocess.run([str(args.registry), "--platform", platform], capture_output=True,
                                text=True, check=True, timeout=3)
        payload = json.loads(result.stdout)
        if payload["platform"] != platform:
            raise ValueError("REGISTRY_PLATFORM_MISMATCH")
        return payload["windows"]

    def find_full(title_set, dims):
        matches = [w for w in windows() if w["title"] in title_set and (w["width"], w["height"]) in dims]
        if len(matches) > 1:
            raise ValueError("WINDOW_NOT_UNIQUE")
        return matches[0] if matches else None

    def wait_for(find, reason):
        end = monotonic() + 4
        while monotonic() < end:
            window = find()
            if window:
                return window
            sleep(0.10)
        raise ValueError(reason)

    def click(window, canvas, point, delay=0, *, wechat_main=False):
        target = {key: window[key] for key in ("window_id", "pid", "owner", "title")}
        target["frame"] = canvas
        if not wechat_main:
            target["window_frame"] = {key: window[key] for key in FRAME_KEYS}
        click_batch(args.click_helper, mode, target,
                    [{"x": point[0], "y": point[1], "delay_ms": delay}], wechat_main=wechat_main)

    try:
        if args.execute and platform == "wechat":
            require_wechat_live()
        layout = json.loads((ROOT / "data/ui-layout.json").read_text())
        config = layout["platforms"][platform]
        width, height = config["baseline_window_size"]
        sidebar = config.get("embedded_canvas", {}).get("left_sidebar_width", 0)
        dims = {(width, height), (width + sidebar, height)}

        def find_farm():
            return find_full({FARM_TITLE}, dims)

        farm = find_farm()
        if args.action == "close":
            if farm is None:
                raise ValueError("STANDARD_FARM_WINDOW_NOT_FOUND")
            canvas = farm_canvas(farm, (width, height), sidebar)
            point = locate(canvas, f"{platform}-close", (width - 54, 0, width, 40), 0.96)
            if point is None:
                raise ValueError("FARM_CLOSE_CONTROL_NOT_FOUND")
            click(farm, canvas, point)
            status = "close_preflight_ok_no_click"
            if args.execute:
                wait_for(lambda: not any(w["title"] == FARM_TITLE for w in windows()), "FARM_STILL_OPEN")
                status = "farm_closed"
        elif farm is not None:
            status = "farm_window_already_present"
        elif platform == "qq":
            status = "qq_open_delegates_to_existing_entry"
            if args.execute:
                subprocess.run(["/usr/bin/swift", str(ROOT / "scripts/open_qq_farm.swift")],
                               capture_output=True, text=True, check=True, timeout=20)
                wait_for(find_farm, "STANDARD_FARM_WINDOW_NOT_FOUND")
                status = "farm_opened"
        else:
            def find_main():
                return find_full(WECHAT_TITLES, {(1007, 974), (1008, 974)})

            if args.execute:
                if not any(w["title"] in WECHAT_TITLES for w in windows()):
                    raise ValueError("WECHAT_MAIN_WINDOW_NOT_FOUND")
                subprocess.run(["/usr/bin/open", "-a", "WeChat"], check=True, timeout=4)
                main_window = wait_for(find_main, "WECHAT_MAIN_WINDOW_NOT_AT_STANDARD_SIZE")
            else:
                main_window = find_main()
                if main_window is None:
                    raise ValueError("WECHAT_MAIN_WINDOW_NOT_AT_STANDARD_SIZE")
            canvas = {key: main_window[key] for key in FRAME_KEYS}
            point = wechat_entry(canvas)
            if point is None:
                discover = locate(canvas, "wechat-discover", (13, 248, 49, 283), 0.87)
                if discover is None:
                    raise ValueError("WECHAT_DISCOVER_OR_RECENT_ENTRY_NOT_FOUND")
                click(main_window, canvas, discover, 500, wechat_main=True)
                if args.execute:
                    main_window = find_main()
                    if main_window is None:
                        raise ValueError("WECHAT_MAIN_WINDOW_CHANGED")
                    canvas = {key: main_window[key] for key in FRAME_KEYS}
                    point = wechat_entry(canvas)
                    if point is None:
                        raise ValueError("WECHAT_RECENT_FARM_ENTRY_NOT_FOUND")
            status = "wechat_discover_preflight_ok_no_click"
            if point is not None:
                click(main_window, canvas, point, wechat_main=True)
                status = "wechat_recent_preflight_ok_no_click"
                if args.execute:
                    wait_for(find_farm, "STANDARD_FARM_WINDOW_NOT_FOUND")
                    status = "farm_opened"
        print(json.dumps({"status": status, "platform": platform}))
        return 0
    except (FertilizerStop, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        failure = {"status": "stopped", "platform": platform, "reason": str(exc)}
        if isinstance(exc, (subprocess.CalledProcessError, subprocess.TimeoutExpired)):
            def readable(value):
                return value.decode("utf-8", "replace") if isinstance(value, bytes) else (value or "")
            stdout, stderr = readable(exc.stdout).strip(), readable(exc.stderr).strip()
            failure.update(command=exc.cmd, child_stdout=stdout, child_stderr=stderr)
            if isinstance(exc, subprocess.CalledProcessError):
                failure["child_returncode"] = exc.returncode
                failure["reason"] = stderr or stdout or str(exc)
            else:
                failure["reason"] = "CHILD_PROCESS_TIMEOUT"
                failure["timeout_seconds"] = exc.timeout
        print(json.dumps(failure, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
