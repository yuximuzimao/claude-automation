from __future__ import annotations

from scripts.apply_fivebox_type_mappings import classify_type


def test_fivebox_type_mapping_keeps_sequential_loot_ahead_of_personal_keyword() -> None:
    status, _ = classify_type("personal_loot_same_kill_sequential_pickup_confirmed")
    assert status == "sequential_loot"


def test_fivebox_type_mapping_distinguishes_shared_personal_special_and_pending() -> None:
    assert classify_type("event_group_shared_confirmed")[0] == "shared"
    assert classify_type("corpse_interaction_personal_confirmed")[0] == "not_shared"
    assert classify_type("single_fight_multi_character_interaction_confirmed")[0] == "special"
    assert classify_type("object_collect_manual_local_loop")[0] == "pending"
