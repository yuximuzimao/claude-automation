from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "data/observations/route-timing-runs.json"
OUT = ROOT / "data/observations/route-timing-observations.json"

ROUTE_KEY_TO_PROFILE = {
    "nagrand": "nagrand-fivebox-67-68",
    "borean": "borean-fivebox",
    "dragonblight": "dragonblight-fivebox",
    "grizzly": "grizzly-fivebox",
    "zuldrak": "zuldrak-fivebox",
    "storm": "storm-peaks-fivebox",
    "howling": "howling-fivebox",
    "sholazar": "sholazar-fivebox",
    "icecrown": "icecrown-fivebox",
    "hellfire_dk": "hellfire-dk-speed",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_label(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def _action_scope(row: dict[str, Any]) -> dict[str, Any] | None:
    start_action_id = row.get("start_action_id")
    end_action_id = row.get("end_action_id")
    if isinstance(start_action_id, str) and isinstance(end_action_id, str):
        return {"start_action_id": start_action_id, "end_action_id": end_action_id}
    return None


def build_payload(source: Path = LEGACY) -> dict[str, Any]:
    raw = json.loads(source.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for index, run in enumerate(raw.get("runs") or [], 1):
        route_key = str(run.get("route_key") or "")
        profile_id = run.get("profile_id") or ROUTE_KEY_TO_PROFILE.get(route_key)
        profile_version = run.get("profile_version")
        action_scope = _action_scope(run)
        clean = run.get("actual_contains_learning_or_route_errors") is False
        exact_profile_contract = isinstance(profile_id, str) and isinstance(profile_version, int)
        stable_scope = action_scope is not None
        calibration_eligible = bool(clean and exact_profile_contract and stable_scope)
        rows.append(
            {
                "observation_id": f"legacy-route-run-{index:03d}",
                "profile_id": profile_id,
                "profile_version": profile_version,
                "program_id": run.get("program_id"),
                "program_version": run.get("program_version"),
                "action_scope": action_scope,
                "actual_minutes": run.get("actual_minutes"),
                "time_precision": run.get("time_precision"),
                "clean": clean,
                "calibration_eligible": calibration_eligible,
                "ineligibility_reasons": [
                    reason
                    for reason, present in (
                        ("contains_learning_or_route_errors", not clean),
                        ("profile_version_missing", not isinstance(profile_version, int)),
                        ("stable_action_scope_missing", action_scope is None),
                        ("profile_mapping_missing", not isinstance(profile_id, str)),
                    )
                    if present
                ],
                "source_route_key": route_key or None,
                "source_record": run,
            }
        )
    return {
        "schema_version": 1,
        "observation_set_id": "route-timing-observations-v1",
        "source": {
            "path": _source_label(source),
            "sha256": _sha256(source),
            "policy": (
                "Legacy runs are preserved verbatim as evidence. Only clean observations with exact "
                "Profile version and stable action-id scope may calibrate current Derived Timing."
            ),
        },
        "observations": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Split pure Timing Observations from the legacy mixed timing-runs file.")
    parser.add_argument("--source", type=Path, default=LEGACY)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    payload = build_payload(args.source)
    summary = {
        "observation_count": len(payload["observations"]),
        "calibration_eligible_count": sum(1 for row in payload["observations"] if row["calibration_eligible"]),
        "output": str(args.out),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.write:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
