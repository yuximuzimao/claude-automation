from __future__ import annotations

from pathlib import Path

from lib.questie_drop_rates import DropRate
from lib.questie_objectives import (
    build_effective_timing_source_inputs,
    objective_atoms,
    objective_counts,
    timing_inputs_from_atoms,
)
from lib.questie_source import QuestieData


class _DropDB:
    def __init__(self, rates: dict[tuple[int, int], float]):
        self.rates = rates

    def get(self, item_id: int, npc_id: int):
        rate = self.rates.get((item_id, npc_id))
        return DropRate(item_id, npc_id, rate, "synthetic") if rate is not None else None


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


def test_item_source_chain_is_preserved_without_inventing_container_drop_rate() -> None:
    data = _questie(items={222: {4: {1: 333}}})
    row = {
        8: {1: "Collect the plans"},
        10: {3: {1: {1: 222}}},
    }

    atoms, issues = objective_atoms(data, 100, row)
    inputs, resolution_issues = timing_inputs_from_atoms(atoms)

    assert issues == []
    assert resolution_issues == []
    assert atoms[0]["source_item_ids"] == [333]
    assert inputs["source_item_ids"] == [333]
    assert "drop_rate" not in inputs


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


def test_drop_rate_percent_is_normalized_to_probability_for_timing() -> None:
    atoms = [
        {
            "objective_type": "item",
            "entity_id": 222,
            "item_id": 222,
            "required_count": 1,
            "source_npc_ids": [333],
            "source_object_ids": [],
            "source_item_ids": [],
        }
    ]
    inputs, issues = timing_inputs_from_atoms(atoms, drop_db=_DropDB({(222, 333): 39.0}))

    assert issues == []
    assert inputs["drop_rate"] == 0.39


def test_equal_multi_npc_drop_rates_resolve_without_route_source_selection() -> None:
    atoms = [
        {
            "objective_type": "item",
            "entity_id": 222,
            "item_id": 222,
            "required_count": 6,
            "source_npc_ids": [333, 444],
            "source_object_ids": [],
            "source_item_ids": [],
        }
    ]
    inputs, issues = timing_inputs_from_atoms(
        atoms,
        drop_db=_DropDB({(222, 333): 20.0, (222, 444): 20.0}),
    )

    assert issues == []
    assert inputs["drop_rate"] == 0.2
    assert inputs["drop_rate_npc_ids"] == [333, 444]
    assert inputs["drop_rate_candidates"] == [
        {"npc_id": 333, "rate": 0.2, "source": "synthetic"},
        {"npc_id": 444, "rate": 0.2, "source": "synthetic"},
    ]


def test_different_multi_npc_drop_rates_still_require_route_source_selection() -> None:
    atoms = [
        {
            "objective_type": "item",
            "entity_id": 222,
            "item_id": 222,
            "required_count": 5,
            "source_npc_ids": [333, 444],
            "source_object_ids": [],
            "source_item_ids": [],
        }
    ]
    inputs, issues = timing_inputs_from_atoms(
        atoms,
        drop_db=_DropDB({(222, 333): 20.0, (222, 444): 30.0}),
    )

    assert "drop_rate" not in inputs
    assert inputs["drop_rate_candidates"] == [
        {"npc_id": 333, "rate": 0.2, "source": "synthetic"},
        {"npc_id": 444, "rate": 0.3, "source": "synthetic"},
    ]
    assert issues[0]["kind"] == "drop_rate_route_source_selection_required"


def test_world_object_item_collection_exposes_interaction_count() -> None:
    atoms = [
        {
            "objective_type": "item",
            "entity_id": 222,
            "item_id": 222,
            "required_count": 8,
            "source_npc_ids": [],
            "source_object_ids": [555],
            "source_item_ids": [],
        }
    ]
    inputs, issues = timing_inputs_from_atoms(atoms)

    assert issues == []
    assert inputs["required_count"] == 8
    assert inputs["interaction_count"] == 8


def test_missing_questie_source_is_explicit_requirement_not_foundation_fallback(tmp_path: Path) -> None:
    missing = tmp_path / "Questie.zip"
    report = build_effective_timing_source_inputs(missing, [100])

    assert report["status"] == "requirements"
    assert report["tasks"] == {}
    assert report["issues"] == [
        {"severity": "requirement", "kind": "questie_timing_source_required", "path": str(missing.resolve())}
    ]
