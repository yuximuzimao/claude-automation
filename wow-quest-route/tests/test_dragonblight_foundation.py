import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "data/route-atlas/dragonblight-task-foundation.json"
MECHANICS = ROOT / "data/route-atlas/dragonblight-special-mechanism-audit.json"
CLUSTERS = ROOT / "data/route-atlas/dragonblight-target-clusters.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def by_id(payload):
    return {row["quest_id"]: row for row in payload["tasks"]}


def test_foundation_is_explicitly_pre_insertion():
    payload = load(FOUNDATION)
    assert payload["status"] == "foundation_only_no_route_order"
    assert payload["entry_contract"]["from_borean_quest_id"] == 11930
    assert payload["entry_contract"]["carried_cross_map_quest_id"] == 12117
    assert payload["entry_contract"]["route_insertion_started"] is False
    assert payload["manual_review_pending_count"] == 0


def test_removed_and_alternate_entry_tasks_are_not_current_candidates():
    rows = by_id(load(FOUNDATION))
    for quest_id in (12015, 12021, 12023, 12051):
        assert rows[quest_id]["scope_status"] == "exclude_removed_or_unavailable"
    for quest_id in (12118, 12182, 12189):
        assert rows[quest_id]["scope_status"] == "exclude_current_entry_axis_alternate"
    assert rows[12117]["scope_status"] == "include_cross_map_inbound"


def test_every_current_world_candidate_has_final_note_decision():
    payload = load(FOUNDATION)
    for row in payload["tasks"]:
        if not row["is_primary_candidate"] or row["is_dungeon"]:
            continue
        if not row["scope_status"].startswith("include_"):
            continue
        decision = row["final_note_review"]["decision"]
        assert decision in {"must_note", "reviewed_no_extra_note", "review_before_route"}
        assert decision != "manual_review_pending"


def test_known_hidden_mechanisms_stay_must_note():
    rows = by_id(load(FOUNDATION))
    must_note = {
        11959, 11999, 12028, 12032, 12049, 12053, 12057, 12059,
        12072, 12076, 12078, 12132, 12214, 12243, 12261, 12263,
        12274, 12449, 12459, 12470, 12498,
    }
    for quest_id in must_note:
        assert rows[quest_id]["final_note_review"]["decision"] == "must_note"


def test_target_clusters_exist_and_do_not_claim_route_order():
    payload = load(CLUSTERS)
    assert payload["status"] == "foundation_only_no_route_order"
    assert payload["cluster_count"] > 0
    assert payload["shared_cluster_count"] > 0


def test_mechanism_audit_has_no_manual_pending():
    payload = load(MECHANICS)
    assert payload["manual_review_pending_count"] == 0
    assert payload["decision_counts"].get("must_note", 0) > 0
    assert payload["decision_counts"].get("reviewed_no_extra_note", 0) > 0
