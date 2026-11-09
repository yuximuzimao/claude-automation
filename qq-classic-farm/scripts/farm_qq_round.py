#!/usr/bin/env python3
"""Run the QQ in-farm round after the user has confirmed the mini-program is open."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from time import sleep


ROOT = Path(__file__).resolve().parents[1]
POST_INITIAL_FERTILIZER_WAIT_SECONDS = 2.2


def command(script, *args):
    return ["python3.13", str(ROOT / "scripts" / script), *args]


def workflow(radish_rounds, harvest_plan, *, field_state="tail", tasks=True, friends=True, reward=True):
    if field_state not in ("tail", "mature", "empty") or not 0 <= radish_rounds <= 5:
        raise ValueError("INVALID_FIELD_STATE_OR_RADISH_ROUNDS")
    steps = []
    if field_state == "tail":
        steps += [command("farm_fertilize_once.py", "--platform", "qq", "--execute"),
                  ("sleep", POST_INITIAL_FERTILIZER_WAIT_SECONDS)]
    if field_state != "empty":
        steps.append(command("farm_harvest_once.py", "--platform", "qq", "--planted-plan", str(harvest_plan), "--execute"))
    if radish_rounds:
        steps.append(command("farm_radish_xp.py", "--rounds", str(radish_rounds), "--execute"))
    steps.append(command("farm_plant_once.py", "--platform", "qq", "--execute"))
    if tasks:
        steps.append(command("farm_daily_task_once.py", "--platform", "qq", "--execute"))
    if friends:
        steps.append(command("farm_friend_sweep.py", "--platform", "qq", "--execute"))
    if reward:
        steps.append(command("farm_daily_fertilizer_reward.py", "--platform", "qq", "--execute"))
    return steps


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--radish-rounds", type=int, choices=range(6), default=0)
    parser.add_argument("--field-state", choices=("tail", "mature", "empty"), required=True)
    parser.add_argument("--tasks", action="store_true")
    parser.add_argument("--friends", action="store_true")
    parser.add_argument("--reward", action="store_true")
    parser.add_argument("--harvest-plan", type=Path, default=ROOT / "data/operation-plan.json")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    steps = workflow(args.radish_rounds, args.harvest_plan, field_state=args.field_state, tasks=args.tasks, friends=args.friends, reward=args.reward)
    if not args.execute:
        printable = [
            {"sleep_seconds": step[1]} if isinstance(step, tuple) else {"command": step[2:]}
            for step in steps
        ]
        print(json.dumps({
            "status": "plan_ok_no_click",
            "scope": "farm_already_open_to_actions_complete",
            "steps": printable,
            "post_actions": ["close mini-program outside this script", "inventory bookkeeping", "create harvest reminder"],
        }, ensure_ascii=False))
        return 0

    completed = []
    for step in steps:
        if isinstance(step, tuple):
            sleep(step[1])
            continue
        result = subprocess.run(step, capture_output=True, text=True, timeout=420)
        name = Path(step[1]).name
        if result.returncode:
            print(json.dumps({
                "status": "awaiting_empty_entry" if result.returncode == 3 and name == "farm_plant_once.py" else "stopped",
                "failed_stage": name,
                "completed_stages": completed,
                "detail": result.stdout.strip() or result.stderr.strip(),
            }, ensure_ascii=False))
            return 2
        completed.append(name)

    print(json.dumps({"status": "qq_round_actions_sent", "completed_stages": completed}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
