from __future__ import annotations

import re
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

from .questie_lua import LuaParseError, LuaTableParser
from .questie_source import QuestieData

QUEST_KEYS = {
    "name": 1, "startedBy": 2, "finishedBy": 3, "requiredLevel": 4,
    "questLevel": 5, "requiredRaces": 6, "requiredClasses": 7,
    "objectivesText": 8, "triggerEnd": 9, "objectives": 10,
    "sourceItemId": 11, "preQuestGroup": 12, "preQuestSingle": 13,
    "childQuests": 14, "inGroupWith": 15, "exclusiveTo": 16,
    "zoneOrSort": 17, "requiredSkill": 18, "requiredMinRep": 19,
    "requiredMaxRep": 20, "requiredSourceItems": 21, "nextQuestInChain": 22,
    "questFlags": 23, "specialFlags": 24, "parentQuest": 25,
    "reputationReward": 26, "breadcrumbForQuestId": 27, "breadcrumbs": 28,
    "extraObjectives": 29, "requiredSpell": 30, "requiredSpecialization": 31,
    "requiredMaxLevel": 32, "availableUntilCompleted": 33,
    "availableStartingWith": 34, "disabledByQuest": 35, "requiredRanks": 36,
}
RACE_IDS = {
    "ALL_ALLIANCE": 1101, "ALL_HORDE": 690, "NONE": 0, "HUMAN": 1,
    "ORC": 2, "DWARF": 4, "NIGHT_ELF": 8, "UNDEAD": 16, "TAUREN": 32,
    "GNOME": 64, "TROLL": 128, "BLOOD_ELF": 512, "DRAENEI": 1024,
}
CLASS_IDS = {
    "ALL_CLASSES": 1535, "NONE": 0, "WARRIOR": 1, "PALADIN": 2,
    "HUNTER": 4, "ROGUE": 8, "PRIEST": 16, "DEATH_KNIGHT": 32,
    "SHAMAN": 64, "MAGE": 128, "WARLOCK": 256, "DRUID": 1024,
}
SPECIAL_FLAGS = {"NONE": 0, "REPEATABLE": 1}
QUEST_FLAGS = {
    "NONE": 0, "STAY_ALIVE": 1, "PARTY_ACCEPT": 2, "EXPLORATION": 4,
    "SHARABLE": 8, "UNUSED1": 16, "EPIC": 32, "RAID": 64,
    "UNUSED2": 128, "UNKNOWN": 256, "HIDDEN_REWARDS": 512,
    "AUTO_REWARDED": 1024, "DAILY": 4096, "WEEKLY": 32768, "MONTHLY": 65536,
}


def _reader(source: str | Path):
    path = Path(source).expanduser().resolve()
    if path.is_file() and path.suffix.lower() == ".zip":
        archive = zipfile.ZipFile(path)
        names = set(archive.namelist())
        prefix = "Questie/" if any(name.startswith("Questie/Database/") for name in names) else ""

        def read(relative: str) -> str:
            return archive.read(prefix + relative).decode("utf-8")

        return read
    root = path / "Questie" if (path / "Questie").is_dir() else path

    def read(relative: str) -> str:
        return (root / relative).read_text(encoding="utf-8")

    return read


def _balanced_end(text: str, brace_start: int) -> int:
    depth = 0
    quote: str | None = None
    escaped = False
    long_string = False
    i = brace_start
    while i < len(text):
        if long_string:
            if text.startswith("]]", i):
                long_string = False
                i += 2
                continue
            i += 1
            continue
        char = text[i]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            i += 1
            continue
        if text.startswith("[[", i):
            long_string = True
            i += 2
            continue
        if char in {'"', "'"}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError("Unbalanced Lua table")


def _simple_named_ints(text: str, marker: str) -> dict[str, int]:
    start = text.find(marker)
    if start == -1:
        return {}
    brace = text.find("{", start)
    if brace == -1:
        return {}
    block = text[brace + 1 : _balanced_end(text, brace) - 1]
    return {
        name: int(value)
        for name, value in re.findall(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*(-?\d+)\s*,?", block, re.M)
    }


def _candidate_blocks(text: str, quest_ids: set[int]) -> dict[int, str]:
    out: dict[int, str] = {}
    for match in re.finditer(r"^        \[(\d+)\]\s*=\s*\{", text, re.M):
        quest_id = int(match.group(1))
        if quest_id not in quest_ids:
            continue
        brace = text.find("{", match.start())
        out[quest_id] = text[brace:_balanced_end(text, brace)]
    return out


def _replace_namespace(text: str, namespace: str, values: dict[str, int]) -> str:
    pattern = re.compile(rf"\b{re.escape(namespace)}\.([A-Z][A-Z0-9_]*)\b")
    return pattern.sub(lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), text)


def _fold_numeric_addition(text: str) -> str:
    pattern = re.compile(r"(?<![\w.])(-?\d+)\s*\+\s*(-?\d+)(?![\w.])")
    while True:
        new = pattern.sub(lambda m: str(int(m.group(1)) + int(m.group(2))), text)
        if new == text:
            return text
        text = new


def parse_wotlk_quest_corrections(
    source: str | Path,
    quest_ids: Iterable[int],
) -> tuple[dict[int, dict[Any, Any]], dict[int, str], dict[str, Any]]:
    read = _reader(source)
    correction_text = read("Database/Corrections/wotlkQuestFixes.lua")
    ids = {int(qid) for qid in quest_ids}
    blocks = _candidate_blocks(correction_text, ids)

    quest_db_text = read("Database/questDB.lua")
    namespaces = {
        "raceIDs": RACE_IDS,
        "classIDs": CLASS_IDS,
        "factionIDs": _simple_named_ints(quest_db_text, "QuestieDB.factionIDs ="),
        "zoneIDs": _simple_named_ints(read("Database/Zones/data/zoneIds.lua"), "ZoneDB.zoneIDs ="),
        "sortKeys": _simple_named_ints(read("Database/Constants.lua"), "QuestieDB.sortKeys ="),
        "specialFlags": SPECIAL_FLAGS,
        "questFlags": QUEST_FLAGS,
    }

    parsed: dict[int, dict[Any, Any]] = {}
    failures: dict[int, str] = {}
    unresolved: dict[int, list[str]] = {}
    for quest_id, block in blocks.items():
        transformed = block
        for key, index in QUEST_KEYS.items():
            transformed = transformed.replace(f"[questKeys.{key}]", f"[{index}]")
        for namespace, values in namespaces.items():
            transformed = _replace_namespace(transformed, namespace, values)
        # Extra-objective icon constants affect only Questie rendering, not task facts.
        transformed = re.sub(r"\bQuestie\.ICON_TYPE_[A-Z0-9_]+\b", "0", transformed)
        # l10n("text") returns localized text at runtime; keep the literal as evidence text.
        transformed = re.sub(r'l10n\(("(?:\\.|[^"\\])*")\)', r'\1', transformed)
        transformed = re.sub(r"l10n\(('(?:\\.|[^'\\])*')\)", r"\1", transformed)
        transformed = _fold_numeric_addition(transformed)
        leftover = sorted(set(re.findall(
            r"\b(?:questKeys|raceIDs|classIDs|factionIDs|zoneIDs|sortKeys|specialFlags|questFlags)\.[A-Za-z_][A-Za-z0-9_]*",
            transformed,
        )))
        if leftover:
            unresolved[quest_id] = leftover
        try:
            value = LuaTableParser(transformed).parse()
        except (LuaParseError, ValueError) as exc:
            failures[quest_id] = str(exc)
            continue
        if isinstance(value, dict):
            parsed[quest_id] = value
        else:
            failures[quest_id] = "correction block did not parse as table"

    kill_credit_first = sorted({
        int(qid)
        for qid in re.findall(r"QuestieCorrections\.killCreditObjectiveFirst\[(\d+)\]\s*=\s*true", correction_text)
        if int(qid) in ids
    })
    meta = {
        "candidate_block_count": len(blocks),
        "parsed_block_count": len(parsed),
        "failed_block_count": len(failures),
        "unresolved_symbol_count": sum(len(values) for values in unresolved.values()),
        "unresolved_symbols": unresolved,
        "kill_credit_objective_first": kill_credit_first,
    }
    return parsed, failures, meta


def effective_quest_rows(
    data: QuestieData,
    source: str | Path,
    quest_ids: Iterable[int],
) -> tuple[dict[int, dict[Any, Any]], dict[str, Any]]:
    ids = {int(qid) for qid in quest_ids if isinstance(qid, int)}
    corrections, failures, meta = parse_wotlk_quest_corrections(source, ids)
    rows: dict[int, dict[Any, Any]] = {}
    changed_fields: dict[int, list[int]] = {}
    for quest_id in ids:
        raw = data.quests.get(quest_id)
        if not isinstance(raw, dict):
            continue
        row = deepcopy(raw)
        correction = corrections.get(quest_id)
        if correction:
            fields: list[int] = []
            for key, value in correction.items():
                if isinstance(key, int):
                    row[key] = deepcopy(value)
                    fields.append(key)
            if fields:
                changed_fields[quest_id] = sorted(fields)
        rows[quest_id] = row
    audit = {
        **meta,
        "parse_failures": {str(qid): reason for qid, reason in sorted(failures.items())},
        "changed_fields": {str(qid): fields for qid, fields in sorted(changed_fields.items())},
    }
    return rows, audit
