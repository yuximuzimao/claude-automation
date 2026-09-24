from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .route_profiles import ROOT, build_task_profile_index, load_all_route_profiles, load_route_profile
from .task_cards import load_all_task_cards, load_task_card

ROUTE_PROGRAMS_DIR = ROOT / "data/route-programs"
CHARACTER_PROFILES_DIR = ROOT / "data/character-profiles"
ROUTE_UI_DIR = ROOT / "data/route-ui"
OBSERVATIONS_DIR = ROOT / "data/observations"
TIMING_INPUTS_DIR = ROOT / "data/timing"
XP_INPUTS_DIR = ROOT / "data/xp-model"
RULES_DIR = ROOT / "docs/rules"
TASK_LIBRARY_RULE = ROOT / "docs/task-library/README.md"
LIFECYCLE_SOP = ROOT / "docs/verified-routes/ROUTE-DESIGN-PROCESS.md"
SCHEMA_SOURCES = {
    "task_card": ROOT / "data/task-cards/schema.json",
    "route_profile": ROOT / "data/route-profiles/schema.json",
    "route_program": ROUTE_PROGRAMS_DIR / "schema.json",
    "character_profile": CHARACTER_PROFILES_DIR / "schema.json",
}

TASK_CARD_SECTIONS = (
    "schema_version",
    "identity",
    "coverage",
    "availability",
    "rewards",
    "guide",
    "fivebox",
    "timing_rule_ref",
    "evidence",
    "presentation",
)

ROUTE_PROFILE_SECTIONS = (
    "schema_version",
    "version",
    "status",
    "scope",
    "entry_requirements",
    "goal",
    "display",
    "task_ids",
    "actions",
    "step_groups",
    "geometry",
    "change_log",
)

ROUTE_PROGRAM_SECTIONS = (
    "schema_version",
    "version",
    "status",
    "scope",
    "entry_state_contract",
    "goal",
    "profile_ids",
    "change_log",
)


class DependencyError(ValueError):
    """Raised when dependency discovery cannot identify a stable root input."""


def canonical_json_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _section_hashes(value: dict[str, Any], keys: Iterable[str]) -> dict[str, str]:
    return {
        key: canonical_json_hash(value.get(key))
        for key in keys
        if key in value
    }


def fingerprint_task_card(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": int(card["task_id"]),
        "hash": canonical_json_hash(card),
        "sections": _section_hashes(card, TASK_CARD_SECTIONS),
    }


def fingerprint_route_profile(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile_id": str(profile["profile_id"]),
        "version": int(profile["version"]),
        "status": str(profile["status"]),
        "hash": canonical_json_hash(profile),
        "sections": _section_hashes(profile, ROUTE_PROFILE_SECTIONS),
    }


def load_route_program_discovery_rows(directory: Path = ROUTE_PROGRAMS_DIR) -> dict[str, dict[str, Any]]:
    """Read only the minimum fields Stage 1 needs for reverse dependency discovery.

    Full Route Program shape/semantic validation belongs to Stage 2. Stage 1 deliberately does not
    become a second schema owner; it only requires stable identity plus an ordered profile_ids list.
    """

    if not directory.exists():
        return {}

    programs: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("*.json")):
        if path.name == "schema.json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise DependencyError(f"Route Program discovery expects an object: {path}")
        program_id = payload.get("program_id")
        profile_ids = payload.get("profile_ids")
        if not isinstance(program_id, str) or not program_id:
            raise DependencyError(f"Route Program discovery missing stable program_id: {path}")
        if path.stem != program_id:
            raise DependencyError(f"Route Program filename/id mismatch: {path.stem!r} != {program_id!r}")
        if not isinstance(profile_ids, list) or not all(isinstance(item, str) and item for item in profile_ids):
            raise DependencyError(f"Route Program discovery needs ordered profile_ids: {path}")
        if len(profile_ids) != len(set(profile_ids)):
            raise DependencyError(f"Route Program discovery has duplicate profile_ids: {path}")
        if program_id in programs:
            raise DependencyError(f"duplicate Route Program id: {program_id}")
        programs[program_id] = payload
    return programs


def build_profile_program_index(
    programs: dict[str, dict[str, Any]] | None = None,
    *,
    include_retired: bool = False,
) -> dict[str, list[str]]:
    if programs is None:
        programs = load_route_program_discovery_rows()
    index: dict[str, list[str]] = {}
    for program_id, program in programs.items():
        if program.get("status") == "retired" and not include_retired:
            continue
        for profile_id in program["profile_ids"]:
            index.setdefault(str(profile_id), []).append(program_id)
    for program_ids in index.values():
        program_ids.sort()
    return dict(sorted(index.items()))


def _fingerprint_json_file(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "path": str(path.relative_to(ROOT)),
        "hash": canonical_json_hash(payload),
    }


def _fingerprint_raw_file(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(ROOT)),
        "hash": file_sha256(path),
        "bytes": path.stat().st_size,
    }


def schema_source_inventory() -> dict[str, dict[str, Any]]:
    missing = [name for name, path in SCHEMA_SOURCES.items() if not path.exists()]
    if missing:
        raise DependencyError(f"missing dependency schemas: {missing}")
    return {name: _fingerprint_json_file(path) for name, path in sorted(SCHEMA_SOURCES.items())}


def rule_source_inventory() -> list[dict[str, Any]]:
    paths = [*sorted(RULES_DIR.glob("*.md")), TASK_LIBRARY_RULE, LIFECYCLE_SOP]
    return [_fingerprint_raw_file(path) for path in paths if path.exists()]


def observation_source_inventory(directory: Path = OBSERVATIONS_DIR) -> list[dict[str, Any]]:
    if not directory.exists():
        return []
    return [_fingerprint_raw_file(path) for path in sorted(directory.rglob("*")) if path.is_file()]


def external_timing_input_inventory(directory: Path = TIMING_INPUTS_DIR) -> list[dict[str, Any]]:
    if not directory.exists():
        return []
    return [_fingerprint_raw_file(path) for path in sorted(directory.rglob("*")) if path.is_file()]


def external_xp_input_inventory(directory: Path = XP_INPUTS_DIR) -> list[dict[str, Any]]:
    if not directory.exists():
        return []
    return [_fingerprint_raw_file(path) for path in sorted(directory.rglob("*")) if path.is_file()]


def profile_ui_input(profile_id: str) -> dict[str, Any] | None:
    path = ROUTE_UI_DIR / f"{profile_id}.json"
    if not path.exists():
        return None
    return _fingerprint_json_file(path)


def character_profile_input(character_profile_id: str) -> dict[str, Any] | None:
    path = CHARACTER_PROFILES_DIR / f"{character_profile_id}.json"
    if not path.exists():
        return None
    return _fingerprint_json_file(path)


def common_source_inventory() -> dict[str, Any]:
    """Build source groups shared by every Profile exactly once for batch audits."""

    return {
        "schemas": schema_source_inventory(),
        "rules": rule_source_inventory(),
        "observations": observation_source_inventory(),
        "external_timing_inputs": external_timing_input_inventory(),
        "external_xp_inputs": external_xp_input_inventory(),
    }


def fingerprint_route_program_discovery(program: dict[str, Any]) -> dict[str, Any]:
    return {
        "program_id": str(program["program_id"]),
        "version": program.get("version"),
        "status": program.get("status"),
        "hash": canonical_json_hash(program),
        "sections": _section_hashes(program, ROUTE_PROGRAM_SECTIONS),
    }


def compose_fingerprint(parts: Any) -> str:
    """Compose a downstream fingerprint from the exact atomic hashes that stage consumes."""

    return canonical_json_hash(parts)


def build_profile_dependency_manifest(
    profile_id: str,
    *,
    profile: dict[str, Any] | None = None,
    cards: dict[int, dict[str, Any]] | None = None,
    programs: dict[str, dict[str, Any]] | None = None,
    shared_source_inventory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if profile is None:
        profile = load_route_profile(profile_id, validate=True, validate_task_cards=False)
    if cards is None:
        cards = {
            int(task_id): load_task_card(int(task_id), validate=True)
            for task_id in profile["task_ids"]
        }
    missing_cards = sorted(set(map(int, profile["task_ids"])) - set(cards))
    if missing_cards:
        raise DependencyError(f"profile {profile_id} missing Task Cards for dependency manifest: {missing_cards}")

    if programs is None:
        programs = load_route_program_discovery_rows()
    profile_program_index = build_profile_program_index(programs)
    program_ids = profile_program_index.get(profile_id, [])

    profile_fp = fingerprint_route_profile(profile)
    task_fps = {
        str(task_id): fingerprint_task_card(cards[int(task_id)])
        for task_id in sorted(map(int, profile["task_ids"]))
    }
    program_fps = {
        program_id: fingerprint_route_program_discovery(programs[program_id])
        for program_id in program_ids
    }

    root_parts = {
        "profile": profile_fp["hash"],
        "task_cards": {task_id: row["hash"] for task_id, row in task_fps.items()},
        "route_programs": {program_id: row["hash"] for program_id, row in program_fps.items()},
    }
    root_fingerprint = compose_fingerprint(root_parts)

    if shared_source_inventory is None:
        shared_source_inventory = common_source_inventory()
    character_profile = character_profile_input(profile["scope"]["character_profile"])
    if character_profile is None:
        raise DependencyError(
            f"profile {profile_id} references missing character profile: {profile['scope']['character_profile']}"
        )
    source_inventory = {
        **shared_source_inventory,
        "character_profile": character_profile,
        "route_ui": profile_ui_input(profile_id),
    }

    return {
        "schema_version": 1,
        "profile": profile_fp,
        "task_cards": task_fps,
        "route_programs": program_fps,
        "root_fingerprint": root_fingerprint,
        "source_inventory": source_inventory,
        # This fingerprints the Stage-1 inventory itself. Downstream stages should still compose
        # their own narrower fingerprint from the atomic section/source hashes they actually consume.
        "manifest_fingerprint": compose_fingerprint(
            {"root_fingerprint": root_fingerprint, "source_inventory": source_inventory}
        ),
    }


def build_all_profile_dependency_manifests(
    *,
    profiles: dict[str, dict[str, Any]] | None = None,
    cards: dict[int, dict[str, Any]] | None = None,
    programs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    if profiles is None:
        profiles = load_all_route_profiles(validate=True, validate_task_cards=False)
    if cards is None:
        # Stage 1 inventories dependencies/hashes; schema validation belongs to the Task Card/Profile
        # contract gates. Avoid recompiling JSON Schema for every card during a global fingerprint pass.
        cards = load_all_task_cards(validate=False)
    if programs is None:
        programs = load_route_program_discovery_rows()
    shared_inventory = common_source_inventory()
    return {
        profile_id: build_profile_dependency_manifest(
            profile_id,
            profile=profile,
            cards=cards,
            programs=programs,
            shared_source_inventory=shared_inventory,
        )
        for profile_id, profile in sorted(profiles.items())
    }


def build_dependency_index(
    *,
    profiles: dict[str, dict[str, Any]] | None = None,
    programs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if profiles is None:
        profiles = load_all_route_profiles(validate=True, validate_task_cards=False)
    if programs is None:
        programs = load_route_program_discovery_rows()

    task_to_profiles = build_task_profile_index(profiles)
    profile_to_programs = build_profile_program_index(programs)
    program_to_profiles = {
        program_id: list(program["profile_ids"])
        for program_id, program in sorted(programs.items())
        if program.get("status") != "retired"
    }

    unknown_profile_refs = sorted(
        {
            profile_id
            for profile_ids in program_to_profiles.values()
            for profile_id in profile_ids
            if profile_id not in profiles
        }
    )

    return {
        "schema_version": 1,
        "task_to_profiles": {str(task_id): profile_ids for task_id, profile_ids in task_to_profiles.items()},
        "profile_to_programs": profile_to_programs,
        "program_to_profiles": program_to_profiles,
        "unknown_program_profile_refs": unknown_profile_refs,
        "summary": {
            "profile_count": len(profiles),
            "program_count": len(programs),
            "task_reverse_index_count": len(task_to_profiles),
            "profile_program_reverse_index_count": len(profile_to_programs),
        },
    }
