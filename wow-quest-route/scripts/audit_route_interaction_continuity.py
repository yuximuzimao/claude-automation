from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.route_profiles import ROUTE_PROFILES_DIR, load_route_profile


def find_interaction_continuity_candidates(profile: dict) -> list[dict]:
    """Find same-NPC accept/turnin runs split only by other NPCs at one location.

    This is a local optimization review signal only. It never rewrites action order.
    """

    action_by_id = {str(action["action_id"]): action for action in profile["actions"]}
    candidates: list[dict] = []

    def eligible(action: dict, location_ref: str | None) -> bool:
        return (
            action.get("kind") in {"accept", "turnin"}
            and isinstance(action.get("npc_name"), str)
            and bool(action["npc_name"])
            and action.get("when") is None
            and action.get("location_ref") == location_ref
        )

    for step in profile["step_groups"]:
        actions = [action_by_id[str(action_id)] for action_id in step["action_ids"]]
        index = 0
        while index < len(actions):
            first = actions[index]
            location_ref = first.get("location_ref")
            if not eligible(first, location_ref):
                index += 1
                continue

            end = index
            segment: list[dict] = []
            while end < len(actions) and eligible(actions[end], location_ref):
                segment.append(actions[end])
                end += 1

            by_npc: dict[str, list[int]] = {}
            for offset, action in enumerate(segment):
                by_npc.setdefault(str(action["npc_name"]), []).append(offset)

            for npc_name, positions in by_npc.items():
                if len(positions) < 2:
                    continue
                if positions == list(range(positions[0], positions[-1] + 1)):
                    continue
                first_pos, last_pos = positions[0], positions[-1]
                candidates.append(
                    {
                        "step_id": step["step_id"],
                        "location_ref": location_ref,
                        "npc_name": npc_name,
                        "action_ids": [segment[pos]["action_id"] for pos in positions],
                        "intervening_action_ids": [
                            segment[pos]["action_id"]
                            for pos in range(first_pos + 1, last_pos)
                            if pos not in positions
                        ],
                    }
                )
            index = end

    return candidates


def _available_profile_ids() -> list[str]:
    return sorted(
        path.stem
        for path in Path(ROUTE_PROFILES_DIR).glob("*.json")
        if path.name != "schema.json"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only local route optimization check for same-NPC interaction continuity. "
            "Run after route design/reordering; findings require dependency/real-order review "
            "before editing the Route Profile."
        )
    )
    parser.add_argument("profile_ids", nargs="*", help="One or more Route Profile ids.")
    parser.add_argument("--all", action="store_true", help="Audit every current Route Profile.")
    args = parser.parse_args()

    if args.all and args.profile_ids:
        parser.error("use profile_ids or --all, not both")
    if not args.all and not args.profile_ids:
        parser.error("specify at least one profile_id, or use --all")

    profile_ids = _available_profile_ids() if args.all else list(dict.fromkeys(args.profile_ids))
    available = set(_available_profile_ids())
    unknown = sorted(set(profile_ids) - available)
    if unknown:
        parser.error(f"unknown profile_ids: {unknown}")

    reports = []
    for profile_id in profile_ids:
        profile = load_route_profile(profile_id, validate=True, validate_task_cards=False)
        candidates = find_interaction_continuity_candidates(profile)
        reports.append(
            {
                "profile_id": profile_id,
                "candidate_count": len(candidates),
                "candidates": candidates,
            }
        )

    print(
        json.dumps(
            {
                "kind": "route_interaction_continuity_review",
                "profile_count": len(reports),
                "candidate_count": sum(row["candidate_count"] for row in reports),
                "profiles": reports,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
