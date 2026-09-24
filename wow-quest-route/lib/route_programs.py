from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .route_profiles import ROOT, load_all_route_profiles

ROUTE_PROGRAMS_DIR = ROOT / "data/route-programs"
ROUTE_PROGRAM_SCHEMA = ROUTE_PROGRAMS_DIR / "schema.json"


class RouteProgramError(ValueError):
    """Raised when a Route Program violates the project contract."""


def route_program_path(program_id: str) -> Path:
    return ROUTE_PROGRAMS_DIR / f"{program_id}.json"


def load_route_program_schema() -> dict[str, Any]:
    return json.loads(ROUTE_PROGRAM_SCHEMA.read_text(encoding="utf-8"))


def _schema_validator() -> Draft202012Validator:
    schema = load_route_program_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _validate_schema(program: Any) -> None:
    errors = sorted(_schema_validator().iter_errors(program), key=lambda error: list(error.absolute_path))
    if not errors:
        return
    rendered: list[str] = []
    for error in errors[:8]:
        path = "$"
        for part in error.absolute_path:
            path += f"[{part}]" if isinstance(part, int) else f".{part}"
        rendered.append(f"{path}: {error.message}")
    if len(errors) > 8:
        rendered.append(f"... and {len(errors) - 8} more schema errors")
    raise RouteProgramError("Route Program JSON Schema validation failed: " + "; ".join(rendered))


def validate_route_program(
    program: dict[str, Any],
    *,
    expected_program_id: str | None = None,
    known_profiles: dict[str, dict[str, Any]] | None = None,
) -> None:
    _validate_schema(program)

    program_id = program["program_id"]
    if expected_program_id is not None and program_id != expected_program_id:
        raise RouteProgramError(
            f"program_id {program_id!r} does not match filename/id {expected_program_id!r}"
        )

    if known_profiles is None:
        return

    profile_ids = list(program["profile_ids"])
    unknown = [profile_id for profile_id in profile_ids if profile_id not in known_profiles]
    if unknown:
        raise RouteProgramError(f"Route Program references unknown Route Profiles: {unknown}")

    adjacent_pairs = set(zip(profile_ids, profile_ids[1:]))
    seen_boundaries: set[tuple[str, str]] = set()
    for transition in program.get("boundary_transitions") or []:
        pair = (str(transition["from_profile_id"]), str(transition["to_profile_id"]))
        if pair not in adjacent_pairs:
            raise RouteProgramError(
                f"boundary transition must bind adjacent Profile ids in Program order: {pair[0]}->{pair[1]}"
            )
        if pair in seen_boundaries:
            raise RouteProgramError(f"duplicate boundary transition: {pair[0]}->{pair[1]}")
        seen_boundaries.add(pair)
        operation_ids: set[str] = set()
        for operation in transition["operations"]:
            operation_id = str(operation["operation_id"])
            if operation_id in operation_ids:
                raise RouteProgramError(
                    f"duplicate boundary operation_id in {pair[0]}->{pair[1]}: {operation_id}"
                )
            operation_ids.add(operation_id)
            if operation["kind"] != "move" and operation.get("movement_mode") is not None:
                raise RouteProgramError(
                    f"movement_mode is only valid for move operations: {pair[0]}->{pair[1]}/{operation_id}"
                )

    expected_variant = program["scope"]["game_variant_id"]
    wrong_variant = [
        profile_id
        for profile_id in profile_ids
        if known_profiles[profile_id]["scope"]["game_variant_id"] != expected_variant
    ]
    if wrong_variant:
        raise RouteProgramError(
            f"Route Program game_variant_id={expected_variant!r} mismatches member Profiles: {wrong_variant}"
        )

    expected_character_profile = program["scope"]["character_profile"]
    wrong_character_profile = [
        profile_id
        for profile_id in profile_ids
        if known_profiles[profile_id]["scope"]["character_profile"] != expected_character_profile
    ]
    if wrong_character_profile:
        raise RouteProgramError(
            f"Route Program character_profile={expected_character_profile!r} mismatches member Profiles: "
            f"{wrong_character_profile}"
        )

    if program["status"] != "retired":
        retired_members = [
            profile_id for profile_id in profile_ids if known_profiles[profile_id].get("status") == "retired"
        ]
        if retired_members:
            raise RouteProgramError(
                f"non-retired Route Program references retired Route Profiles: {retired_members}"
            )


def load_route_program(
    program_id: str,
    *,
    validate: bool = True,
    validate_profiles: bool = False,
) -> dict[str, Any]:
    path = route_program_path(program_id)
    if not path.exists():
        raise FileNotFoundError(path)
    program = json.loads(path.read_text(encoding="utf-8"))
    if validate:
        profiles = load_all_route_profiles(validate=True, validate_task_cards=False) if validate_profiles else None
        validate_route_program(
            program,
            expected_program_id=program_id,
            known_profiles=profiles,
        )
    return program


def load_all_route_programs(
    *,
    validate: bool = True,
    validate_profiles: bool = False,
) -> dict[str, dict[str, Any]]:
    programs: dict[str, dict[str, Any]] = {}
    profiles = load_all_route_profiles(validate=True, validate_task_cards=False) if validate_profiles else None
    if not ROUTE_PROGRAMS_DIR.exists():
        return programs
    for path in sorted(ROUTE_PROGRAMS_DIR.glob("*.json")):
        if path.name == "schema.json":
            continue
        program_id = path.stem
        program = json.loads(path.read_text(encoding="utf-8"))
        if validate:
            validate_route_program(
                program,
                expected_program_id=program_id,
                known_profiles=profiles,
            )
        if program_id in programs:
            raise RouteProgramError(f"duplicate program_id: {program_id}")
        programs[program_id] = program
    return programs
