from __future__ import annotations

import hashlib
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .questie_lua import LuaTableParser, parse_embedded_table_text


TABLE_PATHS = {
    "quests": "Database/Wotlk/wotlkQuestDB.lua",
    "npcs": "Database/Wotlk/wotlkNpcDB.lua",
    "objects": "Database/Wotlk/wotlkObjectDB.lua",
    "items": "Database/Wotlk/wotlkItemDB.lua",
    "quest_names": "Localization/lookups/Wotlk/lookupQuests/zhCN.lua",
    "npc_names": "Localization/lookups/Wotlk/lookupNpcs/zhCN.lua",
    "object_names": "Localization/lookups/Wotlk/lookupObjects/zhCN.lua",
    "item_names": "Localization/lookups/Wotlk/lookupItems/zhCN.lua",
}
QUEST_XP_PATH = "Database/QuestXP/DB/xpDB-wotlk.lua"


@dataclass(frozen=True)
class QuestieData:
    quests: dict[Any, Any]
    npcs: dict[Any, Any]
    objects: dict[Any, Any]
    items: dict[Any, Any]
    quest_names: dict[Any, Any]
    npc_names: dict[Any, Any]
    object_names: dict[Any, Any]
    item_names: dict[Any, Any]
    version: str
    source_sha256: str
    quest_xp: dict[Any, Any] = field(default_factory=dict)

    @staticmethod
    def local_name(table: dict[Any, Any], entity_id: int, fallback: str) -> str:
        value = table.get(entity_id)
        if isinstance(value, dict) and isinstance(value.get(1), str):
            return value[1]
        return fallback


def _version_from_toc(text: str) -> str:
    match = re.search(r"^## Version:\s*(.+?)\s*$", text, flags=re.MULTILINE)
    return match.group(1) if match else "unknown"


def _zip_reader(path: Path) -> tuple[Callable[[str], str], str, str]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    archive = zipfile.ZipFile(path)
    names = set(archive.namelist())
    prefix = "Questie/" if any(name.startswith("Questie/Database/") for name in names) else ""

    def read(relative: str) -> str:
        member = prefix + relative
        try:
            return archive.read(member).decode("utf-8")
        except KeyError as exc:
            raise FileNotFoundError(f"Questie ZIP缺少文件: {member}") from exc

    toc_member = prefix + "Questie-WOTLKC.toc"
    version = _version_from_toc(archive.read(toc_member).decode("utf-8")) if toc_member in names else "unknown"
    return read, version, digest


def _directory_reader(path: Path) -> tuple[Callable[[str], str], str, str]:
    root = path / "Questie" if (path / "Questie" / "Database").is_dir() else path
    if not (root / "Database").is_dir():
        raise FileNotFoundError(f"未找到Questie Database目录: {root}")

    def read(relative: str) -> str:
        return (root / relative).read_text(encoding="utf-8")

    toc_file = root / "Questie-WOTLKC.toc"
    version = _version_from_toc(toc_file.read_text(encoding="utf-8")) if toc_file.exists() else "unknown"
    marker = f"directory:{root.resolve()}:{version}"
    digest = hashlib.sha256(marker.encode("utf-8")).hexdigest()
    return read, version, digest


def _parse_quest_xp(text: str, source: str) -> dict[Any, Any]:
    marker = text.find("QuestXP.db")
    start = text.find("{", marker)
    if marker == -1 or start == -1:
        raise ValueError(f"Questie经验数据库格式异常: {source}")
    parsed = LuaTableParser(text[start:]).parse()
    if not isinstance(parsed, dict):
        raise ValueError(f"Questie经验数据库不是Lua table: {source}")
    return parsed


def load_questie(source: str | Path) -> QuestieData:
    path = Path(source).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Questie来源不存在: {path}")
    if path.is_file() and path.suffix.lower() == ".zip":
        read, version, digest = _zip_reader(path)
    elif path.is_dir():
        read, version, digest = _directory_reader(path)
    else:
        raise ValueError("Questie来源必须是ZIP或Questie目录")

    parsed: dict[str, dict[Any, Any]] = {}
    for key, relative in TABLE_PATHS.items():
        parsed[key] = parse_embedded_table_text(read(relative), relative)
    quest_xp = _parse_quest_xp(read(QUEST_XP_PATH), QUEST_XP_PATH)

    return QuestieData(
        quests=parsed["quests"],
        npcs=parsed["npcs"],
        objects=parsed["objects"],
        items=parsed["items"],
        quest_names=parsed["quest_names"],
        npc_names=parsed["npc_names"],
        object_names=parsed["object_names"],
        item_names=parsed["item_names"],
        version=version,
        source_sha256=digest,
        quest_xp=quest_xp,
    )
