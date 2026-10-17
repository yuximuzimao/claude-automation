from __future__ import annotations

import argparse
import json
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _root_step(step_id: str) -> str:
    match = re.match(r"^(step-\d+)", step_id)
    return match.group(1) if match else step_id


def _sum_optional(values: list[float | None]) -> float | None:
    return sum(float(value) for value in values) if all(value is not None for value in values) else None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare current Route Timing logical blocks with the configured legacy step baseline."
    )
    parser.add_argument("profile_id")
    parser.add_argument("--through", help="Optional logical root step, e.g. step-13; rows after it are omitted.")
    args = parser.parse_args()

    timing_path = ROOT / "data/generated/route-lifecycle/profiles" / args.profile_id / "timing.json"
    timing = _load(timing_path)
    model_config = _load(ROOT / "data/timing/model-config.json")
    legacy_profile = ((model_config.get("legacy_step_baselines") or {}).get(args.profile_id) or {})
    legacy_steps = legacy_profile.get("steps") or {}
    invalidated = {str(value) for value in legacy_profile.get("invalidated_step_ids") or []}

    grouped: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for step in timing.get("steps") or []:
        grouped.setdefault(_root_step(str(step["step_id"])), []).append(step)

    rows = []
    cumulative_current: float | None = 0.0
    cumulative_legacy: float | None = 0.0
    for root_step, members in grouped.items():
        current_center = _sum_optional([row.get("center_minutes") for row in members])
        current_low = _sum_optional([
            (row.get("range_minutes") or [None, None])[0] if row.get("range_minutes") else None
            for row in members
        ])
        current_high = _sum_optional([
            (row.get("range_minutes") or [None, None])[1] if row.get("range_minutes") else None
            for row in members
        ])
        legacy = legacy_steps.get(root_step) or {}
        legacy_center = legacy.get("center_minutes")
        legacy_range = legacy.get("range_minutes")

        if cumulative_current is not None and current_center is not None:
            cumulative_current += float(current_center)
        else:
            cumulative_current = None
        if cumulative_legacy is not None and legacy_center is not None:
            cumulative_legacy += float(legacy_center)
        else:
            cumulative_legacy = None

        rows.append(
            {
                "logical_step": root_step,
                "member_step_ids": [row["step_id"] for row in members],
                "titles": [row["title"] for row in members],
                "current_center_minutes": round(current_center, 3) if current_center is not None else None,
                "current_range_minutes": (
                    [round(current_low, 3), round(current_high, 3)]
                    if current_low is not None and current_high is not None
                    else None
                ),
                "legacy_center_minutes": legacy_center,
                "legacy_range_minutes": legacy_range,
                "legacy_invalidated": root_step in invalidated,
                "delta_center_minutes": (
                    round(float(current_center) - float(legacy_center), 3)
                    if current_center is not None and legacy_center is not None
                    else None
                ),
                "cumulative_current_minutes": (
                    round(cumulative_current, 3) if cumulative_current is not None else None
                ),
                "cumulative_legacy_minutes": (
                    round(cumulative_legacy, 3) if cumulative_legacy is not None else None
                ),
                "cumulative_delta_minutes": (
                    round(cumulative_current - cumulative_legacy, 3)
                    if cumulative_current is not None and cumulative_legacy is not None
                    else None
                ),
            }
        )
        if args.through and root_step == args.through:
            break

    print(
        json.dumps(
            {
                "profile_id": args.profile_id,
                "timing_status": timing.get("status"),
                "timing_complete": timing.get("complete"),
                "legacy_source_ref": legacy_profile.get("source_ref"),
                "rows": rows,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
