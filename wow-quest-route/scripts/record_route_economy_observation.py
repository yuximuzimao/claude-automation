from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from lib.route_economy import ECONOMY_OBSERVATIONS, validate_economy_observations


def parse_asset(raw: str) -> dict[str, Any]:
    asset_id, separator, quantity_raw = raw.partition("=")
    if not separator or not asset_id.strip():
        raise ValueError("asset must use ASSET_ID=QUANTITY")
    quantity = float(quantity_raw)
    if quantity < 0:
        raise ValueError("asset quantity must be non-negative")
    return {"asset_id": asset_id.strip(), "quantity": quantity}


def build_observation(
    *,
    observation_id: str,
    target_kind: str,
    target_id: str,
    target_version: int,
    source_ref: str,
    raw_gold_delta_copper: int | None,
    assets: list[dict[str, Any]],
    clean: bool,
    contamination: list[str],
    character_id: str | None = None,
) -> dict[str, Any]:
    if target_kind not in {"profile", "program"}:
        raise ValueError("target_kind must be profile or program")
    if not target_id:
        raise ValueError("target_id is required")
    if target_version < 1:
        raise ValueError("target_version must be positive")
    if clean and contamination:
        raise ValueError("clean observation cannot contain contamination")
    if not clean and not contamination:
        raise ValueError("non-clean observation requires at least one contamination reason")
    if raw_gold_delta_copper is None and not assets:
        raise ValueError("observation requires raw gold delta or at least one asset quantity")

    target = (
        {"profile_id": target_id, "profile_version": target_version}
        if target_kind == "profile"
        else {"program_id": target_id, "program_version": target_version}
    )
    return {
        "observation_id": observation_id,
        **target,
        "scope": {"kind": "full_route"},
        "subject": (
            {"kind": "character", "character_id": character_id}
            if character_id
            else {"kind": "group"}
        ),
        "raw_gold_delta_copper": raw_gold_delta_copper,
        "assets": assets,
        "clean": clean,
        "contamination": contamination,
        "source_ref": source_ref,
    }


def append_observation(path: Path, observation: dict[str, Any]) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    observations = list(payload.get("observations") or [])
    if any(row.get("observation_id") == observation["observation_id"] for row in observations if isinstance(row, dict)):
        raise ValueError(f"duplicate observation_id: {observation['observation_id']}")
    observations.append(observation)
    updated = dict(payload)
    updated["observations"] = observations
    validate_economy_observations(updated)
    path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Append one raw full-route Economy Observation for a Profile or Route Program. "
            "This records evidence only; it never edits Task Card rewards or market valuations."
        )
    )
    parser.add_argument("--observation-id", required=True)
    parser.add_argument("--target-kind", choices=("profile", "program"), required=True)
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--target-version", required=True, type=int)
    parser.add_argument("--source-ref", required=True)
    parser.add_argument("--gold-delta-copper", type=int)
    parser.add_argument("--asset", action="append", default=[], help="Repeatable ASSET_ID=QUANTITY")
    parser.add_argument("--character-id", help="Omit for one group-level observation")
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--contamination", action="append", default=[])
    parser.add_argument("--output", type=Path, default=ECONOMY_OBSERVATIONS)
    args = parser.parse_args()

    observation = build_observation(
        observation_id=args.observation_id,
        target_kind=args.target_kind,
        target_id=args.target_id,
        target_version=args.target_version,
        source_ref=args.source_ref,
        raw_gold_delta_copper=args.gold_delta_copper,
        assets=[parse_asset(raw) for raw in args.asset],
        clean=args.clean,
        contamination=list(args.contamination),
        character_id=args.character_id,
    )
    updated = append_observation(args.output, observation)
    print(
        json.dumps(
            {
                "status": "recorded",
                "path": str(args.output),
                "observation_id": observation["observation_id"],
                "observation_count": len(updated["observations"]),
                "clean": observation["clean"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
