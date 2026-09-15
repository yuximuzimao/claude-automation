from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

from .task_cards import load_all_task_cards

ROOT = Path(__file__).resolve().parents[1]
ROUTE_PROFILES_DIR = ROOT / "data/route-profiles"
ROUTE_PROFILE_SCHEMA = ROUTE_PROFILES_DIR / "schema.json"
TASK_ACTION_KINDS = {"accept", "objective", "turnin"}

# Intrinsic Task Card facts may never be copied into a Route Profile, including flexible history data.
FORBIDDEN_TASK_FACT_KEYS = {
    "fivebox",
    "mechanics",
    "guide",
    "evidence",
    "presentation",
    "objectives",
    "quest_level",
    "min_level",
    "pre_any",
    "pre_all",
    "direct_followups",
    "exclusive_with",
    "hidden_requirements",
    "base_xp",
    "reward_money",
}


class RouteProfileError(ValueError):
    """Raised when a Route Profile violates the project contract."""


def route_profile_path(profile_id: str) -> Path:
    return ROUTE_PROFILES_DIR / f"{profile_id}.json"


def load_route_profile_schema() -> dict[str, Any]:
    return json.loads(ROUTE_PROFILE_SCHEMA.read_text(encoding="utf-8"))


def _schema_validator() -> Draft202012Validator:
    schema = load_route_profile_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _validate_schema(profile: Any) -> None:
    errors = sorted(_schema_validator().iter_errors(profile), key=lambda error: list(error.absolute_path))
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
    raise RouteProfileError("Route Profile JSON Schema validation failed: " + "; ".join(rendered))


def _duplicates(values: Iterable[Any]) -> list[Any]:
    seen: set[Any] = set()
    duplicates: list[Any] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def _walk_keys(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            yield key, child_path
            yield from _walk_keys(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_keys(child, f"{path}[{index}]")


def _validate_task_state(profile: dict[str, Any]) -> None:
    """Replay only the task state needed by the current Route Profile contract.

    Conditional opportunity tasks must close inside the profile for now.  We deliberately do not
    prebuild reputation/items/objective-level RouteState until a real cross-profile requirement
    needs it.
    """

    active = set(profile["entry_state_contract"]["active_task_ids"])
    maybe_active: set[int] = set()

    for action in profile["actions"]:
        kind = action["kind"]
        if kind not in TASK_ACTION_KINDS:
            continue
        task_id = action["task_id"]
        condition = action.get("when")

        if kind == "accept":
            if task_id in active or task_id in maybe_active:
                raise RouteProfileError(
                    f"duplicate accept for task {task_id} at action {action['action_id']}"
                )
            if condition is None:
                active.add(task_id)
            elif condition["kind"] == "has_item":
                maybe_active.add(task_id)
            else:
                raise RouteProfileError(
                    f"accept action {action['action_id']} uses unsupported condition {condition['kind']!r}"
                )
            continue

        if kind == "objective":
            if task_id not in active and task_id not in maybe_active:
                raise RouteProfileError(
                    f"objective for inactive task {task_id} at action {action['action_id']}"
                )
            continue

        if kind == "turnin":
            if condition is None:
                if task_id not in active:
                    raise RouteProfileError(
                        f"unconditional turnin for non-active task {task_id} at action {action['action_id']}"
                    )
                active.remove(task_id)
                continue

            if condition["kind"] != "task_active" or condition.get("task_id") != task_id:
                raise RouteProfileError(
                    f"conditional turnin {action['action_id']} must use when=task_active for the same task"
                )
            active.discard(task_id)
            maybe_active.discard(task_id)

    if maybe_active:
        raise RouteProfileError(
            "conditional tasks remain unresolved at profile exit: " + ", ".join(map(str, sorted(maybe_active)))
        )

    declared_exit = set(profile["exit_state_contract"]["active_task_ids"])
    if active != declared_exit:
        missing = sorted(active - declared_exit)
        extra = sorted(declared_exit - active)
        raise RouteProfileError(
            f"exit_state_contract does not match replayed state; missing={missing}, extra={extra}"
        )


def validate_route_profile(
    profile: dict[str, Any],
    *,
    expected_profile_id: str | None = None,
    known_task_cards: dict[int, dict[str, Any]] | None = None,
) -> None:
    """Validate one Route Profile.

    JSON Schema owns shape/type/enums.  Python checks only semantic relations that require multiple
    fields/files or ordered state replay.
    """

    _validate_schema(profile)

    profile_id = profile["profile_id"]
    if expected_profile_id is not None and profile_id != expected_profile_id:
        raise RouteProfileError(
            f"profile_id {profile_id!r} does not match filename/id {expected_profile_id!r}"
        )

    forbidden_hits = [
        (key, path)
        for key, path in _walk_keys(profile)
        if key in FORBIDDEN_TASK_FACT_KEYS
    ]
    if forbidden_hits:
        rendered = ", ".join(f"{key}@{path}" for key, path in forbidden_hits)
        raise RouteProfileError(f"Task Card facts are forbidden in Route Profile: {rendered}")

    task_ids = profile["task_ids"]
    task_id_set = set(task_ids)

    if known_task_cards is not None:
        unknown_cards = sorted(task_id_set - set(known_task_cards))
        if unknown_cards:
            raise RouteProfileError(f"task_ids without Task Cards: {unknown_cards}")
        expected_variant = profile["scope"]["game_variant_id"]
        wrong_variant = sorted(
            task_id
            for task_id in task_ids
            if known_task_cards[task_id]["identity"]["game_variant_id"] != expected_variant
        )
        if wrong_variant:
            raise RouteProfileError(
                f"Task Cards do not match profile game_variant_id={expected_variant!r}: {wrong_variant}"
            )

    action_ids = [action["action_id"] for action in profile["actions"]]
    duplicate_actions = _duplicates(action_ids)
    if duplicate_actions:
        raise RouteProfileError(f"duplicate action_id values: {duplicate_actions}")

    referenced_task_ids = {
        action["task_id"]
        for action in profile["actions"]
        if action["kind"] in TASK_ACTION_KINDS
    }
    contract_task_ids = {
        *profile["entry_state_contract"]["active_task_ids"],
        *profile["exit_state_contract"]["active_task_ids"],
    }
    missing_from_task_ids = sorted((referenced_task_ids | contract_task_ids) - task_id_set)
    if missing_from_task_ids:
        raise RouteProfileError(
            f"actions/state contracts reference tasks not listed in task_ids: {missing_from_task_ids}"
        )
    unused_task_ids = sorted(task_id_set - (referenced_task_ids | contract_task_ids))
    if unused_task_ids:
        raise RouteProfileError(f"task_ids without actions/state role: {unused_task_ids}")

    location_ids = set(profile["geometry"]["locations"])
    missing_locations = sorted(
        {
            action["location_ref"]
            for action in profile["actions"]
            if "location_ref" in action and action["location_ref"] not in location_ids
        }
    )
    if missing_locations:
        raise RouteProfileError(f"actions reference unknown location_ref values: {missing_locations}")

    step_ids = [step["step_id"] for step in profile["step_groups"]]
    duplicate_steps = _duplicates(step_ids)
    if duplicate_steps:
        raise RouteProfileError(f"duplicate step_id values: {duplicate_steps}")

    flattened = [action_id for step in profile["step_groups"] for action_id in step["action_ids"]]
    if flattened != action_ids:
        raise RouteProfileError(
            "step_groups must cover every action exactly once and preserve action order"
        )

    _validate_task_state(profile)


def load_route_profile(
    profile_id: str,
    *,
    validate: bool = True,
    validate_task_cards: bool = False,
) -> dict[str, Any]:
    path = route_profile_path(profile_id)
    if not path.exists():
        raise FileNotFoundError(path)
    profile = json.loads(path.read_text(encoding="utf-8"))
    if validate:
        cards = load_all_task_cards() if validate_task_cards else None
        validate_route_profile(
            profile,
            expected_profile_id=profile_id,
            known_task_cards=cards,
        )
    return profile


def load_all_route_profiles(
    *,
    validate: bool = True,
    validate_task_cards: bool = False,
) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    cards = load_all_task_cards() if validate_task_cards else None
    for path in sorted(ROUTE_PROFILES_DIR.glob("*.json")):
        if path.name == "schema.json":
            continue
        profile_id = path.stem
        profile = json.loads(path.read_text(encoding="utf-8"))
        if validate:
            validate_route_profile(
                profile,
                expected_profile_id=profile_id,
                known_task_cards=cards,
            )
        if profile_id in profiles:
            raise RouteProfileError(f"duplicate profile_id: {profile_id}")
        profiles[profile_id] = profile
    return profiles


def build_task_profile_index(
    profiles: dict[str, dict[str, Any]] | None = None,
    *,
    include_retired: bool = False,
) -> dict[int, list[str]]:
    """Build task_id -> Route Profile reverse dependencies mechanically."""

    if profiles is None:
        profiles = load_all_route_profiles(validate=True)
    index: dict[int, list[str]] = {}
    for profile_id, profile in profiles.items():
        if profile.get("status") == "retired" and not include_retired:
            continue
        for task_id in profile["task_ids"]:
            index.setdefault(int(task_id), []).append(profile_id)
    for profile_ids in index.values():
        profile_ids.sort()
    return dict(sorted(index.items()))
