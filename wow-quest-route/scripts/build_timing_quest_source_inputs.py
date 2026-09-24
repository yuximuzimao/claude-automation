from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.questie_objectives import build_effective_timing_source_inputs
from lib.task_cards import load_all_task_cards

DEFAULT_SOURCE = ROOT / "data/sources/questie/Questie.zip"
DEFAULT_OUT = ROOT / "data/timing/quest-source-inputs.json"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build Stage-7 Effective Quest Source timing inputs from the current Questie package. "
            "This derives only mechanical objective quantities/source relations and never reads Task Card guide or route prose."
        )
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--task-id", type=int, action="append", default=[])
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    if args.task_id:
        task_ids = sorted(set(args.task_id))
    else:
        task_ids = sorted(load_all_task_cards(validate=True))

    payload = build_effective_timing_source_inputs(args.source, task_ids)
    summary = {
        "status": payload["status"],
        "task_count": len(payload.get("tasks") or {}),
        "issue_count": len(payload.get("issues") or []),
        "source": payload.get("source"),
        "output": str(args.out),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.write:
        if payload["status"] == "requirements" and not (payload.get("source") or {}).get("exists"):
            raise SystemExit("Questie timing source is unavailable; refusing to write an empty authoritative cache")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
