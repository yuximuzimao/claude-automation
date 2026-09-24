from __future__ import annotations

from lib.questie_source import QuestieData
from lib.task_evidence_index import normalize_questie_task


def _questie() -> QuestieData:
    return QuestieData(
        quests={},
        npcs={},
        objects={},
        items={},
        quest_names={999: {1: "测试任务", 2: {1: "完成测试目标。"}}},
        npc_names={},
        object_names={},
        item_names={},
        version="test",
        source_sha256="test",
        quest_xp={},
    )


def test_normalized_prerequisites_keep_questie_group_and_single_semantics() -> None:
    # Questie schema: field 12 = preQuestGroup (ALL), field 13 = preQuestSingle (ANY).
    row = {
        1: "Test Quest",
        4: 58,
        5: 60,
        6: 690,
        8: {1: "Complete the test objective."},
        12: {1: 100, 2: 101},
        13: {1: 200, 2: 201},
        23: 0,
        24: 0,
    }

    normalized = normalize_questie_task(_questie(), 999, row)
    assert normalized["pre_all"] == [100, 101]
    assert normalized["pre_any"] == [200, 201]
