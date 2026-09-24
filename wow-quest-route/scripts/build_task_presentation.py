from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.task_cards import load_task_card
from lib.task_presentation import project_task_presentation


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect/recompute exactly one Task Presentation to stdout. "
            "The formal incremental update path is update_route_display_task.py, which writes only "
            "through the generated store."
        )
    )
    parser.add_argument("task_id", type=int)
    parser.add_argument("--profile-id", required=True)
    args = parser.parse_args()

    card = load_task_card(args.task_id, validate=True)
    result = project_task_presentation(card, profile_id=args.profile_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
