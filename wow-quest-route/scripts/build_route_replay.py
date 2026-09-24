from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.character_profiles import load_character_profile
from lib.generated_artifacts import write_generated_artifact
from lib.route_dependencies import canonical_json_hash
from lib.route_profiles import load_route_profile
from lib.route_replay import replay_route_profile, replay_summary
from lib.task_cards import load_task_card


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recompute only one Profile Replay/Availability artifact."
    )
    parser.add_argument("profile_id")
    args = parser.parse_args()

    profile = load_route_profile(args.profile_id, validate=True, validate_task_cards=False)
    cards = {int(task_id): load_task_card(int(task_id), validate=True) for task_id in profile["task_ids"]}
    character_profile_id = profile["scope"]["character_profile"]
    character_profile = load_character_profile(character_profile_id, validate=True)

    replay = replay_route_profile(
        profile,
        task_cards=cards,
        character_profile=character_profile,
    )
    payload = replay_summary(replay)
    errors = [row for row in replay.issues if row.get("severity") == "error"]
    requirements = [row for row in replay.issues if row.get("severity") == "requirement"]
    payload["kind"] = "route_replay"
    payload["status"] = (
        "blocked"
        if errors
        else "requirements"
        if requirements or replay.external_state_requirements
        else "pass"
    )
    payload["input_fingerprint"] = canonical_json_hash(
        {
            "profile_id": profile["profile_id"],
            "profile_version": profile["version"],
            "profile_actions": profile["actions"],
            "entry_requirements": profile["entry_requirements"],
            "task_cards": cards,
            "character_profile": character_profile,
        }
    )

    path = write_generated_artifact(
        scope_kind="profiles",
        scope_id=args.profile_id,
        artifact_kind="replay",
        owner="route_replay",
        payload=payload,
    )
    print(json.dumps({"status": payload["status"], "path": str(path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
