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
    completion_level: int
    guaranteed: tuple[int, ...]
    free_conditional: tuple[int, ...] = ()
    owned_material_bonus: tuple[int, ...] = ()
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
        kill_xp_low=18000,
        kill_xp_high=30000,
        minutes_low=70,
        minutes_high=105,
    ),
    Block(
        "赛车场与塔纳利斯核心",
        43,
        (
            1117, 1183, 1186, 1190, 1194,
            1690, 1691, 2781,
            2872, 2873, 2875, 8366,
            992, 5863, 3362,
        ),
        (1187, 1707, 8365, 82, 10, 2876),
        kill_xp_low=35000,
        kill_xp_high=60000,
        minutes_low=155,
        minutes_high=225,
    ),
    Block(
        "塔纳利斯佐料链起点",
        45,
        (2605, 2606),
        (),
        kill_xp_low=4000,
        kill_xp_high=9000,
        minutes_low=12,
        minutes_high=25,
    ),
    Block(
        "菲拉斯高等级回访",
        46,
        (
            2980, 3062, 3063, 3520, 7730, 7731, 7732, 2976,
            3121, 3122, 3123, 3124, 3125, 3126, 3127,
        ),
        (),
        kill_xp_low=50000,
        kill_xp_high=82000,
        minutes_low=135,
        minutes_high=205,
    ),
    Block(
        "辛特兰恶齿村与辛萨罗",
        49,
        (
            7815, 7816, 7828, 7829, 7830,
            7840, 7841, 7842, 7844,
            7845, 7846, 7847, 7849, 7850, 7861, 7862,
            2641,
        ),
        (7839, 485),
        kill_xp_low=65000,
        kill_xp_high=105000,
        minutes_low=175,
        minutes_high=250,
    ),
    Block(
        "灼热峡谷核心",
        50,
        (
            3441, 3442, 3443, 3452, 3453, 3454, 3462, 3463,
            7701, 7722, 7723, 7724, 7727, 7729,
        ),
        (4451, 7702, 7704, 7728),
        # 4449 is intentionally excluded: it requires 75 Silk Cloth for five characters.
        kill_xp_low=42000,
        kill_xp_high=70000,
        minutes_low=130,
        minutes_high=195,
    ),
    Block(
        "炉石加基森集中交付",
        51,
        (2661,),
        (2662,),
        kill_xp_low=0,
        kill_xp_high=0,
        minutes_low=3,
        minutes_high=8,
    ),
    Block(
        "安戈洛零购买核心",
        52,
        (
            3844, 3845, 3881, 3882, 3883, 4145,
            4289, 4290, 4291, 4292, 4301,
            4491, 4492, 4501,
        ),
        (
            3884, 4284, 4285, 4287, 4288,
            4494, 4496, 4503, 4507, 4509, 4511,
            974, 980,
        ),
        # A-Me repair/escort is bonus-only when five Mithril Casings are already owned.
        owned_material_bonus=(4243, 4244, 4245),
        kill_xp_low=48000,
        kill_xp_high=82000,
        minutes_low=145,
        minutes_high=215,
    ),
    Block(
        "西瘟疫四锅与安多哈尔",
        54,
        (
            5094, 5096, 5098,
            5228, 5229, 5230, 5231, 5232, 5233, 5234, 5235, 5236, 5237,
            4971, 5021,
            6004, 6023, 6025,
            4984, 4985,
        ),
        (4972, 5050, 5051, 5060),
        kill_xp_low=65000,
        kill_xp_high=105000,
        minutes_low=155,
        minutes_high=235,
    ),
    Block(
        "费伍德免费备用块",
        54,
        (),
        (8460, 5155, 4505, 6162, 8462),
        kill_xp_low=0,
        kill_xp_high=30000,
        minutes_low=0,
        minutes_high=90,
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
        (ROOT / "data/routes/horde/blood-elf/35-55-task-foundation-enriched.json").read_text(
            encoding="utf-8"
        )
    )
    task_by_id = {int(row["quest_id"]): row for row in payload["tasks"]}
    questie = load_questie(ROOT / "_sandbox/sources/Questie-v11.32.3.zip")

    totals = {
        "guaranteed_task_xp": 0,
        "free_conditional_task_xp": 0,
        "owned_material_bonus_xp": 0,
        "kill_xp_low": 0,
        "kill_xp_high": 0,
        "minutes_low": 0,
        "minutes_high": 0,
    }
    blocks = []
    missing: set[int] = set()

    for block in BLOCKS:
        row = {
            "block": block.name,
            "completion_level": block.completion_level,
            "guaranteed": [],
            "free_conditional": [],
            "owned_material_bonus": [],
            "kill_xp_range": [block.kill_xp_low, block.kill_xp_high],
            "minutes_range": [block.minutes_low, block.minutes_high],
        }
        for field, ids in (
            ("guaranteed", block.guaranteed),
            ("free_conditional", block.free_conditional),
            ("owned_material_bonus", block.owned_material_bonus),
        ):
            subtotal = 0
            for quest_id in ids:
                xp = task_xp(task_by_id, questie, quest_id, block.completion_level)
                if xp <= 0 and quest_id != 2662:
                    missing.add(quest_id)
                name = task_by_id.get(quest_id, {}).get("name", f"Questie:{quest_id}")
                row[field].append({"quest_id": quest_id, "name": name, "xp": xp})
                subtotal += xp
            row[f"{field}_xp"] = subtotal
            totals[f"{field}_task_xp" if field != "owned_material_bonus" else "owned_material_bonus_xp"] += subtotal
        totals["kill_xp_low"] += block.kill_xp_low
        totals["kill_xp_high"] += block.kill_xp_high
        totals["minutes_low"] += block.minutes_low
        totals["minutes_high"] += block.minutes_high
        blocks.append(row)

    required = XP_TO_NEXT[39] - 40893 + sum(XP_TO_NEXT[level] for level in range(40, 55))
    guaranteed_low = totals["guaranteed_task_xp"] + totals["kill_xp_low"]
    free_pool_high = (
        totals["guaranteed_task_xp"]
        + totals["free_conditional_task_xp"]
        + totals["kill_xp_high"]
    )
    output = {
        "schema_version": 1,
        "scenario": "zero_purchase_incremental_control_cost",
        "start": [39, 40893],
        "target_level": 55,
        "xp_required": required,
        "assumptions": [
            "保证路线不购买、不邮寄、不制作任务材料。",
            "主号正常打怪、骑乘、短跳和一次任务物使用属于基线控制，不作为五开额外惩罚。",
            "逐号切换、逐号拾取、断跟随、等待刷新和失败重跑才计入额外成本。",
            "已经持有的秘银外壳等材料只开启额外奖励分支，不计入保证经验。",
        ],
        "blocks": blocks,
        "totals": totals,
        "guaranteed_low_xp": guaranteed_low,
        "free_pool_high_xp": free_pool_high,
        "free_pool_margin": free_pool_high - required,
        "owned_material_pool_high_xp": free_pool_high + totals["owned_material_bonus_xp"],
        "missing_quest_ids": sorted(missing),
    }
    path = ROOT / "data/routes/horde/blood-elf/39-55-zero-purchase-budget.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "xp_required": required,
                "guaranteed_task_xp": totals["guaranteed_task_xp"],
                "free_conditional_task_xp": totals["free_conditional_task_xp"],
                "owned_material_bonus_xp": totals["owned_material_bonus_xp"],
                "kill_xp_range": [totals["kill_xp_low"], totals["kill_xp_high"]],
                "guaranteed_low_xp": guaranteed_low,
                "free_pool_high_xp": free_pool_high,
                "free_pool_margin": free_pool_high - required,
                "minutes_range": [totals["minutes_low"], totals["minutes_high"]],
                "missing": sorted(missing),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
