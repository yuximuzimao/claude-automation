#!/usr/bin/env python3
"""Run QQ white-radish planting-exp rounds from an already empty standard farm."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import tempfile
from time import sleep


ROOT = Path(__file__).resolve().parents[1]
RADISH_PAGE = 7
RADISH_SLOT = 4
RADISH_BATCH = 24
DEFAULT_ROUNDS = 5
POST_FERTILIZER_WAIT_SECONDS = 2.2


def radish_plan():
    return {
        "qq": {
            "planting": {"special": [], "ordinary": {"page": RADISH_PAGE, "slot": RADISH_SLOT}},
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    if not 1 <= args.rounds <= 5:
        print(json.dumps({"status": "stopped", "reason": "ROUNDS_MUST_BE_1_TO_5"}))
        return 2

    summary = {
        "rounds": args.rounds,
        "seeds_consumed": args.rounds * RADISH_BATCH,
        "planting_exp": args.rounds * RADISH_BATCH * 10,
        "round_order": ["plant", "ordinary_fertilizer", "harvest"],
    }
    if not args.execute:
        print(json.dumps({"status": "plan_ok_no_click", **summary}))
        return 0

    try:
        with tempfile.TemporaryDirectory(prefix="farm-radish-plan-") as directory:
            plan = Path(directory) / "operation-plan.json"
            plan.write_text(json.dumps(radish_plan(), ensure_ascii=False), encoding="utf-8")
            completed = []
            for number in range(1, args.rounds + 1):
                run_script("farm_plant_once.py", "--platform", "qq", "--plan", str(plan), "--execute")
                run_script("farm_fertilize_once.py", "--platform", "qq", "--execute")
                sleep(POST_FERTILIZER_WAIT_SECONDS)
                run_script("farm_harvest_once.py", "--platform", "qq", "--execute")
                completed.append(number)
        print(json.dumps({"status": "radish_rounds_sent", "completed_rounds": completed, **summary}))
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "stopped", "reason": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
