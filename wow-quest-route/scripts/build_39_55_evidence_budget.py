from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_35_55_task_foundation import quest_xp_at_level
from lib.questie_source import load_questie


XP_TO_NEXT = {
    39: 70100,
    40: 74300,
    41: 78500,
    42: 82800,
    43: 87100,
    44: 91600,
    45: 96300,
    46: 101000,
    47: 105800,
    48: 110700,
    49: 115700,
    50: 120900,
    51: 126100,
    52: 131500,
    53: 137000,
    54: 142500,
}


@dataclass(frozen=True)
class Block:
    name: str
    completion_level: int
    core: tuple[int, ...]
    conditional: tuple[int, ...] = ()
    kill_xp_low: int = 0
    kill_xp_high: int = 0
    minutes_low: int = 0
    minutes_high: int = 0


BLOCKS = (
    Block(
        "菲拉斯首圈",
        40,
        (2862, 2863, 2902, 2903, 2973, 2974, 2975, 2978),
        (2987,),
        18000,
        30000,
        75,
        110,
    ),
    Block(
        "赛车场与塔纳利斯",
        43,
        (1117, 1183, 1186, 1190, 1194, 1690, 1691, 2781, 2872, 2873, 2875, 8366, 992, 5863),
        (1187, 1707, 8365, 82),
        35000,
        60000,
        180,
        260,
    ),
    Block(
        "菲拉斯第二圈",
        46,
        (2980, 7730, 7731, 7732, 2976),
        (),
        18000,
        30000,
        60,
        95,
    ),
    Block(
        "辛特兰外圈与恶齿村",
        48,
        (7815, 7816, 7828, 7829, 7830, 7840, 7841, 7842, 7844),
        (7839,),
        30000,
        50000,
        105,
        160,
    ),
    Block(
        "辛特兰辛萨罗叠加块",
        49,
        (7845, 7846, 7847, 7849, 7850, 7861, 7862),
        (),
        35000,
        60000,
        80,
        130,
    ),
    Block(
        "灼热峡谷核心",
        50,
        (3441, 3442, 3443, 3452, 3453, 3454, 3462, 3463, 7701, 7722, 7723, 7724, 7727, 7729),
        (4449, 4451, 7702, 7728),
        40000,
        70000,
        150,
        225,
    ),
    Block(
        "安戈洛核心一圈",
        52,
        (3844, 3845, 3881, 3882, 3883, 4145, 4243, 4244, 4245, 4289, 4290, 4291, 4292, 4301, 4491, 4492, 4501),
        (4284, 4285, 4287, 4288, 4494, 4496, 4503, 4507, 4509, 4511, 974, 980),
        50000,
        85000,
        175,
        265,
    ),
    Block(
        "费伍德零缺口备用块",
        53,
        (8460, 5155, 4505, 6162),
        (8462,),
        18000,
        30000,
        55,
        90,
    ),
    Block(
        "西瘟疫核心",
        54,
        (5228, 5229, 5230, 5231, 5232, 5233, 5234, 4971, 5021, 5058, 5098),
        (5235, 5236, 4984, 4985, 6004, 5060, 4972),
        45000,
        80000,
        145,
        230,
    ),
)


def advance(level: int, progress: int, gained: int) -> tuple[int, int]:
    progress += gained
    while level in XP_TO_NEXT and progress >= XP_TO_NEXT[level]:
        progress -= XP_TO_NEXT[level]
        level += 1
    return level, progress


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    foundation = json.loads(
        (root / "data/routes/horde/blood-elf/35-55-task-foundation-enriched.json").read_text(encoding="utf-8")
    )
    tasks = {int(row["quest_id"]): row for row in foundation["tasks"]}
    questie = load_questie(root / "_sandbox/sources/Questie-v11.32.3.zip")

    level = 39
    progress = 40893
    rows = []
    total_core = 0
    total_conditional = 0
    total_kill_low = 0
    total_kill_high = 0
    missing: set[int] = set()

    for block in BLOCKS:
        core_xp = 0
        conditional_xp = 0
        task_rows = []
        for category, ids in (("core", block.core), ("conditional", block.conditional)):
            for quest_id in ids:
                task = tasks.get(quest_id)
                if task is None:
                    xp = quest_xp_at_level(questie, quest_id, block.completion_level)
                    if xp <= 0:
                        missing.add(quest_id)
                        task_rows.append({"quest_id": quest_id, "category": category, "xp": None})
                        continue
                    task_name = f"Questie:{quest_id}"
                else:
                    xp = int(task.get("xp_by_completion_level", {}).get(str(block.completion_level), 0))
                    task_name = task.get("name")
                task_rows.append(
                    {
                        "quest_id": quest_id,
                        "name": task_name,
                        "category": category,
                        "xp": xp,
                    }
                )
                if category == "core":
                    core_xp += xp
                else:
                    conditional_xp += xp

        low_gain = core_xp + block.kill_xp_low
        high_gain = core_xp + conditional_xp + block.kill_xp_high
        low_end = advance(level, progress, low_gain)
        high_end = advance(level, progress, high_gain)
        # Progress the baseline simulation with the midpoint of core kill XP and
        # half the conditional reward. This is only a planning baseline, not a
        # claim about the final route.
        midpoint_gain = core_xp + (conditional_xp // 2) + (block.kill_xp_low + block.kill_xp_high) // 2
        level, progress = advance(level, progress, midpoint_gain)

        rows.append(
            {
                "block": block.name,
                "completion_level_assumption": block.completion_level,
                "core_task_xp": core_xp,
                "conditional_task_xp": conditional_xp,
                "kill_xp_range": [block.kill_xp_low, block.kill_xp_high],
                "minutes_range": [block.minutes_low, block.minutes_high],
                "gain_range": [low_gain, high_gain],
                "baseline_end": [level, progress],
                "low_end_from_block_start": list(low_end),
                "high_end_from_block_start": list(high_end),
                "tasks": task_rows,
            }
        )
        total_core += core_xp
        total_conditional += conditional_xp
        total_kill_low += block.kill_xp_low
        total_kill_high += block.kill_xp_high

    remaining = XP_TO_NEXT[39] - 40893 + sum(XP_TO_NEXT[level] for level in range(40, 55))
    result = {
        "schema_version": 1,
        "start": [39, 40893],
        "target_level": 55,
        "xp_required": remaining,
        "blocks": rows,
        "totals": {
            "core_task_xp": total_core,
            "conditional_task_xp": total_conditional,
            "kill_xp_range": [total_kill_low, total_kill_high],
            "total_xp_range": [
                total_core + total_kill_low,
                total_core + total_conditional + total_kill_high,
            ],
            "minutes_range_without_cross_zone_transport": [
                sum(block.minutes_low for block in BLOCKS),
                sum(block.minutes_high for block in BLOCKS),
            ],
            "baseline_simulated_end": [level, progress],
        },
        "missing_quest_ids": sorted(missing),
        "notes": [
            "任务奖励已包含项目配置中的服务器双倍任务经验。",
            "击杀经验和分钟区间是待实跑标定的任务块级估算，不是最终保证值。",
            "跨大陆与飞行交通尚未加入分钟合计。",
        ],
    }
    output = root / "data/routes/horde/blood-elf/39-55-evidence-budget-draft.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["totals"] | {"xp_required": remaining, "missing": sorted(missing)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
