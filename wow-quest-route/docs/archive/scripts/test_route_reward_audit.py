import json
from functools import lru_cache

from scripts.build_route_reward_audit import (
    BOREAN_ATTRIBUTE_LOCKS,
    BOREAN_DECISION_LOCKS,
    _attribute_lock_payload,
    _base_output_payload,
    _decision_lock_payload,
    build_borean,
)


@lru_cache(maxsize=1)
def audit_payload():
    return build_borean()


def by_id(payload):
    return {row["quest_id"]: row for row in payload["tasks"]}


def decisions_by_id(payload):
    return {row["quest_id"]: row for row in payload["removal_priority_candidates"]}


def test_borean_reward_audit_covers_formal_route():
    payload = audit_payload()
    assert payload["summary"] == {
        "task_card_universe_count": 163,
        "equipment_reward_count": 49,
        "no_equipment_reward_count": 114,
        "no_equipment_with_direct_money_count": 61,
        "no_equipment_no_direct_money_count": 53,
        "money_pending_count": 0,
        "multi_item_drop_or_pickup_count": 24,
        "multi_item_drop_count": 18,
        "multi_item_pickup_count": 6,
        "multi_item_mixed_sources_count": 0,
        "collection_review_count": 0,
        "chain_has_in_scope_followup_count": 120,
        "chain_terminal_in_scope_count": 43,
        "chain_dependency_confirmed_followup_count": 117,
        "chain_explicit_followup_only_count": 3,
        "timing_estimated_count": 153,
        "timing_unknown_count": 10,
        "removal_priority_1_count": 0,
        "removal_priority_2_count": 9,
        "removal_priority_3_count": 10,
        "removal_priority_4_count": 2,
        "removal_priority_pending_count": 0,
    }


def test_borean_reward_tags_keep_money_and_equipment_separate():
    rows = by_id(audit_payload())

    # No equipment, but direct leveling money: not part of the combined low-reward tag.
    assert rows[11931]["has_equipment_reward"] is False  # Cracking the Code
    assert rows[11931]["has_direct_money"] is True
    assert "reward:no_equipment_or_direct_money" not in rows[11931]["tags"]

    # No equipment and no direct leveling money. Max-level XP-to-money does not count.
    assert rows[11625]["has_equipment_reward"] is False  # The Trident of Naz'jan
    assert rows[11625]["has_direct_money"] is False
    assert "reward:no_equipment_or_direct_money" in rows[11625]["tags"]

    # Direct equipment reward wins the basic screen; money lookup is intentionally deferred.
    assert rows[11914]["has_equipment_reward"] is True  # Keep the Secret
    assert rows[11914]["direct_money_status"] == "not_required_for_basic_filter"
    assert "reward:equipment" in rows[11914]["tags"]

    # Consumable reward is not an equippable reward; direct money remains a separate fact.
    assert rows[11564]["has_equipment_reward"] is False  # Succulent Orca Stew
    assert rows[11564]["has_direct_money"] is True
    assert rows[11564]["other_reward_items"]


def test_borean_collection_tags_exclude_single_interactions_and_preserve_subtypes():
    rows = by_id(audit_payload())

    # User-confirmed Warsong munitions are repeated ground pickups, not creature drops.
    assert "objective:multi_item_pickup" in rows[11606]["tags"]
    assert "objective:multi_item_drop" not in rows[11606]["tags"]
    assert "objective:multi_repeated_item_collection" in rows[11606]["tags"]
    assert rows[11606]["collection_screen"]["manual_override_source"] == "user_field_confirmation_2026-08-18"

    # User-confirmed ground spare parts and crashed-pilot toolkits are pickups, not creature drops.
    assert "objective:multi_item_pickup" in rows[11906]["tags"]
    assert "objective:multi_item_drop" not in rows[11906]["tags"]
    assert rows[11906]["collection_screen"]["manual_override_source"] == "user_field_confirmation_2026-08-18"
    assert "objective:multi_item_pickup" in rows[11887]["tags"]
    assert "objective:multi_repeated_item_collection" in rows[11887]["tags"]

    # Multiple distinct one-each objectives stay separate from repeated farming.
    assert "objective:multi_distinct_one_each" in rows[11695]["tags"]
    assert "objective:multi_distinct_one_each" in rows[11640]["tags"]
    assert "objective:multi_distinct_one_each" in rows[11943]["tags"]

    # Mixed 3+1 drop structure is still multi-item, with its own subtype.
    assert "objective:multi_item_drop" in rows[11931]["tags"]
    assert "objective:multi_repeated_plus_distinct" in rows[11931]["tags"]

    # Single item + single interaction must not be promoted into the multi-item screen.
    assert "objective:multi_item_drop_or_pickup" not in rows[11909]["tags"]
    assert "objective:multi_item_drop_or_pickup" not in rows[11637]["tags"]

    # Multiple object interactions are not item collection for this pass.
    assert "objective:multi_item_drop_or_pickup" not in rows[11602]["tags"]
    assert "objective:multi_item_drop_or_pickup" not in rows[11936]["tags"]


def test_borean_chain_tags_cover_local_and_next_map_scope():
    rows = by_id(audit_payload())

    assert rows[11930]["chain_screen"]["has_in_scope_followup"] is True
    assert any(item["quest_id"] == 11977 for item in rows[11930]["chain_screen"]["direct_followups"])
    assert "chain:has_in_scope_followup" in rows[11930]["tags"]

    assert rows[11910]["chain_screen"]["has_in_scope_followup"] is False
    assert "chain:terminal_in_scope" in rows[11910]["tags"]


def test_borean_removal_priorities_follow_additive_rule_and_stay_out_of_task_cards():
    payload = audit_payload()
    rows = by_id(payload)
    decisions = decisions_by_id(payload)

    # Pickup + no direct reward + one valuable follow-up => P3B.
    assert decisions[11606]["priority_label"] == "P3B"
    assert decisions[11606]["screen"]["collection_source"] == "pickup"
    assert decisions[11606]["screen"]["direct_has_equipment_or_money_value"] is False
    assert decisions[11606]["screen"]["valuable_followup_count"] == 1
    assert "removal:pickup_one_level_lower_than_drop" in decisions[11606]["screen"]["tags"]

    # Drop + direct reward + no valuable follow-up => P2A.
    assert decisions[11931]["priority_label"] == "P2A"

    # Drop + direct reward + one valuable follow-up => P3B.
    assert decisions[11866]["priority_label"] == "P3B"

    # Pickup is one level lower than the equivalent drop case; no valuable follow-up => A.
    assert decisions[11906]["priority_label"] == "P3A"
    assert decisions[11906]["screen"]["collection_source"] == "pickup"
    assert "removal:pickup_one_level_lower_than_drop" in decisions[11906]["screen"]["tags"]
    assert decisions[11887]["priority_label"] == "P3A"
    assert "removal:pickup_one_level_lower_than_drop" in decisions[11887]["screen"]["tags"]

    # Multiple distinct one-each items and user-confirmed shared world-object objectives never enter the removal decision set.
    assert 11640 not in decisions
    assert 11943 not in decisions
    assert 11695 not in decisions
    assert 11936 not in decisions

    # Base task-card facts must never contain removal decisions.
    for row in rows.values():
        assert not any(tag.startswith("removal:") for tag in row["tags"])
        assert "removal_priority_screen" not in row
    base = _base_output_payload(payload)
    assert "removal_priority_candidates" not in base
    assert not any(key.startswith("removal_priority_") for key in base["summary"])


def test_borean_task_timing_marks_unknown_instead_of_using_fake_fallbacks():
    rows = by_id(audit_payload())
    assert rows[11887]["timing_screen"]["status"] == "estimated"
    assert rows[11894]["timing_screen"]["status"] == "estimated"
    assert rows[11605]["timing_screen"]["status"] == "estimated"
    assert rows[11936]["timing_screen"]["status"] == "estimated"
    assert round(rows[11936]["timing_screen"]["minutes"], 2) == 1.83
    assert rows[11943]["timing_screen"]["status"] == "estimated"
    assert round(rows[11943]["timing_screen"]["minutes"], 2) == 0.80
    assert rows[11652]["timing_screen"]["status"] == "estimated"
    assert round(rows[11652]["timing_screen"]["minutes"], 2) == 15.00
    assert rows[11606]["timing_screen"]["status"] == "estimated"
    assert round(rows[11606]["timing_screen"]["minutes"], 2) == 8.75
    assert rows[11931]["timing_screen"]["status"] == "unknown"
    assert rows[11931]["timing_screen"]["minutes"] is None
    assert "timing:unknown" in rows[11931]["tags"]


def test_borean_locked_attributes_and_decisions_match_current_computation():
    payload = audit_payload()
    attribute_locked = json.loads(BOREAN_ATTRIBUTE_LOCKS.read_text(encoding="utf-8"))
    decision_locked = json.loads(BOREAN_DECISION_LOCKS.read_text(encoding="utf-8"))
    assert attribute_locked == _attribute_lock_payload(payload)
    assert decision_locked == _decision_lock_payload(payload)


def test_borean_same_name_variants_use_formal_route_identity():
    rows = by_id(audit_payload())
    assert 11585 in rows and 11586 not in rows
    assert 11596 in rows and 11595 not in rows and 11597 not in rows
    assert 11684 in rows and 11713 not in rows
    assert 11919 in rows and 11940 not in rows
    assert 11702 in rows and 11704 not in rows
