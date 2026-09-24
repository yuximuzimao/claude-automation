from __future__ import annotations

import copy

import pytest
from jsonschema import Draft202012Validator

from lib.character_profiles import (
    CharacterProfileError,
    load_all_character_profiles,
    load_character_profile_schema,
    validate_route_profile_character_reference,
)
from lib.route_profiles import load_all_route_profiles


def test_character_profile_schema_is_valid_draft_2020_12() -> None:
    schema = load_character_profile_schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "wow-quest-route/character-profile/v1"


def test_all_current_route_profiles_resolve_to_machine_character_profiles() -> None:
    character_profiles = load_all_character_profiles(validate=True)
    route_profiles = load_all_route_profiles(validate=True, validate_task_cards=False)

    assert set(character_profiles) == {"horde-fivebox-current", "dk-twohand-blood-current"}
    for profile in route_profiles.values():
        validate_route_profile_character_reference(profile, character_profiles)

    assert character_profiles["horde-fivebox-current"]["race"] == "blood_elf"
    assert character_profiles["horde-fivebox-current"]["class"] == "paladin"
    assert character_profiles["dk-twohand-blood-current"]["race"] == "orc"
    assert character_profiles["dk-twohand-blood-current"]["class"] == "death_knight"


def test_route_profile_character_reference_rejects_unknown_or_wrong_variant() -> None:
    character_profiles = load_all_character_profiles(validate=True)
    profile = next(iter(load_all_route_profiles(validate=True, validate_task_cards=False).values()))

    unknown = copy.deepcopy(profile)
    unknown["scope"]["character_profile"] = "missing-profile"
    with pytest.raises(CharacterProfileError, match="unknown character_profile"):
        validate_route_profile_character_reference(unknown, character_profiles)

    wrong_variant_profiles = copy.deepcopy(character_profiles)
    ref = profile["scope"]["character_profile"]
    wrong_variant_profiles[ref]["game_variant_id"] = "other-variant"
    with pytest.raises(CharacterProfileError, match="does not match Character Profile"):
        validate_route_profile_character_reference(profile, wrong_variant_profiles)
