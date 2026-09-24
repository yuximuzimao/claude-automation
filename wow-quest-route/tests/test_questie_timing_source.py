from __future__ import annotations

from pathlib import Path

from lib.questie_objectives import (
    build_effective_timing_source_inputs,
    objective_atoms,
    objective_counts,
    timing_inputs_from_atoms,
)
from lib.questie_source import QuestieData


def _questie(*, quest_names=None, items=None) -> QuestieData:
    return QuestieData(
        quests={},
        npcs={},
        objects={},
        items=items or {},
        quest_names=quest_names or {},
        npc_names={},
        object_names={},
        item_names={},
        version="synthetic",
        source_sha256="0" * 64,
        quest_xp={},
    )


def test_historical_objective_count_parser_keeps_exact_slot_order() -> None:
    counts, confidence = objective_counts("Kill 4 Crawlers / Collect 12 Thin Hides", 2)

    assert counts == [4, 12]
    assert confidence == "exact_text_order"


def test_effective_objective_adapter_exposes_only_unambiguous_machine_counts() -> None:
    data = _questie(items={222: {2: {1: 333}}})
    row = {
        8: {1: "Kill 4 Crawlers", 2: "Collect 12 Thin Hides"},
        10: {
            1: {1: {1: 111}},
            3: {1: {1: 222}},
        },
    }

    atoms, issues = objective_atoms(data, 100, row)
    inputs, resolution_issues = timing_inputs_from_atoms(atoms)

    assert issues == []
    assert resolution_issues == []
    assert [(row["objective_type"], row["required_count"]) for row in atoms] == [
        ("kill", 4),
        ("item", 12),
    ]
    assert atoms[1]["source_npc_ids"] == [333]
    assert inputs["kill_count"] == 4
    assert inputs["required_count"] == 12
    assert inputs["item_id"] == 222
    assert "drop_rate" not in inputs


def test_ambiguous_extra_numbers_remain_review_requirement_not_machine_count() -> None:
    data = _questie()
    row = {
        8: {1: "At level 70 kill 1 named target"},
        10: {1: {1: {1: 111}}},
    }

    atoms, issues = objective_atoms(data, 100, row)
    inputs, _ = timing_inputs_from_atoms(atoms)

    assert atoms[0]["required_count"] is None
    assert atoms[0]["source_count_candidate"] == 1
    assert atoms[0]["count_confidence"] == "ambiguous_extra_numbers"
    assert "kill_count" not in inputs
    assert issues[0]["kind"] == "questie_objective_count_review_required"


def test_multiple_drop_sources_never_select_one_route_drop_rate_implicitly() -> None:
    data = _questie(items={222: {2: {1: 333, 2: 444}}})
    row = {
        8: {1: "Collect 5 hides"},
        10: {3: {1: {1: 222}}},
    }

    atoms, issues = objective_atoms(data, 100, row)
    inputs, _ = timing_inputs_from_atoms(atoms)

    assert issues == []
    assert inputs["required_count"] == 5
    assert atoms[0]["source_npc_ids"] == [333, 444]
    assert "drop_rate" not in inputs


def test_missing_questie_source_is_explicit_requirement_not_foundation_fallback(tmp_path: Path) -> None:
    missing = tmp_path / "Questie.zip"
    report = build_effective_timing_source_inputs(missing, [100])

    assert report["status"] == "requirements"
    assert report["tasks"] == {}
    assert report["issues"] == [
        {"severity": "requirement", "kind": "questie_timing_source_required", "path": str(missing.resolve())}
    ]
