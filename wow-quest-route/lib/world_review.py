from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .questie_source import QuestieData
from .simple_route import (
    _annotate_distances,
    _annotate_quest_kinds,
    _auto_steps,
    _objective_profile,
    validate_simple_route,
)


def _review_level(quest: dict[str, Any]) -> int:
    values = [
        int(value)
        for value in (quest.get("required_level"), quest.get("quest_level"))
        if isinstance(value, int) and value > 0
    ]
    return max(values) if values else 1


def _route_json_path(candidate_root: Path, zone_entry: dict[str, Any]) -> Path:
    html_path = Path(str(zone_entry["file"]))
    return candidate_root / html_path.parent / "route.json"


def _selected_zone_records(
    candidate_root: Path,
    min_level: int,
    max_level: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest_path = candidate_root / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"候选任务清单不存在: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = []
    for zone_entry in manifest.get("zones", []):
        route_path = _route_json_path(candidate_root, zone_entry)
        candidate = json.loads(route_path.read_text(encoding="utf-8"))
        selected = [
            quest
            for quest in candidate.get("quest_catalog", [])
            if isinstance(quest, dict)
            and isinstance(quest.get("quest_id"), int)
            and min_level <= _review_level(quest) <= max_level
        ]
        if not selected:
            continue
        records.append(
            {
                "entry": zone_entry,
                "candidate": candidate,
                "quests": selected,
                "min_level": min(_review_level(quest) for quest in selected),
                "max_level": max(_review_level(quest) for quest in selected),
            }
        )
    records.sort(
        key=lambda record: (
            0 if int(record["entry"].get("zone_id", 0)) == 4298 else 1,
            int(record["min_level"]),
            str(record["entry"].get("continent", "")),
            str(record["entry"].get("name_zh", "")),
        )
    )
    return manifest, records


def build_world_review(
    data: QuestieData,
    candidate_root: Path,
    min_level: int = 55,
    max_level: int = 80,
) -> dict[str, Any]:
    if min_level < 1 or max_level > 80 or min_level > max_level:
        raise ValueError(f"无效等级范围: {min_level}—{max_level}")
    manifest, zone_records = _selected_zone_records(candidate_root, min_level, max_level)
    profile_label = str(manifest.get("profile_label") or "血精灵死亡骑士")
    segments: list[dict[str, Any]] = []
    seen_quests: set[int] = set()

    for index, record in enumerate(zone_records):
        entry = record["entry"]
        candidate = record["candidate"]
        quest_ids = {
            int(quest["quest_id"])
            for quest in record["quests"]
            if int(quest["quest_id"]) not in seen_quests
        }
        if not quest_ids:
            continue
        seen_quests.update(quest_ids)
        next_name = (
            str(zone_records[index + 1]["entry"].get("name_zh", "下一地图"))
            if index + 1 < len(zone_records)
            else ""
        )
        loot_class = {
            quest_id: "must"
            for quest_id in quest_ids
            if _objective_profile(data, quest_id)["kill_drop"]
        }
        segment_spec = {
            "id": f"zone-{int(entry['zone_id'])}",
            "name": str(entry["name_zh"]),
            "level_min": int(record["min_level"]),
            "level_max": int(record["max_level"]),
        }
        steps = _auto_steps(
            data,
            candidate,
            quest_ids,
            loot_class,
            segment_spec,
            next_name,
        )
        if steps:
            steps[-1] = {
                "text": (
                    f"完成本地图全部可执行任务后，前往{next_name}。"
                    if next_name
                    else f"完成全部{min_level}—{max_level}级地图任务；等待实跑反馈后再冻结最终循环顺序。"
                ),
                "tags": [],
                "quest_ids": [],
            }
        _annotate_quest_kinds(data, steps, segment_spec)
        _annotate_distances(steps)
        segments.append(
            {
                "id": segment_spec["id"],
                "name": segment_spec["name"],
                "continent": str(entry.get("continent", "其他")),
                "level_min": segment_spec["level_min"],
                "level_max": segment_spec["level_max"],
                "audit": "Questie完整任务目录自动梳理；尚未实跑验证道路、建筑层级和高风险点",
                "steps": steps,
                "public_steps": steps,
                "optional_tasks": [],
                "loot_tasks": [
                    {
                        "quest_id": quest_id,
                        "classification": "must",
                        "name": next(
                            str(quest.get("name", f"任务{quest_id}"))
                            for quest in record["quests"]
                            if int(quest["quest_id"]) == quest_id
                        ),
                        "reason": "全图清任务母版中保留",
                    }
                    for quest_id in sorted(loot_class)
                ],
                "selected_quest_ids": sorted(quest_ids),
                "selected_quest_count": len(quest_ids),
                "skipped": {},
            }
        )

    result = {
        "route_id": f"{manifest.get('profile', 'death-knight')}-world-review-{min_level}-{max_level}-v1",
        "title": f"{profile_label}五开 {min_level}—{max_level} 全世界任务母版",
        "character": profile_label,
        "mode": "五个死亡骑士重复清图；第一轮记录阻断、死亡、折返和逐号操作，后续冻结稳定流程",
        "eyebrow": "打金循环 · 全任务母版",
        "lede": (
            f"当前主目标是用死亡骑士五开完整覆盖{min_level}—{max_level}级可执行户外任务。"
            "本页优先保证任务覆盖完整，并按Questie接取、目标、交付位置整理；道路、洞穴、建筑楼层和服务器特有限制仍需第一轮实跑修正。"
        ),
        "source": {
            "questie_version": data.version,
            "questie_sha256": data.source_sha256,
            "candidate_profile": manifest.get("profile", "death-knight"),
        },
        "segments": segments,
        "stats": {
            "segment_count": len(segments),
            "step_count": sum(len(segment["steps"]) for segment in segments),
            "public_step_count": sum(len(segment["public_steps"]) for segment in segments),
            "selected_quest_count": sum(segment["selected_quest_count"] for segment in segments),
            "loot_must_count": sum(len(segment["loot_tasks"]) for segment in segments),
            "loot_optional_count": 0,
        },
    }
    validate_simple_route(result)
    return result


def render_world_review_markdown(route: dict[str, Any]) -> str:
    stats = route["stats"]
    lines = [
        f"# {route['title']}内部归档",
        "",
        "## 项目目标",
        "",
        "- 首组血精灵圣骑士只承担解锁55级死亡骑士创建条件；现有1—80路线继续保留为首组实跑参考，不再作为后续重复打金的主模型。",
        "- 后续循环以五个55级死亡骑士为起点，完整跑55—80级主要打金地图，并逐轮记录任务阻断、死亡点、回头路、洞穴风险和逐号操作。",
        "- 当前页面是全任务覆盖母版，不宣称第一版已经是最短路线；只有实跑稳定的地图段才能升级为固定循环。",
        "",
        "## 覆盖统计",
        "",
        f"- 地图：{stats['segment_count']}。",
        f"- 任务：{stats['selected_quest_count']}。",
        f"- 页面步骤：{stats['public_step_count']}。",
        f"- 需要打怪掉物的任务：{stats['loot_must_count']}。",
        "",
        "## 地图清单",
        "",
    ]
    for segment in route["segments"]:
        lines.append(
            f"- {segment['continent']} · {segment['name']} {segment['level_min']}—{segment['level_max']}："
            f"{segment['selected_quest_count']}个任务，{len(segment['public_steps'])}步；{segment['audit']}。"
        )
    return "\n".join(lines) + "\n"


def write_world_review_markdown(route: dict[str, Any], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_world_review_markdown(route), encoding="utf-8")
    return output
