from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "data/timing/model-config.json"
PROFILE_DIR = ROOT / "data/route-profiles"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _root_step(step_id: str) -> str:
    match = re.match(r"^(step-\d+)", step_id)
    return match.group(1) if match else step_id


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Invalidate legacy root-step baselines whenever the current Profile splits that root into multiple step groups."
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    config = _load(CONFIG_PATH)
    baselines = config.get("legacy_step_baselines") or {}
    changes: list[dict[str, Any]] = []

    for profile_path in sorted(PROFILE_DIR.glob("*.json")):
        if profile_path.name == "schema.json":
            continue
        profile_id = profile_path.stem
        baseline = baselines.get(profile_id)
        if not isinstance(baseline, dict):
            continue
        profile = _load(profile_path)
        root_members: dict[str, list[str]] = {}
        for step in profile.get("step_groups") or []:
            step_id = str(step["step_id"])
            root_members.setdefault(_root_step(step_id), []).append(step_id)
        split_roots = sorted(root for root, members in root_members.items() if len(members) > 1)
        if not split_roots:
            continue
        before = [str(value) for value in baseline.get("invalidated_step_ids") or []]
        after = sorted(set(before) | set(split_roots))
        if after == before and baseline.get("migration_policy") == "legacy_center_and_range_residual_only_for_unchanged_step_contracts":
            continue
        changes.append(
            {
                "profile_id": profile_id,
                "split_roots": split_roots,
                "invalidated_before": before,
                "invalidated_after": after,
            }
        )
        if args.write:
            baseline["migration_policy"] = "legacy_center_and_range_residual_only_for_unchanged_step_contracts"
            baseline["invalidated_step_ids"] = after

    if args.write and changes:
        CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"write": args.write, "changes": changes}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
