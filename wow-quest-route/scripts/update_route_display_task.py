from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.generated_artifacts import read_generated_artifact, write_generated_artifact
from lib.route_display import refresh_task_card_display
from lib.task_cards import load_task_card
from lib.task_presentation import project_task_presentation


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Update one task's Presentation inside the current Route Display. "
            "Does not recompute Replay/Program/Movement/Service/Timing/XP/Economy."
        )
    )
    parser.add_argument("profile_id")
    parser.add_argument("task_id", type=int)
    parser.add_argument(
        "--identity-changed",
        action="store_true",
        help="Also update rendered task names inside action lines/task_refs.",
    )
    args = parser.parse_args()

    display = read_generated_artifact(
        scope_kind="profiles", scope_id=args.profile_id, artifact_kind="display"
    )
    card = load_task_card(args.task_id, validate=True)
    presentation = project_task_presentation(card, profile_id=args.profile_id)
    result = refresh_task_card_display(
        display,
        presentation,
        update_action_text=args.identity_changed,
    )
    path = write_generated_artifact(
        scope_kind="profiles",
        scope_id=args.profile_id,
        artifact_kind="display",
        owner="route_display",
        payload=result,
    )
    print(json.dumps({"status": result["status"], "path": str(path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
