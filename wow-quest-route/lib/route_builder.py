from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from typing import Any

from .questie_lua import seq
from .questie_source import QuestieData


QUEST_KEYS = {
    "name": 1,
    "started_by": 2,
    "finished_by": 3,
    "required_level": 4,
    "quest_level": 5,
    "required_races": 6,
    "required_classes": 7,
    "objectives_text": 8,
    "objectives": 10,
    "pre_group": 12,
    "pre_single": 13,
    "child_quests": 14,
    "zone_or_sort": 17,
    "next_quest": 22,
}

NPC_KEYS = {"name": 1, "spawns": 7, "zone_id": 9}
OBJECT_KEYS = {"name": 1, "spawns": 4, "zone_id": 5}


def _array(table: Any) -> list[Any]:
    return seq(table)


def _coords(spawns: Any, map_area_id: int) -> list[tuple[float, float]]:
    if not isinstance(spawns, dict):
        return []
    selected = spawns.get(map_area_id)
    if selected is None:
        values = [value for value in spawns.values() if isinstance(value, dict)]
        selected = values[0] if len(values) == 1 else None
    points: list[tuple[float, float]] = []
    for point in _array(selected):
        values = _array(point)
        if len(values) >= 2 and all(isinstance(value, (int, float)) for value in values[:2]):
            points.append((float(values[0]), float(values[1])))
    return points


def _summary(points: list[tuple[float, float]]) -> dict[str, Any] | None:
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return {
        "representative": {"x": round(mean(xs), 2), "y": round(mean(ys), 2)},
        "bounds": {
            "min_x": round(min(xs), 2),
            "max_x": round(max(xs), 2),
            "min_y": round(min(ys), 2),
            "max_y": round(max(ys), 2),
        },
        "spawn_count": len(points),
    }


def _entity(data: QuestieData, entity_id: int, map_area_id: int) -> dict[str, Any]:
    if entity_id in data.npcs:
        row = data.npcs[entity_id]
        raw_name = row.get(NPC_KEYS["name"], f"NPC {entity_id}")
        name = data.local_name(data.npc_names, entity_id, raw_name)
        points = _coords(row.get(NPC_KEYS["spawns"]), map_area_id)
        kind = "npc"
    elif entity_id in data.objects:
        row = data.objects[entity_id]
        raw_name = row.get(OBJECT_KEYS["name"], f"Object {entity_id}")
        name = data.local_name(data.object_names, entity_id, raw_name)
        points = _coords(row.get(OBJECT_KEYS["spawns"]), map_area_id)
        kind = "object"
    else:
        raise KeyError(f"路线锚点ID不存在于NPC/Object DB: {entity_id}")
    return {
        "id": entity_id,
        "kind": kind,
        "name": name,
        "coordinate_summary": _summary(points),
        "coordinates": [{"x": x, "y": y} for x, y in points],
    }


def _quest(data: QuestieData, quest_id: int) -> dict[str, Any]:
    row = data.quests.get(quest_id)
    if not isinstance(row, dict):
        raise KeyError(f"Questie中不存在任务: {quest_id}")
    raw_name = row.get(QUEST_KEYS["name"], f"Quest {quest_id}")
    localized = data.quest_names.get(quest_id)
    name = localized.get(1) if isinstance(localized, dict) and isinstance(localized.get(1), str) else raw_name
    localized_objective = ""
    if isinstance(localized, dict):
        objective_values = _array(localized.get(2))
        if objective_values:
            localized_objective = " / ".join(str(value) for value in objective_values)
    return {
        "quest_id": quest_id,
        "name": name,
        "raw_name": raw_name,
        "required_level": row.get(QUEST_KEYS["required_level"]),
        "quest_level": row.get(QUEST_KEYS["quest_level"]),
        "required_races": row.get(QUEST_KEYS["required_races"]),
        "required_classes": row.get(QUEST_KEYS["required_classes"]),
        "zone_or_sort": row.get(QUEST_KEYS["zone_or_sort"]),
        "pre_single": _array(row.get(QUEST_KEYS["pre_single"])),
        "pre_group": _array(row.get(QUEST_KEYS["pre_group"])),
        "child_quests": _array(row.get(QUEST_KEYS["child_quests"])),
        "next_quest": row.get(QUEST_KEYS["next_quest"]),
        "objective_text": localized_objective,
    }


def _anchor_details(data: QuestieData, anchor: dict[str, Any], map_area_id: int) -> dict[str, Any]:
    ids: list[int]
    if "id" in anchor:
        ids = [int(anchor["id"])]
    else:
        ids = [int(value) for value in anchor.get("ids", [])]
    entities = [_entity(data, entity_id, map_area_id) for entity_id in ids]
    representatives = [
        entity["coordinate_summary"]["representative"]
        for entity in entities
        if entity["coordinate_summary"]
    ]
    representative = None
    if representatives:
        representative = {
            "x": round(mean(point["x"] for point in representatives), 2),
            "y": round(mean(point["y"] for point in representatives), 2),
        }
    return {
        "type": anchor["type"],
        "representative": representative,
        "entities": entities,
    }


def build_route(
    data: QuestieData,
    spec_path: Path,
    observations_path: Path,
) -> dict[str, Any]:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    observations = json.loads(observations_path.read_text(encoding="utf-8"))
    map_area_id = int(spec["map_area_id"])
    enriched_steps: list[dict[str, Any]] = []
    all_quest_ids: set[int] = set()

    for step in spec["steps"]:
        quest_ids = [int(value) for value in step["quest_ids"]]
        all_quest_ids.update(quest_ids)
        enriched_steps.append(
            {
                **step,
                "quests": [_quest(data, quest_id) for quest_id in quest_ids],
                "anchor_details": _anchor_details(data, step["anchor"], map_area_id),
            }
        )

    task_observations = observations.get("tasks", {})
    return {
        "route_id": spec["route_id"],
        "title": spec["title"],
        "zone": spec["zone"],
        "map_area_id": map_area_id,
        "quest_zone_or_sort": spec["quest_zone_or_sort"],
        "assumptions": spec["assumptions"],
        "source": {
            "questie_version": data.version,
            "source_sha256": data.source_sha256,
        },
        "steps": enriched_steps,
        "quest_catalog": [_quest(data, quest_id) for quest_id in sorted(all_quest_ids)],
        "fivebox_observations": {
            str(quest_id): task_observations.get(str(quest_id), {"status": "not_classified"})
            for quest_id in sorted(all_quest_ids)
        },
        "verification_required": [
            "五号交付8325后是否全部达到2级；若否，需要补杀多少只法力浮龙",
            "击杀任务的五号共享进度",
            "山猫项圈、奥术薄片和首级是否可由五号从同一尸体分别拾取",
            "三个索兰尼亚物品和达斯雷玛神殿是否必须逐号交互",
            "被污染的奥术碎片是否五号都能在一次学院路线中获得",
            "西南目标环与法瑟林学院之间的实际可走道路和跟随卡点",
        ],
    }


def _coord_text(anchor: dict[str, Any]) -> str:
    representative = anchor.get("representative")
    if not representative:
        return "无坐标"
    return f"{representative['x']:.2f}, {representative['y']:.2f}"


def render_markdown(route: dict[str, Any]) -> str:
    lines = [
        f"# {route['title']}",
        "",
        "> 这是基于Questie静态数据生成的候选路线，不是游戏内自动导航。道路、刷新效率和五开共享行为仍需实测。",
        "",
        f"- Questie版本：`{route['source']['questie_version']}`",
        f"- 来源SHA256：`{route['source']['source_sha256']}`",
        f"- 地图区域ID：`{route['map_area_id']}`；任务区域字段：`{route['quest_zone_or_sort']}`",
        "",
        "## 使用前提",
        "",
    ]
    lines.extend(f"- {item}" for item in route["assumptions"])
    lines.extend(
        [
            "",
            "## 路线步骤",
            "",
            "| 步骤 | 动作 | 代表坐标 | 任务 | 五开类型 | 置信度 |",
            "| ---: | --- | --- | --- | --- | --- |",
        ]
    )
    for step in route["steps"]:
        quests = "、".join(f"{quest['quest_id']} {quest['name']}" for quest in step["quests"])
        lines.append(
            f"| {step['step']} | {step['action']} | {_coord_text(step['anchor_details'])} | "
            f"{quests} | `{step['fivebox']}` | {step['confidence']} |"
        )
        lines.append("")
        lines.append(f"**操作：** {step['instruction']}")
        entity_parts: list[str] = []
        for entity in step["anchor_details"]["entities"]:
            summary = entity["coordinate_summary"]
            if summary:
                point = summary["representative"]
                entity_parts.append(
                    f"{entity['name']}（{entity['id']}，{point['x']:.2f},{point['y']:.2f}，"
                    f"{summary['spawn_count']}个点）"
                )
            else:
                entity_parts.append(f"{entity['name']}（{entity['id']}，无坐标）")
        lines.append(f"**锚点：** {'；'.join(entity_parts)}")
        lines.append("")

    lines.extend(["## 必须逐号检查的任务", ""])
    for quest_id, observation in route["fivebox_observations"].items():
        if observation.get("status") == "not_classified":
            continue
        quest = next(item for item in route["quest_catalog"] if str(item["quest_id"]) == quest_id)
        lines.append(
            f"- **{quest_id} {quest['name']}**：`{observation.get('type')}` — {observation.get('note', '')}"
        )

    lines.extend(["", "## V1实测清单", ""])
    lines.extend(f"- [ ] {item}" for item in route["verification_required"])
    lines.extend(
        [
            "",
            "## 反馈格式",
            "",
            "只记录异常即可：`步骤号｜任务名｜发生了什么｜五号中几号完成｜是否走回头路/卡跟随`。",
            "",
        ]
    )
    return "\n".join(lines)


def write_route(route: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "sunstrider-isle-v1.json"
    markdown_path = output_dir / "sunstrider-isle-v1.md"
    json_path.write_text(json.dumps(route, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(route), encoding="utf-8")
    return markdown_path, json_path
