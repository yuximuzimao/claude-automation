import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    return json.loads((ROOT / "data/route-atlas" / name).read_text(encoding="utf-8"))


def test_zuldrak_scope_and_dependency_pool_is_closed():
    scope = load("zuldrak-scope-audit.json")
    foundation = load("zuldrak-task-foundation.json")
    assert scope["formal_candidate_count"] == 104
    assert foundation["formal_task_count"] == 104
    assert foundation["dependency_hard_gap_count"] == 0
    ids = set(foundation["formal_task_ids"])
    assert 12932 in ids
    assert 12948 in ids
    assert 12954 not in ids
    assert 12633 not in ids
    assert 12638 not in ids
    assert 12643 not in ids
    assert 12649 not in ids
    assert 12780 not in ids


def test_zuldrak_foundation_has_no_unknown_service_time():
    foundation = load("zuldrak-task-foundation.json")
    assert foundation["unknown_service_tasks"] == []
    by_id = {task["quest_id"]: task for task in foundation["tasks"]}
    for qid in (12527, 12555, 12557, 12622, 12627, 12648, 12677, 12729, 12919):
        service = by_id[qid]["intrinsic_service_time"]
        assert service["status"] == "estimated"
        assert service["minutes"] > 0
        assert len(service.get("range_minutes", [])) == 2


def test_zuldrak_target_clusters_include_extra_objective_anchors():
    clusters = load("zuldrak-target-clusters.json")
    assert clusters["cluster_count"] == 148
    rows = clusters["clusters"]
    assert any(12527 in row["quest_ids"] and "extra_reference" in row.get("source_kinds", []) for row in rows)
    assert any(12622 in row["quest_ids"] and "extra_reference" in row.get("source_kinds", []) for row in rows)
    assert any(12919 in row["quest_ids"] and "extra_coordinate" in row.get("source_kinds", []) for row in rows)


def test_zuldrak_pre_route_gate_is_complete_before_insertion():
    mechanics = load("zuldrak-special-mechanism-audit.json")
    spatial = load("zuldrak-spatial-instances.json")
    sequence = load("zuldrak-target-cluster-sequence.json")
    video = load("zuldrak-video-reference.json")
    assert mechanics["blocking_unknown_count"] == 0
    assert mechanics["must_note_count"] >= 55
    assert mechanics["fivebox_check_task_count"] >= 70
    assert spatial["unmapped_no_coordinate_count"] == 0
    assert sequence["cluster_count"] == 148
    assert sequence["ordered_cluster_count"] == 148
    assert sequence["missing_cluster_count"] == 0
    assert video["formal_task_with_video_count"] >= 43
