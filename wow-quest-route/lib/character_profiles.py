from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .route_profiles import ROOT

CHARACTER_PROFILES_DIR = ROOT / "data/character-profiles"
CHARACTER_PROFILE_SCHEMA = CHARACTER_PROFILES_DIR / "schema.json"


class CharacterProfileError(ValueError):
    """Raised when a Character Profile violates the project contract."""


def character_profile_path(character_profile_id: str) -> Path:
    return CHARACTER_PROFILES_DIR / f"{character_profile_id}.json"


def load_character_profile_schema() -> dict[str, Any]:
    return json.loads(CHARACTER_PROFILE_SCHEMA.read_text(encoding="utf-8"))


def _schema_validator() -> Draft202012Validator:
    schema = load_character_profile_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_character_profile(
    profile: dict[str, Any],
    *,
    expected_character_profile_id: str | None = None,
) -> None:
    errors = sorted(_schema_validator().iter_errors(profile), key=lambda error: list(error.absolute_path))
    if errors:
        rendered: list[str] = []
        for error in errors[:8]:
            path = "$"
            for part in error.absolute_path:
                path += f"[{part}]" if isinstance(part, int) else f".{part}"
            rendered.append(f"{path}: {error.message}")
        if len(errors) > 8:
            rendered.append(f"... and {len(errors) - 8} more schema errors")
        raise CharacterProfileError("Character Profile JSON Schema validation failed: " + "; ".join(rendered))

    character_profile_id = profile["character_profile_id"]
    if expected_character_profile_id is not None and character_profile_id != expected_character_profile_id:
        raise CharacterProfileError(
            f"character_profile_id {character_profile_id!r} does not match filename/id "
            f"{expected_character_profile_id!r}"
        )


def load_character_profile(character_profile_id: str, *, validate: bool = True) -> dict[str, Any]:
    path = character_profile_path(character_profile_id)
    if not path.exists():
        raise FileNotFoundError(path)
    profile = json.loads(path.read_text(encoding="utf-8"))
    if validate:
        validate_character_profile(profile, expected_character_profile_id=character_profile_id)
    return profile


def load_all_character_profiles(*, validate: bool = True) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    if not CHARACTER_PROFILES_DIR.exists():
        return profiles
    for path in sorted(CHARACTER_PROFILES_DIR.glob("*.json")):
        if path.name == "schema.json":
            continue
        character_profile_id = path.stem
        profile = json.loads(path.read_text(encoding="utf-8"))
        if validate:
            validate_character_profile(profile, expected_character_profile_id=character_profile_id)
        if character_profile_id in profiles:
            raise CharacterProfileError(f"duplicate character_profile_id: {character_profile_id}")
        profiles[character_profile_id] = profile
    return profiles


def validate_route_profile_character_reference(
    route_profile: dict[str, Any],
    character_profiles: dict[str, dict[str, Any]],
) -> None:
    character_profile_id = route_profile["scope"]["character_profile"]
    if character_profile_id not in character_profiles:
        raise CharacterProfileError(
            f"Route Profile {route_profile['profile_id']!r} references unknown character_profile "
            f"{character_profile_id!r}"
        )
    character_profile = character_profiles[character_profile_id]
    expected_variant = route_profile["scope"]["game_variant_id"]
    if character_profile["game_variant_id"] != expected_variant:
        raise CharacterProfileError(
            f"Route Profile {route_profile['profile_id']!r} game_variant_id={expected_variant!r} "
            f"does not match Character Profile {character_profile_id!r} "
            f"game_variant_id={character_profile['game_variant_id']!r}"
        )
