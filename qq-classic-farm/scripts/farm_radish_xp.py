#!/usr/bin/env python3
"""Run QQ white-radish planting-exp rounds from an already empty standard farm."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import subprocess
import tempfile
from time import sleep
from farm_process import MANAGED_ENV, ActionCancelled, ActionCleanupError, run_action


ROOT = Path(__file__).resolve().parents[1]
RADISH_BATCH = 24
DEFAULT_ROUNDS = 5
PROGRESS_PATH = ROOT / "data/qq-radish-progress.json"
POST_FERTILIZER_WAIT_SECONDS = 2.2


def radish_plan(catalog_path=ROOT / "data/seed-catalog.json"):
    catalog = json.loads(catalog_path.read_text())
    entries = [seed for seed in catalog["seeds"]
               if seed.get("observations", {}).get("qq", {}).get("quantity_latest_known", 0) > 0]
    entries.sort(key=lambda seed: (
        seed["observations"]["qq"]["latest_warehouse_position"]["page"],
        seed["observations"]["qq"]["latest_warehouse_position"]["slot"],
    ))
    index = next((i for i, seed in enumerate(entries) if seed["name"] == "白萝卜种子"), None)
    if index is None:
        raise ValueError("RADISH_NOT_IN_KNOWN_INVENTORY")
    page, slot = index // 5 + 1, index % 5 + 1
    page_items = min(5, len(entries) - (page - 1) * 5)
    return {
        "qq": {
            "planting": {"special": [], "ordinary": {"page": page, "slot": slot, "page_items": page_items}},
            "daily": {"tasks": False, "fertilizer_reward": False, "share": False},
        },
        "wechat": {
            "planting": {"special": [], "ordinary": None},
            "daily": {"tasks": False, "fertilizer_reward": False, "share": False},
        },
    }


def run_script(script, *arguments):
    result = subprocess.run(
        ["python3.13", str(ROOT / "scripts" / script), *arguments],
        capture_output=True, text=True, timeout=90,
    )
    if result.returncode:
        detail = result.stdout.strip() or result.stderr.strip() or f"exit={result.returncode}"
        raise RuntimeError(f"{script}: {detail}")
    return result.stdout.strip()


def load_progress(path, date):
    if not path.exists():
        return {"date": date, "completed_rounds": 0}
    value = json.loads(path.read_text())
    if value.get("date") != date:
        return {"date": date, "completed_rounds": 0}
    count = value.get("completed_rounds")
    if type(count) is not int or not 0 <= count <= DEFAULT_ROUNDS:
        raise ValueError("INVALID_RADISH_PROGRESS")
    return value


def save_progress(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, prefix=path.name,
                                     suffix=".tmp", delete=False) as stream:
        temp = Path(stream.name)
        try:
            json.dump(value, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    if json.loads(path.read_text()) != value:
        raise ValueError("RADISH_PROGRESS_READBACK_FAILED")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--progress-file", type=Path, default=PROGRESS_PATH)
    args = parser.parse_args()

    if not 1 <= args.rounds <= 5:
        print(json.dumps({"status": "stopped", "reason": "ROUNDS_MUST_BE_1_TO_5"}))
        return 2

    summary = {
        "rounds": args.rounds,
        "seeds_consumed": args.rounds * RADISH_BATCH,
        "planting_exp": args.rounds * RADISH_BATCH * 10,
        "round_order": ["plant", "ordinary_fertilizer", "organic_fertilizer", "harvest"],
    }
    if not args.execute:
        print(json.dumps({"status": "plan_ok_no_click", **summary}))
        return 0

    completed = []
    stage = "preflight"
    number = 0
    progress = None
    try:
        date = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
        progress = load_progress(args.progress_file, date)
        rounds = min(args.rounds, DEFAULT_ROUNDS - progress["completed_rounds"])
        with tempfile.TemporaryDirectory(prefix="farm-radish-plan-") as directory:
            plan = Path(directory) / "operation-plan.json"
            plan.write_text(json.dumps(radish_plan(), ensure_ascii=False), encoding="utf-8")
            for number in range(1, rounds + 1):
                stage = "plant"
                run_script("farm_plant_once.py", "--platform", "qq", "--plan", str(plan), "--execute")
                stage = "ordinary_fertilizer"
                run_script("farm_fertilize_once.py", "--platform", "qq", "--execute")
                sleep(POST_FERTILIZER_WAIT_SECONDS)
                stage = "organic_fertilizer"
                run_script("farm_fertilize_once.py", "--platform", "qq", "--kind", "organic", "--execute")
                sleep(POST_FERTILIZER_WAIT_SECONDS)
                stage = "harvest"
                run_script("farm_harvest_once.py", "--platform", "qq", "--ordinary-only", "--execute")
                stage = "save_progress"
                # Count only a harvest that returned success. An ambiguous round
                # stays uncounted; never infer success from a timeout or screenshot.
                harvest_date = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
                if progress["date"] != harvest_date:
                    progress = {"date": harvest_date, "completed_rounds": 0}
                progress["completed_rounds"] += 1
                progress["updated_at"] = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
                save_progress(args.progress_file, progress)
                completed.append(number)
        print(json.dumps({**summary, "status": "radish_rounds_sent", "completed_rounds": completed,
                          "rounds": len(completed), "seeds_consumed": len(completed) * RADISH_BATCH,
                          "planting_exp": len(completed) * RADISH_BATCH * 10,
                          "daily_completed_rounds": progress["completed_rounds"]}))
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "stopped", "reason": str(exc),
                          "completed_rounds": completed, "failed_round": number, "failed_stage": stage,
                          "progress_file": str(args.progress_file),
                          "unconfirmed_round_counts": False}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    if os.environ.get(MANAGED_ENV) == "1" or "--execute" not in sys.argv:
        raise SystemExit(main())
    try:
        result = run_action([sys.executable, __file__, *sys.argv[1:]], timeout=420)
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        raise SystemExit(result.returncode)
    except (subprocess.TimeoutExpired, ActionCancelled, ActionCleanupError, OSError) as exc:
        print(json.dumps({"status": "stopped", "reason": str(exc),
                          "progress_file": str(PROGRESS_PATH), "process_group_stopped": True}))
        raise SystemExit(2)
