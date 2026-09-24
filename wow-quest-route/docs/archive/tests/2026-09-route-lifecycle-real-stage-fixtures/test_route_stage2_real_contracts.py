from __future__ import annotations

from lib.character_profiles import load_all_character_profiles
from lib.route_programs import load_route_program
from lib.route_profiles import load_all_route_profiles
from scripts.rebuild_route_profile import audit_profile


# Stage 2 migration acceptance fixture. Expectations are declared from the formal
# topology before treating validator output as proof. Do not edit Route Profiles or
# the Program merely to make this fixture pass; classify any future mismatch first.
def test_stage2_frozen_real_program_and_character_contracts() -> None:
    profiles = load_all_route_profiles(validate=True, validate_task_cards=False)
    character_profiles = load_all_character_profiles(validate=True)
    program = load_route_program(
        "horde-fivebox-full-clear",
        validate=True,
        validate_profiles=True,
    )

    assert len(profiles) == 14
    assert set(character_profiles) == {"horde-fivebox-current", "dk-twohand-blood-current"}
    assert program["scope"] == {
        "program_scope": "Horde fivebox Outland-to-Northrend full-clear sequence",
        "character_profile": "horde-fivebox-current",
        "game_variant_id": "timewalking-wotlk-cn",
    }
    assert program["entry_state_contract"] == {"active_task_ids": []}
    assert program["profile_ids"] == [
        "hellfire-fivebox",
        "zangarmarsh-fivebox",
        "nagrand-fivebox-67-68",
        "borean-fivebox",
        "dragonblight-fivebox",
        "dalaran-mainline-77",
        "storm-peaks-fivebox",
        "icecrown-fivebox",
        "sholazar-fivebox",
        "zuldrak-fivebox",
        "grizzly-fivebox",
        "howling-fivebox",
    ]
    for profile_id in program["profile_ids"]:
        assert profiles[profile_id]["schema_version"] == 2
        assert "entry_requirements" in profiles[profile_id]
        assert "entry_state_contract" not in profiles[profile_id]
        assert "exit_state_contract" not in profiles[profile_id]
        assert profiles[profile_id]["scope"]["character_profile"] == "horde-fivebox-current"
        assert profiles[profile_id]["scope"]["game_variant_id"] == "timewalking-wotlk-cn"

    assert profiles["hellfire-dk-speed"]["scope"]["character_profile"] == "dk-twohand-blood-current"
    assert profiles["zangarmarsh-dk-speed"]["scope"]["character_profile"] == "dk-twohand-blood-current"


def test_stage2_rebuild_entrypoint_executes_real_contract_gate() -> None:
    report = audit_profile("hellfire-fivebox")
    stage2 = report["stages"][1]

    assert stage2["name"] == "profile_program_contract"
    assert stage2["implementation_status"] == "implemented"
    assert stage2["evaluation_status"] == "pass"
    assert stage2["detail"]["profile_contract"] == "valid"
    assert stage2["detail"]["character_profile_contract"] == "valid"
    assert stage2["detail"]["character_profile_id"] == "horde-fivebox-current"
    assert stage2["detail"]["route_program_count"] == 1
    assert stage2["detail"]["route_program_ids"] == ["horde-fivebox-full-clear"]
    assert stage2["detail"]["standalone_profile"] is False
    assert report["status"] == "blocked"
