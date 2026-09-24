from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.generated_artifacts import read_generated_artifact, write_generated_artifact
from lib.route_profiles import load_route_profile
from lib.route_xp import evaluate_profile_xp
from lib.task_cards import load_task_card


def _runtime(path: Path | None) -> dict:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("XP runtime input must be a JSON object")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Recompute only one Profile XP artifact. Requires current Replay. "
            "Optional runtime JSON may provide entry_state and external_xp_upper_bound_by_character."
        )
    )
    parser.add_argument("profile_id")
    parser.add_argument("--runtime-input", type=Path)
    args = parser.parse_args()

    profile = load_route_profile(args.profile_id, validate=True, validate_task_cards=False)
    cards = {int(task_id): load_task_card(int(task_id), validate=True) for task_id in profile["task_ids"]}
    replay = read_generated_artifact(
        scope_kind="profiles", scope_id=args.profile_id, artifact_kind="replay"
    )
    runtime = _runtime(args.runtime_input)

    payload = evaluate_profile_xp(
        profile,
        task_cards=cards,
        action_execution=dict(replay.get("action_execution") or {}),
        deferred_gates=list((replay.get("availability") or {}).get("deferred_gates") or []),
        entry_state=runtime.get("entry_state"),
        external_xp_upper_bound_by_character=runtime.get("external_xp_upper_bound_by_character"),
    )
    path = write_generated_artifact(
        scope_kind="profiles",
        scope_id=args.profile_id,
        artifact_kind="xp",
        owner="route_xp",
        payload=payload,
    )
    print(json.dumps({"status": payload["status"], "path": str(path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
