from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.questie_source import load_questie
from scripts.build_35_55_task_foundation import quest_xp_at_level
from scripts.build_39_55_evidence_budget import XP_TO_NEXT, advance


@dataclass(frozen=True)
class Block:
    name: str
    level: int
    core: tuple[int, ...]
    natural: tuple[int, ...] = ()
    kill_xp: tuple[int, int] = (0, 0)
    minutes: tuple[int, int] = (0, 0)


BLOCKS = (
    Block(
        "菲拉斯首圈",
        40,
        (2862, 2863, 2902, 2903, 2973, 2974, 2975, 2978),
        (2987,),
        (18000, 30000),
        (70, 105),
    ),
    Block(
        "赛车场与塔纳利斯第一轮",
        43,
        (
            1117, 1183, 1186, 1190, 1194,
            1690, 1691, 2781,
            2875, 8366,
            992,
        ),
        (1187, 1707, 8365, 82, 10, 2872, 2873, 2876),
        (30000, 52000),
        (130, 190),
    ),
    Block(
        "菲拉斯高等级回访与灵魂链",
        47,
        (
            2980, 3062, 3063, 3520, 7730, 7731, 7732, 2976,
            3121, 3122, 3123, 3124, 3125, 3126, 3127,
        ),
        (),
        (50000, 82000),
        (135, 205),
    ),
    Block(
        "塔纳利斯高等级收尾",
        47,
        (5863, 3362, 2605, 2606),
        (),
        (13000, 20000),
        (45, 75),
    ),
    Block(
        "辛特兰恶齿村与辛萨罗",
        49,
        (
            7815, 7816, 7828, 7829, 7830,
            7840, 7841, 7842, 7844,
            7845, 7846, 7847, 7849, 7850, 7861, 7862,
        ),
        (7839, 485),
        (65000, 105000),
        (175, 250),
    ),
    Block(
        "灼热峡谷核心",
        51,
        (
            3441, 3442, 3443, 3452, 3453, 3454, 3462, 3463,
            7701, 7722, 7723, 7724, 7727, 7729,
        ),
        (4451, 7702, 7704, 7728),
        (42000, 70000),
        (130, 195),
    ),
    Block(
        "西瘟疫四锅、安多哈尔与未竟事业",
        54,
        (
            5094, 5096, 5098,
            5228, 5229, 5230, 5231, 5232, 5233, 5234, 5235, 5236, 5237,
            4971, 5021,
            6004, 6023, 6025,
            4984, 4985,
            5142,
        ),
        (4972,),
        (70000, 115000),
        (175, 260),
    ),
    Block(
        "帕米拉历史链与东瘟最短收尾",
        54,
        (
            5149, 5152, 5153, 5154, 5210, 5241, 5211,
            5543, 6042, 6021,
        ),
        (6024, 6133, 6164, 5542),
        (42000, 75000),
        (75, 125),
    ),
)


def task_xp(task_by_id: dict[int, dict], questie: dict, quest_id: int, level: int) -> int:
    task = task_by_id.get(quest_id)
    if task:
        value = task.get("xp_by_completion_level", {}).get(str(level))
        if value is not None:
            return int(value)
    return int(quest_xp_at_level(questie, quest_id, level))


def main() -> None:
    payload = json.loads(
        (ROOT / "data/routes/horde/blood-elf/35-55-task-foundation-enriched.json").read_text(encoding="utf-8")
    )
    task_by_id = {int(row["quest_id"]): row for row in payload["tasks"]}
    questie = load_questie(ROOT / "_sandbox/sources/Questie-v11.32.3.zip")

    rows = []
    total_core = total_natural = total_kill_low = total_kill_high = 0
    total_min_low = total_min_high = 0
    missing: set[int] = set()
    level, progress = 39, 40893

    for block in BLOCKS:
        core_xp = 0
        natural_xp = 0
        tasks = []
        for category, ids in (("core", block.core), ("natural", block.natural)):
            for quest_id in ids:
                xp = task_xp(task_by_id, questie, quest_id, block.level)
                if xp <= 0:
                    missing.add(quest_id)
                name = task_by_id.get(quest_id, {}).get("name", f"Questie:{quest_id}")
                tasks.append({"quest_id": quest_id, "name": name, "category": category, "xp": xp})
                if category == "core":
                    core_xp += xp
                else:
                    natural_xp += xp
        midpoint = core_xp + natural_xp // 2 + sum(block.kill_xp) // 2
        level, progress = advance(level, progress, midpoint)
        rows.append(
            {
                "block": block.name,
                "completion_level_assumption": block.level,
                "core_task_xp": core_xp,
                "natural_task_xp": natural_xp,
                "kill_xp_range": list(block.kill_xp),
                "minutes_range": list(block.minutes),
                "midpoint_end": [level, progress],
                "tasks": tasks,
            }
        )
        total_core += core_xp
        total_natural += natural_xp
        total_kill_low += block.kill_xp[0]
        total_kill_high += block.kill_xp[1]
        total_min_low += block.minutes[0]
        total_min_high += block.minutes[1]

    required = XP_TO_NEXT[39] - 40893 + sum(XP_TO_NEXT[level] for level in range(40, 55))
    output = {
        "schema_version": 1,
        "scenario": "zero_purchase_single_video_independent_eastern_kingdoms_finish",
        "start": [39, 40893],
        "target_level": 55,
        "xp_required": required,
        "blocks": rows,
        "totals": {
            "core_task_xp": total_core,
            "natural_task_xp": total_natural,
            "kill_xp_range": [total_kill_low, total_kill_high],
            "xp_range": [
                total_core + total_kill_low,
                total_core + total_natural + total_kill_high,
            ],
            "margin_range": [
                total_core + total_kill_low - required,
                total_core + total_natural + total_kill_high - required,
            ],
            "minutes_range_before_interzone_transport_calibration": [total_min_low, total_min_high],
            "midpoint_end": [level, progress],
        },
        "missing_quest_ids": sorted(missing),
        "assumptions": [
            "不购买、邮寄或制作任务材料。",
            "单号视频仅提供机制和地点证据，不限制任务候选或地图顺序。",
            "主号正常战斗、短跳和短暂手动走位不计五开额外惩罚。",
            "尸体/场景物使用按队伍共享或短串行操作处理，不假设必须同时输入。",
            "安戈洛和费伍德均从主轴删除；东瘟只做足够达到55的前缀，达到55立即停止。",
        ],
    }
    path = ROOT / "data/routes/horde/blood-elf/39-55-eastern-kingdoms-candidate.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output["totals"] | {"xp_required": required, "missing": sorted(missing)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
