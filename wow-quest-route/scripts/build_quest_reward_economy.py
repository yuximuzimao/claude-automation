from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = ROOT / "data/route-atlas/northrend-task-universe.json"
OUT = ROOT / "data/route-atlas/quest-reward-economy.json"

# AzerothCore 3.3.5a 官方基础库（含 RewardMoney / SellPrice）。
# jsDelivr 对大文件会截断，item_template 走 gh-proxy 镜像；两者都已对 Wowhead 抽验一致。
CACHE = Path("/tmp/ac_worlddb_cache")
QUEST_URLS = [
    "https://cdn.jsdelivr.net/gh/azerothcore/azerothcore-wotlk@master/data/sql/base/db_world/quest_template.sql",
    "https://gh-proxy.com/https://raw.githubusercontent.com/azerothcore/azerothcore-wotlk/master/data/sql/base/db_world/quest_template.sql",
]
ITEM_URLS = [
    "https://gh-proxy.com/https://raw.githubusercontent.com/azerothcore/azerothcore-wotlk/master/data/sql/base/db_world/item_template.sql",
    "https://cdn.jsdelivr.net/gh/azerothcore/azerothcore-wotlk@master/data/sql/base/db_world/item_template.sql",
]

COPPER_PER_XP = 6  # wowpedia: 满级任务经验折金 6铜/XP；AC QuestDef.cpp 注释同口径
NO_MONEY_FROM_XP_FLAG = 0x2000000  # QUEST_FLAGS_NO_MONEY_FROM_XP

# AzerothCore quest_template 列索引（CREATE TABLE 顺序，列名见生成物 meta）
QCOL = {"id": 0, "level": 2, "money": 13, "item1": 22, "item2": 24, "item3": 26, "item4": 28,
        "choice1": 38, "choice2": 40, "choice3": 42, "choice4": 44, "choice5": 46, "choice6": 48}
ICOL = {"entry": 0, "class": 1, "subclass": 2, "name": 4, "sell": 11}


def _download(urls: list[str], dest: Path) -> None:
    for url in urls:
        try:
            subprocess.run(
                ["curl", "-sL", "--max-time", "480", "-o", str(dest), url],
                check=True, capture_output=True,
            )
            if dest.stat().st_size > 1_000_000:
                return
        except subprocess.CalledProcessError:
            continue
    raise RuntimeError(f"下载失败: {dest.name}")


def _fetch(urls: list[str], name: str) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / name
    if not dest.exists() or dest.stat().st_size < 1_000_000:
        _download(urls, dest)
    return dest.read_text(encoding="utf-8", errors="replace")


def _parse_tuples(chunk: str) -> list[list[str]]:
    """解析 MySQL dump INSERT 的元组流，处理引号转义与嵌套括号。"""
    rows: list[list[str]] = []
    i, n = 0, len(chunk)
    while i < n:
        if chunk[i] != "(":
            i += 1
            continue
        row: list[str] = []
        field = ""
        in_str = False
        depth = 1
        j = i + 1
        while j < n and depth > 0:
            c = chunk[j]
            if in_str:
                if c == "\\" and j + 1 < n:
                    field += chunk[j + 1]
                    j += 2
                    continue
                if c == "'":
                    if j + 1 < n and chunk[j + 1] == "'":
                        field += "'"
                        j += 2
                        continue
                    in_str = False
                    j += 1
                    continue
                field += c
                j += 1
                continue
            if c == "'":
                in_str = True
                j += 1
                continue
            if c == "(":
                depth += 1
                field += c
                j += 1
                continue
            if c == ")":
                depth -= 1
                if depth == 0:
                    row.append(field.strip())
                    rows.append(row)
                    i = j + 1
                    break
                field += c
                j += 1
                continue
            if c == ",":
                row.append(field.strip())
                field = ""
                j += 1
                continue
            field += c
            j += 1
        else:
            break
    return rows


def _parse_dump(text: str, table: str) -> list[list[str]]:
    rows: list[list[str]] = []
    buf: list[str] = []
    in_insert = False
    for line in text.splitlines(keepends=True):
        if not in_insert:
            if line.startswith(f"INSERT INTO `{table}` VALUES"):
                in_insert = True
                buf = [line.split("VALUES", 1)[1]]
            continue
        buf.append(line)
        if re.search(r";\s*$", line):
            in_insert = False
            rows.extend(_parse_tuples("".join(buf)))
            buf = []
    return rows


def _int(value: str) -> int:
    return int(value) if value not in ("", "NULL", "0") else 0


def main() -> None:
    universe = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    quest_rows = _parse_dump(_fetch(QUEST_URLS, "quest_template.sql"), "quest_template")
    item_rows = _parse_dump(_fetch(ITEM_URLS, "item_template.sql"), "item_template")

    items: dict[int, dict[str, Any]] = {}
    for row in item_rows:
        items[int(row[ICOL["entry"]])] = {
            "name": row[ICOL["name"]],
            "class": _int(row[ICOL["class"]]),
            "subclass": _int(row[ICOL["subclass"]]),
            "sell_copper": _int(row[ICOL["sell"]]),
        }
    quests: dict[int, list[str]] = {int(r[0]): r for r in quest_rows}

    # universe 奖励物品的中文名优先（Questie zhCN），AC 只提供英文名兜底
    zh_names: dict[int, str] = {}
    for task in universe["tasks"]:
        for bucket in ("equipment_rewards", "other_reward_items"):
            for item in task.get("rewards", {}).get(bucket, []):
                zh_names.setdefault(item["item_id"], item.get("name", ""))

    def item_view(item_id: int) -> dict[str, Any]:
        src = items.get(item_id, {})
        return {
            "item_id": item_id,
            "name": zh_names.get(item_id) or src.get("name", ""),
            "sell_copper": src.get("sell_copper", 0),
        }

    result_quests: dict[str, Any] = {}
    unmatched: list[int] = []
    for task in universe["tasks"]:
        qid = task["quest_id"]
        row = quests.get(qid)
        if row is None:
            unmatched.append(qid)
            continue
        no_xp_money = bool(task.get("quest_flags", 0) & NO_MONEY_FROM_XP_FLAG)
        xp_gold = 0
        xp = task.get("xp") or {}
        if not no_xp_money:
            xp_gold = int((xp.get("max_level_bonus_money") or {}).get("bonus_money_from_xp_copper") or 0)
        fixed = [item_view(i) for i in (_int(row[QCOL[k]]) for k in ("item1", "item2", "item3", "item4")) if i]
        choice = sorted(
            (item_view(i) for i in (_int(row[QCOL[k]]) for k in ("choice1", "choice2", "choice3", "choice4", "choice5", "choice6")) if i),
            key=lambda x: -x["sell_copper"],
        )
        reward_money = int(row[QCOL["money"]])
        gear_max = sum(i["sell_copper"] for i in fixed) + (choice[0]["sell_copper"] if choice else 0)
        result_quests[str(qid)] = {
            "name": task["name"],
            "zone": task["assigned_zone_name"],
            "eligibility": (task.get("eligibility") or {}).get("status"),
            "reward_money_copper": reward_money,
            "xp_gold_copper": xp_gold,
            "no_money_from_xp": no_xp_money,
            "fixed_items": fixed,
            "choice_items_desc_by_sell": choice,
            "gear_sale_max_copper": gear_max,
            # 满级交任务两种内核口径：TC3.3.5=取max；AzerothCore=相加。
            # 17173时光服实测11095G与本表max口径10984G吻合，本服按max采信。
            "at80_money_max_copper": max(reward_money, xp_gold),
            "at80_money_additive_copper": reward_money + xp_gold,
        }

    zone_summary: dict[str, Any] = {}
    for task in universe["tasks"]:
        entry = result_quests.get(str(task["quest_id"]))
        if not entry or entry["eligibility"] != "eligible_first_run":
            continue
        z = zone_summary.setdefault(entry["zone"], {
            "eligible_quests": 0, "at80_money_max_copper": 0,
            "at80_money_additive_copper": 0, "gear_sale_max_copper": 0,
        })
        z["eligible_quests"] += 1
        z["at80_money_max_copper"] += entry["at80_money_max_copper"]
        z["at80_money_additive_copper"] += entry["at80_money_additive_copper"]
        z["gear_sale_max_copper"] += entry["gear_sale_max_copper"]

    referenced: dict[str, Any] = {}
    for entry in result_quests.values():
        for item in entry["fixed_items"] + entry["choice_items_desc_by_sell"]:
            if str(item["item_id"]) not in referenced:
                referenced[str(item["item_id"])] = item_view(item["item_id"])

    quest_sql = (CACHE / "quest_template.sql").read_bytes()
    out = {
        "schema_version": 1,
        "status": "quest_reward_economy_reference",
        "generated": "2026-08-28",
        "sources": {
            "quest_template": {
                "repo": "azerothcore/azerothcore-wotlk master data/sql/base/db_world/quest_template.sql",
                "columns": {"ID": 0, "QuestLevel": 2, "RewardMoney": 13,
                            "RewardItem1-4": "22/24/26/28", "RewardChoiceItemID1-6": "38/40/42/44/46/48"},
                "sha256": hashlib.sha256(quest_sql).hexdigest(),
            },
            "item_template": {
                "repo": "azerothcore/azerothcore-wotlk master data/sql/base/db_world/item_template.sql",
                "columns": {"entry": 0, "class": 1, "subclass": 2, "name": 4, "SellPrice": 11},
            },
            "cross_validation": [
                "任务13010 RewardMoney=14800铜(14g80s) 与 Wowhead wotlk/quest=13010 'You will also receive: 14 80' 一致",
                "物品42793 SellPrice=39056铜(3g90s56c) 与 Wowhead wotlk/item=42793 'Sell Price: 3 90 56' 一致",
                "满级折金6铜/XP：wowpedia Quest + AzerothCore QuestDef.cpp(引wowpedia) + Wowhead 13010评论'16g 53s at 80'=27550XP*6铜 三方一致",
                "全诺森德eligible一次性任务max口径合计10984G 与17173时光服实测11095G(2026-04)吻合",
            ],
        },
        "mechanics": {
            "xp_to_gold": "满级交任务时经验按6铜/XP折金，使用基础XP（不吃服务器2x经验倍率）",
            "at80_money": "满级到手金币两种内核口径：TC3.3.5=max(RewardMoney, 折金)；AzerothCore=两者相加。本服采信max口径：同为时光服的17173实测全清11095G与本表max口径10984G吻合，相加口径15733G与实测明显不符",
            "pre80_money": "未满级交任务只给RewardMoney，经验不折金",
            "choice_reward": "可选奖励六选一只拿一件，估值按最贵一件；选最贵vs选最便宜全诺森德差约903G",
            "flag_no_money_from_xp": "quest_flags含0x2000000(QUEST_FLAGS_NO_MONEY_FROM_XP)时满级不折金，只给RewardMoney",
        },
        "unmatched_universe_quest_ids": unmatched,
        "zone_summary_eligible_first_run": zone_summary,
        "items": referenced,
        "quests": result_quests,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    eligible = sum(1 for e in result_quests.values() if e["eligibility"] == "eligible_first_run")
    total_max = sum(e["at80_money_max_copper"] for e in result_quests.values() if e["eligibility"] == "eligible_first_run")
    total_gear = sum(e["gear_sale_max_copper"] for e in result_quests.values() if e["eligibility"] == "eligible_first_run")
    print(f"任务 {len(result_quests)} 条（universe未匹配 {len(unmatched)}）；eligible {eligible} 项")
    print(f"eligible满级max口径金币 {total_max/10000:.0f}G + 装备卖店 {total_gear/10000:.0f}G = {(total_max+total_gear)/10000:.0f}G")
    print(f"物品 {len(referenced)} 件；输出 {OUT}")


if __name__ == "__main__":
    main()
