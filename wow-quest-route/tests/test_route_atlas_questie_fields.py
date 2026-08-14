import json
from pathlib import Path

from scripts.audit_zangarmarsh_task_profiles import eligibility
from scripts.build_route_atlas_prototype import (
    Q_PRE_GROUP,
    Q_PRE_SINGLE,
    Q_REQUIRED_MAX_REP,
    Q_REQUIRED_MIN_REP,
    Q_SPECIAL_FLAGS,
)


def test_questie_precedence_field_indexes_match_questdb_schema():
    # Questie/Database/questDB.lua compact schema.
    assert Q_PRE_GROUP == 12
    assert Q_PRE_SINGLE == 13
    assert Q_REQUIRED_MIN_REP == 19
    assert Q_REQUIRED_MAX_REP == 20
    assert Q_SPECIAL_FLAGS == 24


def test_eligibility_preserves_reputation_availability_rewards_and_repeatability():
    row = eligibility(
        {
            19: {1: 970, 2: 3000},
            20: {1: 970, 2: 42000},
            24: 1,
            26: {1: {1: 970, 2: 250}},
        }
    )
    assert row["required_min_rep"] == {"faction_id": 970, "value": 3000}
    assert row["required_max_rep"] == {"faction_id": 970, "value": 42000}
    assert row["special_flags"] == 1
    assert row["repeatable"] is True
    assert row["reputation_rewards"] == [{"faction_id": 970, "value": 250}]
    assert row["has_reputation_condition"] is True


def test_zangarmarsh_leveling_policy_excludes_zero_xp_sporeggar_repeatables():
    root = Path(__file__).resolve().parents[1]
    profiles = json.loads(
        (root / "data/route-atlas/zangarmarsh-task-profiles.json").read_text(encoding="utf-8")
    )["quests"]

    for quest_id in (9727, 9742, 9744, 9807, 9809):
        profile = profiles[str(quest_id)]
        assert profile["repeatable"] is True
        assert profile["quest_xp_base"] is None
        assert profile["route_policy"] == "exclude_leveling_route"

    mature_spores = profiles["9806"]
    assert mature_spores["classification"]["effective_primary"] == "background_tradeable_mob_drop"
    assert mature_spores["route_policy"] == "include"
