from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .questie_effective import QUEST_FLAGS, QUEST_KEYS
from .questie_source import QuestieData

CACHE = Path("/tmp/ac_worlddb_cache")
QUEST_URLS = [
    "https://cdn.jsdelivr.net/gh/azerothcore/azerothcore-wotlk@master/data/sql/base/db_world/quest_template.sql",
    "https://gh-proxy.com/https://raw.githubusercontent.com/azerothcore/azerothcore-wotlk/master/data/sql/base/db_world/quest_template.sql",
]
ITEM_URLS = [
    "https://gh-proxy.com/https://raw.githubusercontent.com/azerothcore/azerothcore-wotlk/master/data/sql/base/db_world/item_template.sql",
    "https://cdn.jsdelivr.net/gh/azerothcore/azerothcore-wotlk@master/data/sql/base/db_world/item_template.sql",
]

# AzerothCore quest_template / item_template column positions for the current base SQL layout.
QCOL = {
    "id": 0,
    "money": 13,
    "item1": 22,
    "item1_count": 23,
    "item2": 24,
    "item2_count": 25,
    "item3": 26,
    "item3_count": 27,
    "item4": 28,
    "item4_count": 29,
    "choice1": 38,
    "choice1_count": 39,
    "choice2": 40,
    "choice2_count": 41,
    "choice3": 42,
    "choice3_count": 43,
    "choice4": 44,
    "choice4_count": 45,
    "choice5": 46,
    "choice5_count": 47,
    "choice6": 48,
    "choice6_count": 49,
}
ICOL = {"entry": 0, "class": 1, "subclass": 2, "name": 4, "sell": 11}


@dataclass(frozen=True)
class RewardDatabase:
    quest_template_text: str
    item_template_text: str
    quest_template_sha256: str
    item_template_sha256: str


def _download(urls: list[str], dest: Path) -> None:
    for url in urls:
        try:
            subprocess.run(
                ["curl", "-sL", "--max-time", "480", "-o", str(dest), url],
                check=True,
                capture_output=True,
            )
            if dest.exists() and dest.stat().st_size > 1_000_000:
                return
        except subprocess.CalledProcessError:
            continue
    raise RuntimeError(f"下载失败: {dest.name}")


def _fetch(urls: list[str], name: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / name
    if not dest.exists() or dest.stat().st_size < 1_000_000:
        _download(urls, dest)
    return dest


def _parse_tuples(chunk: str) -> list[list[str]]:
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


def _parse_row_at(text: str, start: int) -> list[str]:
    if start < 0 or start >= len(text) or text[start] != "(":
        raise ValueError("tuple start is invalid")
    row: list[str] = []
    field = ""
    in_str = False
    depth = 1
    j = start + 1
    while j < len(text):
        c = text[j]
        if in_str:
            if c == "\\" and j + 1 < len(text):
                field += text[j + 1]
                j += 2
                continue
            if c == "'":
                if j + 1 < len(text) and text[j + 1] == "'":
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
                return row
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
    raise ValueError("unterminated SQL tuple")


def _find_row(text: str, record_id: int) -> list[str]:
    needle = f"({record_id},"
    start = text.find(needle)
    if start == -1:
        raise KeyError(record_id)
    row = _parse_row_at(text, start)
    if not row or int(row[0]) != record_id:
        raise KeyError(record_id)
    return row


def _scan_rows(text: str, record_ids: set[int]) -> dict[int, list[str]]:
    """Parse only requested SQL tuples in one linear scan of a base dump."""
    if not record_ids:
        return {}
    remaining = set(record_ids)
    rows: dict[int, list[str]] = {}
    for match in re.finditer(r"(?m)^\((\d+),", text):
        record_id = int(match.group(1))
        if record_id not in remaining:
            continue
        rows[record_id] = _parse_row_at(text, match.start())
        remaining.remove(record_id)
        if not remaining:
            break
    return rows


def _int(value: str | None) -> int:
    if value in (None, "", "NULL"):
        return 0
    return int(value)


def _no_money_from_xp_from_questie_row(row: dict[Any, Any] | None) -> bool | None:
    if not isinstance(row, dict):
        return None
    flags = row.get(QUEST_KEYS["questFlags"])
    if flags is None:
        flags = 0
    if not isinstance(flags, (int, float)) or isinstance(flags, bool):
        return None
    return bool(int(flags) & QUEST_FLAGS["NO_MONEY_FROM_XP"])


def load_reward_database() -> RewardDatabase:
    quest_path = _fetch(QUEST_URLS, "quest_template.sql")
    item_path = _fetch(ITEM_URLS, "item_template.sql")
    quest_text = quest_path.read_text(encoding="utf-8", errors="replace")
    item_text = item_path.read_text(encoding="utf-8", errors="replace")
    return RewardDatabase(
        quest_template_text=quest_text,
        item_template_text=item_text,
        quest_template_sha256=hashlib.sha256(quest_path.read_bytes()).hexdigest(),
        item_template_sha256=hashlib.sha256(item_path.read_bytes()).hexdigest(),
    )


def _reward_item(
    database: RewardDatabase,
    item_id: int,
    quantity: int,
    questie: QuestieData | None,
) -> dict[str, Any]:
    row = _find_row(database.item_template_text, item_id)
    sell_each = _int(row[ICOL["sell"]])
    name_en = row[ICOL["name"]] or None
    name_zhcn = None
    if questie is not None:
        localized = questie.item_names.get(item_id)
        if isinstance(localized, str):
            name_zhcn = localized
        elif isinstance(localized, dict) and isinstance(localized.get(1), str):
            name_zhcn = localized[1]
    return {
        "item_id": item_id,
        "quantity": quantity,
        "name_zhcn": name_zhcn,
        "name_en": name_en,
        "sell_price_each_copper": sell_each,
        "sell_price_total_copper": sell_each * quantity,
    }


def _questie_reputation_rewards(questie: QuestieData | None, quest_id: int) -> list[dict[str, int]]:
    if questie is None:
        return []
    raw = questie.quests.get(quest_id)
    if not isinstance(raw, dict):
        return []
    rewards = raw.get(26)
    if not isinstance(rewards, dict):
        return []
    result: list[dict[str, int]] = []
    for key in sorted(k for k in rewards if isinstance(k, int)):
        entry = rewards[key]
        if not isinstance(entry, dict):
            continue
        faction_id = entry.get(1)
        amount = entry.get(2)
        if isinstance(faction_id, (int, float)) and isinstance(amount, (int, float)):
            result.append({"faction_id": int(faction_id), "amount": int(amount)})
    return result


def quest_reward_facts(
    database: RewardDatabase,
    quest_id: int,
    *,
    questie: QuestieData | None = None,
    effective_quest_row: dict[Any, Any] | None = None,
) -> dict[str, Any]:
    try:
        row = _find_row(database.quest_template_text, quest_id)
    except KeyError as exc:
        raise KeyError(f"AzerothCore quest_template缺少任务 {quest_id}") from exc

    fixed: list[dict[str, Any]] = []
    for index in range(1, 5):
        item_id = _int(row[QCOL[f"item{index}"]])
        if not item_id:
            continue
        quantity = max(1, _int(row[QCOL[f"item{index}_count"]]))
        fixed.append(_reward_item(database, item_id, quantity, questie))

    choices: list[dict[str, Any]] = []
    for index in range(1, 7):
        item_id = _int(row[QCOL[f"choice{index}"]])
        if not item_id:
            continue
        quantity = max(1, _int(row[QCOL[f"choice{index}_count"]]))
        choices.append(_reward_item(database, item_id, quantity, questie))
    choices.sort(key=lambda item: (-item["sell_price_total_copper"], item["item_id"]))

    fixed_total = sum(item["sell_price_total_copper"] for item in fixed)
    choice_max = choices[0]["sell_price_total_copper"] if choices else 0
    result: dict[str, Any] = {
        "reward_money_copper": _int(row[QCOL["money"]]),
        "fixed_items": fixed,
        "choice_items_desc_by_sell": choices,
        "fixed_items_sell_total_copper": fixed_total,
        "choice_item_max_sell_copper": choice_max,
        "gear_sale_max_copper": fixed_total + choice_max,
        "reputation_rewards": _questie_reputation_rewards(questie, quest_id),
    }
    questie_row = effective_quest_row
    if questie_row is None and questie is not None:
        raw_row = questie.quests.get(quest_id)
        questie_row = raw_row if isinstance(raw_row, dict) else None
    no_money_from_xp = _no_money_from_xp_from_questie_row(questie_row)
    if no_money_from_xp is not None:
        result["no_money_from_xp"] = no_money_from_xp
    if questie is not None:
        xp_row = questie.quest_xp.get(quest_id)
        if isinstance(xp_row, dict) and isinstance(xp_row.get(2), int):
            result["full_xp"] = xp_row[2]
    return result


def _reputation_rewards_from_row(row: dict[Any, Any] | None) -> list[dict[str, int]]:
    if not isinstance(row, dict):
        return []
    rewards = row.get(26)
    if not isinstance(rewards, dict):
        return []
    result: list[dict[str, int]] = []
    for key in sorted(k for k in rewards if isinstance(k, int)):
        entry = rewards[key]
        if not isinstance(entry, dict):
            continue
        faction_id = entry.get(1)
        amount = entry.get(2)
        if isinstance(faction_id, (int, float)) and isinstance(amount, (int, float)):
            result.append({"faction_id": int(faction_id), "amount": int(amount)})
    return result


def batch_quest_reward_facts(
    database: RewardDatabase,
    quest_ids: set[int] | list[int] | tuple[int, ...],
    *,
    questie: QuestieData | None = None,
    effective_quest_rows: dict[int, dict[Any, Any]] | None = None,
) -> tuple[dict[int, dict[str, Any]], dict[str, Any]]:
    """Build exact reward facts for many quests with one scan per SQL dump."""
    wanted = {int(qid) for qid in quest_ids}
    quest_rows = _scan_rows(database.quest_template_text, wanted)

    reward_item_ids: set[int] = set()
    for row in quest_rows.values():
        for index in range(1, 5):
            item_id = _int(row[QCOL[f"item{index}"]])
            if item_id:
                reward_item_ids.add(item_id)
        for index in range(1, 7):
            item_id = _int(row[QCOL[f"choice{index}"]])
            if item_id:
                reward_item_ids.add(item_id)
    item_rows = _scan_rows(database.item_template_text, reward_item_ids)

    missing_items = sorted(reward_item_ids - set(item_rows))

    def item_view(item_id: int, quantity: int) -> dict[str, Any]:
        row = item_rows.get(item_id)
        if row is None:
            sell_each = 0
            name_en = None
        else:
            sell_each = _int(row[ICOL["sell"]])
            name_en = row[ICOL["name"]] or None
        name_zhcn = None
        if questie is not None:
            localized = questie.item_names.get(item_id)
            if isinstance(localized, str):
                name_zhcn = localized
            elif isinstance(localized, dict) and isinstance(localized.get(1), str):
                name_zhcn = localized[1]
        return {
            "item_id": item_id,
            "quantity": quantity,
            "name_zhcn": name_zhcn,
            "name_en": name_en,
            "sell_price_each_copper": sell_each,
            "sell_price_total_copper": sell_each * quantity,
        }

    result: dict[int, dict[str, Any]] = {}
    for quest_id, row in quest_rows.items():
        fixed: list[dict[str, Any]] = []
        for index in range(1, 5):
            item_id = _int(row[QCOL[f"item{index}"]])
            if not item_id:
                continue
            quantity = max(1, _int(row[QCOL[f"item{index}_count"]]))
            fixed.append(item_view(item_id, quantity))

        choices: list[dict[str, Any]] = []
        for index in range(1, 7):
            item_id = _int(row[QCOL[f"choice{index}"]])
            if not item_id:
                continue
            quantity = max(1, _int(row[QCOL[f"choice{index}_count"]]))
            choices.append(item_view(item_id, quantity))
        choices.sort(key=lambda item: (-item["sell_price_total_copper"], item["item_id"]))

        fixed_total = sum(item["sell_price_total_copper"] for item in fixed)
        choice_max = choices[0]["sell_price_total_copper"] if choices else 0
        questie_row = None
        if effective_quest_rows is not None:
            questie_row = effective_quest_rows.get(quest_id)
        elif questie is not None:
            questie_row = questie.quests.get(quest_id)
        facts: dict[str, Any] = {
            "reward_money_copper": _int(row[QCOL["money"]]),
            "fixed_items": fixed,
            "choice_items_desc_by_sell": choices,
            "fixed_items_sell_total_copper": fixed_total,
            "choice_item_max_sell_copper": choice_max,
            "gear_sale_max_copper": fixed_total + choice_max,
            "reputation_rewards": _reputation_rewards_from_row(questie_row),
        }
        no_money_from_xp = _no_money_from_xp_from_questie_row(questie_row)
        if no_money_from_xp is not None:
            facts["no_money_from_xp"] = no_money_from_xp
        if questie is not None:
            xp_row = questie.quest_xp.get(quest_id)
            if isinstance(xp_row, dict) and isinstance(xp_row.get(2), int):
                facts["full_xp"] = xp_row[2]
        result[quest_id] = facts

    audit = {
        "requested_quest_count": len(wanted),
        "matched_quest_count": len(quest_rows),
        "missing_quest_ids": sorted(wanted - set(quest_rows)),
        "reward_item_count": len(reward_item_ids),
        "matched_reward_item_count": len(item_rows),
        "missing_reward_item_ids": missing_items,
    }
    return result, audit
