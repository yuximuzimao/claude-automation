from __future__ import annotations

import json
import math
import re
import zipfile
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any, Callable

from .navigator_renderer import write_navigator_html
from .questie_lua import LuaTableParser, seq
from .questie_source import QuestieData
from .route_builder import _quest


QUEST = {
    "started_by": 2,
    "finished_by": 3,
    "required_level": 4,
    "quest_level": 5,
    "required_races": 6,
    "required_classes": 7,
    "trigger_end": 9,
    "objectives": 10,
    "pre_group": 12,
    "pre_single": 13,
    "zone_or_sort": 17,
    "required_skill": 18,
    "quest_flags": 23,
    "special_flags": 24,
}
NPC = {"name": 1, "spawns": 7}
OBJECT = {"name": 1, "spawns": 4}
ITEM = {"name": 1, "npc_drops": 2, "object_drops": 3}

BLOOD_ELF_RACE_FLAG = 2 ** (10 - 1)
PALADIN_CLASS_FLAG = 2 ** (2 - 1)
QUEST_FLAG_RAID = 64
QUEST_FLAG_DAILY = 4096
QUEST_FLAG_WEEKLY = 32768
SPECIAL_REPEATABLE = 1
SPECIAL_EVENT = 2
ALLOWED_ZONE_FILES = {
    "EasternKingdoms.lua": "东部王国",
    "Kalimdor.lua": "卡利姆多",
    "Outland.lua": "外域",
    "Northrend.lua": "诺森德",
}
ZONE_CONTINENT_OVERRIDES = {
    3430: "东部王国",  # 永歌森林/逐日岛
    3433: "东部王国",  # 幽魂之地
    3487: "东部王国",  # 银月城
    4080: "东部王国",  # 奎尔丹纳斯岛
    3524: "卡利姆多",  # 秘蓝岛
    3525: "卡利姆多",  # 秘血岛
    3557: "卡利姆多",  # 埃索达
}


def _source_reader(source: str | Path) -> Callable[[str], str]:
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


def _parse_assignment_table(text: str, marker: str) -> dict[Any, Any]:
    start = text.find(marker)
    if start == -1:
        return {}
    brace = text.find("{", start)
    if brace == -1:
        return {}
    parsed = LuaTableParser(text[brace:]).parse()
    return parsed if isinstance(parsed, dict) else {}


def _flatten_zone_names(table: Any, out: dict[int, str]) -> None:
    if not isinstance(table, dict):
        return
    for key, value in table.items():
        if isinstance(key, int) and isinstance(value, str):
            out.setdefault(key, value)
        elif isinstance(value, dict):
            _flatten_zone_names(value, out)


def _parse_zone_translations(read: Callable[[str], str]) -> tuple[dict[str, str], dict[str, str]]:
    zh: dict[str, str] = {}
    continents: dict[str, str] = {}
    entry_re = re.compile(r'\["((?:[^"\\]|\\.)+)"\]\s*=\s*\{(.*?)\n\s*\},', re.S)
    zh_re = re.compile(r'\["zhCN"\]\s*=\s*"((?:[^"\\]|\\.)*)"')
    for filename, continent in ALLOWED_ZONE_FILES.items():
        text = read(f"Localization/Translations/Zones/{filename}")
        for match in entry_re.finditer(text):
            english = bytes(match.group(1), "utf-8").decode("unicode_escape") if "\\" in match.group(1) else match.group(1)
            continents[english] = continent
            zh_match = zh_re.search(match.group(2))
            if zh_match:
                zh[english] = zh_match.group(1)
    return zh, continents


def _parse_zone_metadata(source: str | Path) -> dict[str, Any]:
    read = _source_reader(source)
    lookup = _parse_assignment_table(read("Localization/lookups/lookupZones.lua"), "l10n.zoneLookup")
    names: dict[int, str] = {}
    _flatten_zone_names(lookup, names)

    parent_text = read("Database/Zones/data/subZoneToParentZone.lua")
    parent_map = {int(a): int(b) for a, b in re.findall(r"\[(\d+)\]\s*=\s*(\d+)", parent_text)}

    dungeon_text = read("Database/Zones/data/dungeons.lua")
    dungeon_ids = {int(value) for value in re.findall(r"^\s*\[(\d+)\]\s*=", dungeon_text, re.M)}

    zh, continents = _parse_zone_translations(read)
    return {
        "names": names,
        "parents": parent_map,
        "dungeons": dungeon_ids,
        "zh": zh,
        "continents": continents,
    }


def _parent_zone(zone_id: int, parent_map: dict[int, int]) -> int:
    seen: set[int] = set()
    while zone_id in parent_map and zone_id not in seen:
        seen.add(zone_id)
        zone_id = parent_map[zone_id]
    return zone_id


def _bit_allowed(mask: Any, flag: int) -> bool:
    if not isinstance(mask, int) or mask == 0:
        return True
    return mask % (flag * 2) >= flag


def _eligible(data: QuestieData, row: Any) -> bool:
    if not isinstance(row, dict):
        return False
    zone = row.get(QUEST["zone_or_sort"])
    if not isinstance(zone, int) or zone <= 0:
        return False
    level = row.get(QUEST["required_level"])
    if isinstance(level, int) and level > 80:
        return False
    if not _bit_allowed(row.get(QUEST["required_races"]), BLOOD_ELF_RACE_FLAG):
        return False
    if not _bit_allowed(row.get(QUEST["required_classes"]), PALADIN_CLASS_FLAG):
        return False
    if row.get(QUEST["required_skill"]):
        return False
    qflags = row.get(QUEST["quest_flags"])
    if isinstance(qflags, int) and qflags & (QUEST_FLAG_RAID | QUEST_FLAG_DAILY | QUEST_FLAG_WEEKLY):
        return False
    sflags = row.get(QUEST["special_flags"])
    if isinstance(sflags, int) and sflags & (SPECIAL_REPEATABLE | SPECIAL_EVENT):
        return False
    starters = row.get(QUEST["started_by"])
    npc_starters = _ids(starters, 1)
    if npc_starters:
        friendly = []
        for npc_id in npc_starters:
            npc = data.npcs.get(npc_id)
            if isinstance(npc, dict):
                friendly.append(npc.get(13))
        if friendly and not any(isinstance(value, str) and "H" in value for value in friendly):
            return False
    return True


def _coords_for_zone(spawns: Any, zone_id: int) -> list[dict[str, float]]:
    if not isinstance(spawns, dict):
        return []
    raw = spawns.get(zone_id)
    if raw is None:
        return []
    points: list[dict[str, float]] = []
    for point in seq(raw):
        values = seq(point)
        if len(values) >= 2 and all(isinstance(v, (int, float)) for v in values[:2]):
            points.append({"x": float(values[0]), "y": float(values[1])})
    return points


def _entity(data: QuestieData, kind: str, entity_id: int, zone_id: int, label_prefix: str = "") -> dict[str, Any] | None:
    if kind == "npc":
        row = data.npcs.get(entity_id)
        if not isinstance(row, dict):
            return None
        raw = row.get(NPC["name"], f"NPC {entity_id}")
        name = data.local_name(data.npc_names, entity_id, raw)
        coords = _coords_for_zone(row.get(NPC["spawns"]), zone_id)
    else:
        row = data.objects.get(entity_id)
        if not isinstance(row, dict):
            return None
        raw = row.get(OBJECT["name"], f"Object {entity_id}")
        name = data.local_name(data.object_names, entity_id, raw)
        coords = _coords_for_zone(row.get(OBJECT["spawns"]), zone_id)
    if not coords:
        return None
    return {
        "id": entity_id,
        "kind": kind,
        "name": f"{label_prefix}{name}",
        "coordinates": coords,
        "coordinate_summary": _coord_summary(coords),
    }


def _coord_summary(points: list[dict[str, float]]) -> dict[str, Any] | None:
    if not points:
        return None
    xs = [p["x"] for p in points]
    ys = [p["y"] for p in points]
    return {
        "representative": {"x": round(float(median(xs)), 2), "y": round(float(median(ys)), 2)},
        "bounds": {
            "min_x": round(min(xs), 2),
            "max_x": round(max(xs), 2),
            "min_y": round(min(ys), 2),
            "max_y": round(max(ys), 2),
        },
        "spawn_count": len(points),
    }


def _ids(group: Any, index: int) -> list[int]:
    if not isinstance(group, dict):
        return []
    return [int(v) for v in seq(group.get(index)) if isinstance(v, int)]


def _questgiver_entities(data: QuestieData, group: Any, zone_id: int, prefix: str = "") -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    for npc_id in _ids(group, 1):
        entity = _entity(data, "npc", npc_id, zone_id, prefix)
        if entity:
            entities.append(entity)
    for object_id in _ids(group, 2):
        entity = _entity(data, "object", object_id, zone_id, prefix)
        if entity:
            entities.append(entity)
    return entities


def _objective_entities(data: QuestieData, row: dict[Any, Any], zone_id: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    objectives = row.get(QUEST["objectives"])
    if isinstance(objectives, dict):
        for entry in seq(objectives.get(1)):
            values = seq(entry)
            if values and isinstance(values[0], int):
                entity = _entity(data, "npc", values[0], zone_id)
                if entity:
                    result.append(entity)
        for entry in seq(objectives.get(2)):
            values = seq(entry)
            if values and isinstance(values[0], int):
                entity = _entity(data, "object", values[0], zone_id)
                if entity:
                    result.append(entity)
        for entry in seq(objectives.get(3)):
            values = seq(entry)
            if not values or not isinstance(values[0], int):
                continue
            item_id = values[0]
            item_row = data.items.get(item_id)
            if not isinstance(item_row, dict):
                continue
            raw = item_row.get(ITEM["name"], f"Item {item_id}")
            item_name = data.local_name(data.item_names, item_id, raw)
            source_count = 0
            for npc_id in seq(item_row.get(ITEM["npc_drops"])):
                if source_count >= 8:
                    break
                if isinstance(npc_id, int):
                    entity = _entity(data, "npc", npc_id, zone_id, f"{item_name}来源：")
                    if entity:
                        result.append(entity)
                        source_count += 1
            for object_id in seq(item_row.get(ITEM["object_drops"])):
                if source_count >= 8:
                    break
                if isinstance(object_id, int):
                    entity = _entity(data, "object", object_id, zone_id, f"{item_name}来源：")
                    if entity:
                        result.append(entity)
                        source_count += 1
        for entry in seq(objectives.get(5)):
            values = seq(entry)
            if not values:
                continue
            ids = seq(values[0]) if isinstance(values[0], dict) else []
            for npc_id in ids:
                if isinstance(npc_id, int):
                    entity = _entity(data, "npc", npc_id, zone_id)
                    if entity:
                        result.append(entity)

    trigger = row.get(QUEST["trigger_end"])
    if isinstance(trigger, dict):
        values = seq(trigger)
        if len(values) >= 2 and isinstance(values[1], dict):
            points = _coords_for_zone(values[1], zone_id)
            if points:
                result.append({
                    "id": f"trigger-{id(row)}",
                    "kind": "event",
                    "name": str(values[0] or "触发目标"),
                    "coordinates": points,
                    "coordinate_summary": _coord_summary(points),
                })
    return _dedupe_entities(result)


def _dedupe_entities(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, Any, str]] = set()
    out: list[dict[str, Any]] = []
    for entity in entities:
        key = (entity["kind"], entity["id"], entity["name"])
        if key not in seen:
            seen.add(key)
            out.append(entity)
    return out


def _node_rep(entities: list[dict[str, Any]]) -> dict[str, float] | None:
    points = [e["coordinate_summary"]["representative"] for e in entities if e.get("coordinate_summary")]
    if not points:
        return None
    return {"x": float(median([p["x"] for p in points])), "y": float(median([p["y"] for p in points]))}


def _dependency_depths(quests: dict[int, dict[Any, Any]]) -> dict[int, int]:
    memo: dict[int, int] = {}

    def depth(qid: int, stack: set[int]) -> int:
        if qid in memo:
            return memo[qid]
        if qid in stack:
            return 0
        stack = set(stack)
        stack.add(qid)
        row = quests[qid]
        parents = [int(x) for x in seq(row.get(QUEST["pre_single"])) + seq(row.get(QUEST["pre_group"])) if isinstance(x, int) and x in quests]
        value = 0 if not parents else max(depth(parent, stack) + 1 for parent in parents)
        memo[qid] = value
        return value

    for quest_id in quests:
        depth(quest_id, set())
    return memo


def _distance(a: dict[str, float] | None, b: dict[str, float] | None) -> float:
    if not a or not b:
        return 999.0
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


def _cluster_nodes(nodes: list[dict[str, Any]], radius: float = 4.5) -> list[dict[str, Any]]:
    clusters: list[dict[str, Any]] = []
    for node in nodes:
        rep = node.get("representative")
        match = None
        for cluster in clusters:
            if _distance(rep, cluster.get("representative")) <= radius:
                match = cluster
                break
        if not match:
            match = {
                "phase": node["phase"],
                "quest_ids": [],
                "entities": [],
                "labels": [],
                "representative": rep,
            }
            clusters.append(match)
        match["quest_ids"].extend(node["quest_ids"])
        match["entities"].extend(node["entities"])
        match["labels"].extend(node["labels"])
        match["quest_ids"] = sorted(set(match["quest_ids"]))
        match["entities"] = _dedupe_entities(match["entities"])
        match["representative"] = _node_rep(match["entities"])
    return clusters


def _nearest_order(nodes: list[dict[str, Any]], start: dict[str, float] | None) -> tuple[list[dict[str, Any]], dict[str, float] | None]:
    remaining = list(nodes)
    ordered: list[dict[str, Any]] = []
    current = start
    while remaining:
        if current is None:
            idx = min(range(len(remaining)), key=lambda i: ((remaining[i].get("representative") or {"y": 999})["y"], (remaining[i].get("representative") or {"x": 999})["x"]))
        else:
            idx = min(range(len(remaining)), key=lambda i: _distance(current, remaining[i].get("representative")))
        node = remaining.pop(idx)
        ordered.append(node)
        current = node.get("representative") or current
    return ordered, current


def _phase_nodes(data: QuestieData, quests: dict[int, dict[Any, Any]], zone_id: int, qids: list[int], phase: str) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for qid in qids:
        row = quests[qid]
        if phase == "accept":
            entities = _questgiver_entities(data, row.get(QUEST["started_by"]), zone_id)
            label = "接取"
        elif phase == "objective":
            entities = _objective_entities(data, row, zone_id)
            label = "完成目标"
        else:
            entities = _questgiver_entities(data, row.get(QUEST["finished_by"]), zone_id)
            label = "交付"
        if not entities:
            continue
        nodes.append({
            "phase": phase,
            "quest_ids": [qid],
            "entities": entities,
            "labels": [label],
            "representative": _node_rep(entities),
        })
    return nodes


def _instruction(phase: str, quest_names: list[str], entities: list[dict[str, Any]]) -> str:
    targets = "、".join(entity["name"] for entity in entities[:4])
    if len(entities) > 4:
        targets += f"等{len(entities)}个目标"
    names = "、".join(quest_names)
    if phase == "accept":
        return f"到{targets}处接取：{names}。其他跟随号只需在NPC附近逐个切换接取。"
    if phase == "turnin":
        return f"到{targets}处交付：{names}。其他跟随号在附近逐个切换交付。"
    return f"在{targets}周边完成：{names}。路线只按主控号移动；需要个人拾取或点击时再切换跟随号。"


def _segments(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    current: list[int] = []
    first_rep: dict[str, float] | None = None
    first_name = ""
    for step in steps:
        rep = step["anchor_details"].get("representative")
        if current and (len(current) >= 9 or _distance(first_rep, rep) > 28):
            letter = chr(ord("A") + len(segments)) if len(segments) < 26 else str(len(segments) + 1)
            segments.append({"id": letter, "title": f"{first_name}周边", "steps": current, "goal": "只执行本小区域内的接取、目标和交付"})
            current = []
            first_rep = None
        if not current:
            first_rep = rep
            entities = step["anchor_details"]["entities"]
            first_name = entities[0]["name"] if entities else f"步骤{step['step']}"
        current.append(step["step"])
    if current:
        letter = chr(ord("A") + len(segments)) if len(segments) < 26 else str(len(segments) + 1)
        segments.append({"id": letter, "title": f"{first_name}周边", "steps": current, "goal": "只执行本小区域内的接取、目标和交付"})
    return segments


def build_zone_route(data: QuestieData, zone_id: int, zone_name: str, zone_name_zh: str, quests: dict[int, dict[Any, Any]]) -> dict[str, Any] | None:
    actionable: dict[int, dict[Any, Any]] = {}
    for qid, row in quests.items():
        if (
            _questgiver_entities(data, row.get(QUEST["started_by"]), zone_id)
            or _objective_entities(data, row, zone_id)
            or _questgiver_entities(data, row.get(QUEST["finished_by"]), zone_id)
        ):
            actionable[qid] = row
    quests = actionable
    if not quests:
        return None
    depths = _dependency_depths(quests)
    waves: dict[tuple[int, int], list[int]] = defaultdict(list)
    for qid, row in quests.items():
        level = row.get(QUEST["required_level"])
        if not isinstance(level, int) or level <= 0:
            level = row.get(QUEST["quest_level"])
        level = int(level) if isinstance(level, int) and level > 0 else 1
        waves[(max(0, (level - 1) // 5), depths.get(qid, 0))].append(qid)

    ordered_nodes: list[dict[str, Any]] = []
    current: dict[str, float] | None = None
    for wave in sorted(waves):
        qids = sorted(waves[wave], key=lambda qid: (quests[qid].get(QUEST["required_level"]) or 0, qid))
        for phase in ("accept", "objective", "turnin"):
            clusters = _cluster_nodes(_phase_nodes(data, quests, zone_id, qids, phase))
            ordered, current = _nearest_order(clusters, current)
            ordered_nodes.extend(ordered)

    if not ordered_nodes:
        return None

    catalog = [_quest(data, qid) for qid in sorted(quests)]
    steps: list[dict[str, Any]] = []
    for index, node in enumerate(ordered_nodes, 1):
        quest_names = [next(q["name"] for q in catalog if q["quest_id"] == qid) for qid in node["quest_ids"]]
        action = {"accept": "接取", "objective": "完成目标", "turnin": "交付"}[node["phase"]]
        steps.append({
            "step": index,
            "action": action,
            "quest_ids": node["quest_ids"],
            "quests": [q for q in catalog if q["quest_id"] in node["quest_ids"]],
            "instruction": _instruction(node["phase"], quest_names, node["entities"]),
            "confidence": "database_candidate",
            "fivebox": "main_route_followers_note_only",
            "anchor_details": {
                "type": node["phase"],
                "representative": node["representative"],
                "entities": node["entities"],
            },
        })

    levels = []
    for row in quests.values():
        level = row.get(QUEST["required_level"])
        if not isinstance(level, int) or level <= 0:
            level = row.get(QUEST["quest_level"])
        if isinstance(level, int) and level > 0:
            levels.append(level)
    if not levels:
        levels = [1]
    basename = f"zone-{zone_id}"
    route = {
        "route_id": f"horde-blood-elf-paladin-{basename}-candidate",
        "title": f"{zone_name_zh}（{zone_name}）坐标导航候选版",
        "output_basename": basename,
        "zone": zone_name_zh,
        "zone_en": zone_name,
        "map_area_id": zone_id,
        "quest_zone_or_sort": zone_id,
        "assumptions": [
            "只按一个主控角色计算路线，另外四个角色视为持续跟随",
            "仅使用Questie静态数据库离线生成，不安装自制游戏内插件",
            "当前是全量自动候选版，未经过该区域实跑审计",
        ],
        "segments": _segments(steps),
        "source": {"questie_version": data.version, "source_sha256": data.source_sha256},
        "steps": steps,
        "quest_catalog": catalog,
        "fivebox_observations": {str(qid): {"status": "not_classified"} for qid in quests},
        "verification_required": ["任务顺序、道路和建筑楼层需要实际游戏验证"],
        "stats": {
            "quest_count": len(quests),
            "step_count": len(steps),
            "min_level": min(levels),
            "max_level": max(levels),
        },
    }
    return route


def _slug_safe(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-").lower() or "zone"


def _write_index(entries: list[dict[str, Any]], output: Path) -> Path:
    rows = []
    for e in entries:
        rows.append(
            f'<tr><td>{e["continent"]}</td><td><a href="{e["file"]}">{e["name_zh"]}</a><div class="en">{e["name_en"]}</div></td>'
            f'<td>{e["min_level"]}–{e["max_level"]}</td><td>{e["quest_count"]}</td><td>{e["segment_count"]}</td></tr>'
        )
    text = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>血精灵圣骑士1–80区域路线索引</title><style>
body{{margin:0;background:#0c1118;color:#e7edf5;font:16px/1.5 system-ui,"Microsoft YaHei";padding:24px}}h1{{margin-top:0}}.note{{background:#20170e;border:1px solid #8a5c18;padding:12px;border-radius:9px;margin-bottom:18px}}table{{width:100%;border-collapse:collapse;background:#121923}}th,td{{padding:10px;border-bottom:1px solid #2d3a49;text-align:left}}th{{position:sticky;top:0;background:#18212c}}a{{color:#22d3ee;font-weight:800}}.en{{font-size:12px;color:#94a3b8}}</style></head><body><h1>血精灵圣骑士1–80区域路线索引</h1><div class="note">这是Questie静态数据库自动生成的全量候选版。每个区域已拆成小区块，并提供坐标方向计算；它覆盖范围广，但不代表每个区域已经人工证明最优。</div><table><thead><tr><th>大陆</th><th>区域</th><th>最低等级</th><th>任务数</th><th>小区块</th></tr></thead><tbody>{''.join(rows)}</tbody></table></body></html>'''
    path = output / "index.html"
    path.write_text(text, encoding="utf-8")
    return path


def build_world_routes(data: QuestieData, source: str | Path, output: Path) -> dict[str, Any]:
    meta = _parse_zone_metadata(source)
    grouped: dict[int, dict[int, dict[Any, Any]]] = defaultdict(dict)
    for qid, row in data.quests.items():
        if not isinstance(qid, int) or not _eligible(data, row):
            continue
        raw_zone = int(row[QUEST["zone_or_sort"]])
        zone_id = _parent_zone(raw_zone, meta["parents"])
        if zone_id in meta["dungeons"]:
            continue
        zone_name = meta["names"].get(zone_id)
        if not zone_name or (zone_name not in meta["continents"] and zone_id not in ZONE_CONTINENT_OVERRIDES):
            continue
        grouped[zone_id][qid] = row

    output.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    for zone_id, quests in sorted(grouped.items(), key=lambda item: min(int(r.get(QUEST["required_level"]) or 1) for r in item[1].values())):
        zone_name = meta["names"].get(zone_id, f"Zone {zone_id}")
        zone_name_zh = meta["zh"].get(zone_name, zone_name)
        route = build_zone_route(data, zone_id, zone_name, zone_name_zh, quests)
        if not route:
            continue
        zone_dir = output / f"{zone_id}-{_slug_safe(zone_name)}"
        zone_dir.mkdir(parents=True, exist_ok=True)
        json_path = zone_dir / "route.json"
        json_path.write_text(json.dumps(route, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        html_path = write_navigator_html(route, zone_dir)
        entries.append({
            "zone_id": zone_id,
            "name_en": zone_name,
            "name_zh": zone_name_zh,
            "continent": ZONE_CONTINENT_OVERRIDES.get(zone_id, meta["continents"].get(zone_name, "其他")),
            "file": f"{zone_dir.name}/{html_path.name}",
            "quest_count": route["stats"]["quest_count"],
            "segment_count": len(route["segments"]),
            "min_level": route["stats"]["min_level"],
            "max_level": route["stats"]["max_level"],
        })

    entries.sort(key=lambda e: (e["min_level"], e["continent"], e["name_zh"]))
    index = _write_index(entries, output)
    manifest = {
        "questie_version": data.version,
        "zone_count": len(entries),
        "quest_count": sum(e["quest_count"] for e in entries),
        "zones": entries,
        "index": index.name,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
