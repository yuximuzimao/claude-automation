from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .questie_lua import LuaTableParser, seq
from .questie_source import QuestieData


QUEST = {
    "name": 1,
    "started_by": 2,
    "finished_by": 3,
    "required_level": 4,
    "quest_level": 5,
    "objectives": 10,
    "pre_group": 12,
    "pre_single": 13,
    "child_quests": 14,
    "next_quest": 22,
}
ITEM = {"name": 1, "npc_drops": 2, "object_drops": 3}
BANNED_NAME_PARTS = ("UNUSED", "NYI", "TEST", "DEPRECATED", "ZZOLD")
FORBIDDEN_HTML_TERMS = (
    "当前X",
    "当前Y",
    "坐标输入",
    "东南西北",
    "Questie刷新点",
    "置信度",
    "候选路线",
    "任务链关系图",
    "<svg",
    "路线评分",
)


@dataclass(frozen=True)
class RXPInfo:
    source: str
    current_group: str
    current_guide: str
    metadata_count: int
    matched_chain: tuple[str, ...]
    missing_chain: tuple[str, ...]
    has_route_body: bool


@dataclass
class SegmentBuild:
    spec: dict[str, Any]
    candidate: dict[str, Any] | None
    selected_qids: set[int]
    selected_quests: list[dict[str, Any]]
    skipped: dict[str, int]
    steps: list[dict[str, Any]]
    loot_tasks: list[dict[str, Any]]


def parse_rxp_saved_variables(path: Path | None, expected_chain: list[str]) -> RXPInfo:
    if path is None:
        return RXPInfo("未提供", "", "", 0, (), tuple(expected_chain), False)
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"RXP SavedVariables不存在: {resolved}")
    text = resolved.read_text(encoding="utf-8")
    marker = text.find("RXPCData")
    brace = text.find("{", marker)
    if marker == -1 or brace == -1:
        raise ValueError(f"RXP SavedVariables中未找到RXPCData: {resolved}")
    parsed = LuaTableParser(text[brace:]).parse()
    if not isinstance(parsed, dict):
        raise ValueError("RXPCData不是Lua table")
    metadata = parsed.get("guideMetaData")
    metadata = metadata if isinstance(metadata, dict) else {}
    names = {
        str(value.get("name", ""))
        for value in metadata.values()
        if isinstance(value, dict) and value.get("name")
    }
    matched = tuple(name for name in expected_chain if name in names)
    missing = tuple(name for name in expected_chain if name not in names)
    has_route_body = bool(
        re.search(r"(?:^|\s)\.(?:accept|turnin|goto|complete)\b|RegisterGuide|\[\"steps\"\]", text)
    )
    return RXPInfo(
        source=str(resolved),
        current_group=str(parsed.get("currentGuideGroup", "")),
        current_guide=str(parsed.get("currentGuideName", "")),
        metadata_count=len(metadata),
        matched_chain=matched,
        missing_chain=missing,
        has_route_body=has_route_body,
    )


def _candidate_path(root: Path, zone_id: int) -> Path:
    matches = sorted(root.glob(f"{zone_id}-*/route.json"))
    if len(matches) != 1:
        raise FileNotFoundError(f"区域{zone_id}候选数据应唯一，实际找到{len(matches)}个")
    return matches[0]


def _quest_level(quest: dict[str, Any]) -> int:
    required = quest.get("required_level")
    if isinstance(required, int) and required > 0:
        return required
    level = quest.get("quest_level")
    return int(level) if isinstance(level, int) and level > 0 else 1


def _quest_name(data: QuestieData, quest_id: int) -> str:
    row = data.quests.get(quest_id)
    if not isinstance(row, dict):
        return f"任务{quest_id}"
    localized = data.quest_names.get(quest_id)
    if isinstance(localized, dict) and isinstance(localized.get(1), str):
        return localized[1]
    return str(row.get(QUEST["name"], f"任务{quest_id}"))


def _quest_xp(data: QuestieData, quest_id: int) -> tuple[int | None, int | None]:
    row = data.quest_xp.get(quest_id)
    values = seq(row)
    if len(values) < 2:
        return None, None
    level = int(values[0]) if isinstance(values[0], int) and values[0] > 0 else None
    xp = int(values[1]) if isinstance(values[1], int) and values[1] > 0 else None
    return level, xp


def _localized_objective(data: QuestieData, quest_id: int) -> str:
    localized = data.quest_names.get(quest_id)
    if isinstance(localized, dict):
        descriptions = seq(localized.get(2))
        for value in descriptions:
            if isinstance(value, str) and value.strip():
                return value.strip()
    row = data.quests.get(quest_id)
    if isinstance(row, dict):
        descriptions = seq(row.get(8))
        for value in descriptions:
            if isinstance(value, str) and value.strip():
                return value.strip()
    return "未找到任务目标说明。"


def _ids(group: Any, index: int) -> list[int]:
    if not isinstance(group, dict):
        return []
    return [int(value) for value in seq(group.get(index)) if isinstance(value, int)]


def _item_sources(data: QuestieData, item_id: int) -> tuple[bool, bool]:
    row = data.items.get(item_id)
    if not isinstance(row, dict):
        return False, False
    npc_drop = any(isinstance(value, int) for value in seq(row.get(ITEM["npc_drops"])))
    object_drop = any(isinstance(value, int) for value in seq(row.get(ITEM["object_drops"])))
    return npc_drop, object_drop


def _objective_profile(data: QuestieData, quest_id: int) -> dict[str, bool]:
    row = data.quests.get(quest_id)
    profile = {
        "kill": False,
        "kill_drop": False,
        "object": False,
        "object_drop": False,
        "ability": False,
        "item_trigger": False,
    }
    if not isinstance(row, dict):
        return profile
    objectives = row.get(QUEST["objectives"])
    if isinstance(objectives, dict):
        profile["kill"] = bool(seq(objectives.get(1)))
        profile["object"] = bool(seq(objectives.get(2)))
        profile["ability"] = bool(seq(objectives.get(5)))
        for entry in seq(objectives.get(3)):
            values = seq(entry)
            if not values or not isinstance(values[0], int):
                continue
            npc_drop, object_drop = _item_sources(data, values[0])
            profile["kill_drop"] = profile["kill_drop"] or npc_drop
            profile["object_drop"] = profile["object_drop"] or object_drop
    for item_id in _ids(row.get(QUEST["started_by"]), 3):
        npc_drop, object_drop = _item_sources(data, item_id)
        profile["item_trigger"] = profile["item_trigger"] or npc_drop
        profile["kill_drop"] = profile["kill_drop"] or npc_drop
        profile["object_drop"] = profile["object_drop"] or object_drop
    return profile


def _prerequisite_sets(data: QuestieData, quest_id: int) -> tuple[set[int], set[int]]:
    row = data.quests.get(quest_id)
    if not isinstance(row, dict):
        return set(), set()
    required_all = {
        value
        for value in seq(row.get(QUEST["pre_group"]))
        if isinstance(value, int) and value > 0
    }
    required_one = {
        value
        for value in seq(row.get(QUEST["pre_single"]))
        if isinstance(value, int) and value > 0
    }
    return required_all, required_one


def _parent_ids(data: QuestieData, quest_id: int) -> set[int]:
    required_all, required_one = _prerequisite_sets(data, quest_id)
    return required_all | required_one


def _quest_detail(
    data: QuestieData,
    quest_id: int,
    override: dict[str, Any] | None = None,
    kind_override: str | None = None,
) -> dict[str, Any]:
    override = override or {}
    required_all, required_one = _prerequisite_sets(data, quest_id)
    xp_level, base_xp = _quest_xp(data, quest_id)
    profile = _objective_profile(data, quest_id)
    inferred_kind = "collect" if (
        profile["kill_drop"]
        or profile["object"]
        or profile["object_drop"]
        or profile["item_trigger"]
    ) else "simple"
    return {
        "quest_id": quest_id,
        "name": _quest_name(data, quest_id),
        "kind": kind_override or str(override.get("kind") or inferred_kind),
        "xp_level": xp_level,
        "base_xp": base_xp,
        "required_all": [
            {"quest_id": parent, "name": _quest_name(data, parent)}
            for parent in sorted(required_all)
        ],
        "required_one": [
            {"quest_id": parent, "name": _quest_name(data, parent)}
            for parent in sorted(required_one)
        ],
        "objective": str(override.get("objective") or _localized_objective(data, quest_id)),
        "flow": str(override.get("flow") or "按任务目标完成后返回交付。"),
        "fivebox": str(override.get("fivebox") or "尚未实测五开操作，按五号最低进度确认。"),
        "location": str(override.get("location") or ""),
        "note": str(override.get("note") or ""),
    }


def _optional_task_records(data: QuestieData, segment: dict[str, Any]) -> list[dict[str, Any]]:
    detail_overrides = {
        int(key): value
        for key, value in segment.get("quest_details", {}).items()
        if isinstance(value, dict)
    }
    kind_overrides = {
        int(key): str(value)
        for key, value in segment.get("quest_kind_overrides", {}).items()
    }
    records = [
        _quest_detail(
            data,
            int(quest_id),
            detail_overrides.get(int(quest_id)),
            kind_overrides.get(int(quest_id)),
        )
        for quest_id in segment.get("public_optional_quest_ids", [])
    ]
    records.sort(
        key=lambda record: (
            -(int(record["base_xp"]) if isinstance(record.get("base_xp"), int) else -1),
            int(record["quest_id"]),
        )
    )
    return records


def _distance_band(distance: float) -> tuple[str, str]:
    if distance <= 2.5:
        return "same", "同一区域"
    if distance <= 5:
        return "near", "附近"
    if distance <= 8:
        return "separate", "不同任务点"
    return "far", "较远"


def _annotate_distances(steps: list[dict[str, Any]]) -> None:
    previous: tuple[float, float] | None = None
    for step in steps:
        raw = step.get("coords")
        current: tuple[float, float] | None = None
        if (
            isinstance(raw, list)
            and len(raw) == 2
            and all(isinstance(value, (int, float)) for value in raw)
        ):
            current = (float(raw[0]), float(raw[1]))
        if previous is not None and current is not None:
            distance = (
                (previous[0] - current[0]) ** 2
                + (previous[1] - current[1]) ** 2
            ) ** 0.5
            code, label = _distance_band(distance)
            step["distance"] = {
                "value": round(distance, 1),
                "code": code,
                "label": label,
            }
        if current is not None:
            previous = current


def _first_step_order(candidate: dict[str, Any]) -> dict[int, int]:
    order: dict[int, int] = {}
    for index, step in enumerate(candidate.get("steps", [])):
        for quest_id in step.get("quest_ids", []):
            if isinstance(quest_id, int):
                order.setdefault(quest_id, index)
    return order


def _select_quests(
    data: QuestieData,
    candidate: dict[str, Any],
    segment: dict[str, Any],
    used_qids: set[int],
) -> tuple[set[int], list[dict[str, Any]], dict[str, int]]:
    catalog = [quest for quest in candidate.get("quest_catalog", []) if isinstance(quest, dict)]
    by_id = {int(quest["quest_id"]): quest for quest in catalog if isinstance(quest.get("quest_id"), int)}
    order = _first_step_order(candidate)
    quest_min = int(segment["quest_min"])
    quest_max = int(segment["quest_max"])
    max_quests = int(segment.get("max_quests", 30))
    skipped = {"outside_level_band": 0, "already_used": 0, "banned_or_invalid": 0, "route_cap": 0}
    seeds: list[dict[str, Any]] = []
    for quest in catalog:
        quest_id = int(quest["quest_id"])
        name = str(quest.get("name", ""))
        if any(part in name.upper() for part in BANNED_NAME_PARTS):
            skipped["banned_or_invalid"] += 1
            continue
        if quest_id in used_qids:
            skipped["already_used"] += 1
            continue
        level = _quest_level(quest)
        quest_level = quest.get("quest_level")
        if not (quest_min <= level <= quest_max):
            skipped["outside_level_band"] += 1
            continue
        if isinstance(quest_level, int) and quest_level > quest_max + 6:
            skipped["outside_level_band"] += 1
            continue
        seeds.append(quest)
    seeds.sort(key=lambda quest: (order.get(int(quest["quest_id"]), 999999), _quest_level(quest), int(quest["quest_id"])))
    if len(seeds) > max_quests:
        skipped["route_cap"] = len(seeds) - max_quests
        seeds = seeds[:max_quests]
    selected = {int(quest["quest_id"]) for quest in seeds}

    stack = list(selected)
    while stack:
        quest_id = stack.pop()
        quest = by_id.get(quest_id)
        if not quest:
            continue
        required_all, required_one = _prerequisite_sets(data, quest_id)
        parents_to_add = set(required_all)
        if required_one and not (required_one & (selected | used_qids)):
            local_choices = [
                parent
                for parent in required_one
                if parent in by_id
                and not any(
                    part in str(by_id[parent].get("name", "")).upper()
                    for part in BANNED_NAME_PARTS
                )
            ]
            if local_choices:
                parents_to_add.add(
                    min(
                        local_choices,
                        key=lambda parent: (
                            order.get(parent, 999999),
                            _quest_level(by_id[parent]),
                            parent,
                        ),
                    )
                )
        for parent in parents_to_add:
            if parent in by_id and parent not in used_qids and parent not in selected:
                parent_name = str(by_id[parent].get("name", ""))
                if any(part in parent_name.upper() for part in BANNED_NAME_PARTS):
                    continue
                selected.add(parent)
                stack.append(parent)

    selected_quests = [by_id[qid] for qid in selected if qid in by_id]
    selected_quests.sort(key=lambda quest: (order.get(int(quest["quest_id"]), 999999), _quest_level(quest), int(quest["quest_id"])))
    return selected, selected_quests, skipped


def _catalog_by_id(build: SegmentBuild) -> dict[int, dict[str, Any]]:
    if not build.candidate:
        return {}
    return {
        int(quest["quest_id"]): quest
        for quest in build.candidate.get("quest_catalog", [])
        if isinstance(quest, dict) and isinstance(quest.get("quest_id"), int)
    }


def _close_route_prerequisites(data: QuestieData, builds: list[SegmentBuild]) -> dict[str, Any]:
    catalogs = [_catalog_by_id(build) for build in builds]
    orders = [_first_step_order(build.candidate or {}) for build in builds]
    added: list[tuple[int, int]] = []
    removed: list[tuple[int, int, int]] = []
    blocked_qids: set[int] = set()

    def selected_stages() -> dict[int, int]:
        result: dict[int, int] = {}
        for index, build in enumerate(builds):
            for quest_id in build.selected_qids:
                result.setdefault(quest_id, index)
        return result

    def target_for(parent_id: int, child_stage: int) -> int | None:
        if parent_id in blocked_qids:
            return None
        candidates = [
            index
            for index in range(child_stage + 1)
            if parent_id in catalogs[index]
        ]
        if not candidates:
            return None
        parent_level = _quest_level(catalogs[candidates[-1]][parent_id])
        level_matches = [
            index
            for index in candidates
            if int(builds[index].spec.get("quest_min", 1))
            <= parent_level
            <= int(builds[index].spec.get("quest_max", 80))
        ]
        return level_matches[-1] if level_matches else candidates[-1]

    def add_or_move(parent_id: int, target_stage: int) -> None:
        for index, build in enumerate(builds):
            if index != target_stage:
                build.selected_qids.discard(parent_id)
        if parent_id not in builds[target_stage].selected_qids:
            builds[target_stage].selected_qids.add(parent_id)
            builds[target_stage].skipped["prerequisite_added"] = (
                builds[target_stage].skipped.get("prerequisite_added", 0) + 1
            )
            added.append((parent_id, target_stage))

    def remove_child(child_id: int, blocker_id: int, child_stage: int) -> None:
        if builds[child_stage].candidate is None:
            raise ValueError(
                f"人工路线任务缺少无法补入的前置: {child_id} <- {blocker_id}"
            )
        for build in builds:
            build.selected_qids.discard(child_id)
        blocked_qids.add(child_id)
        builds[child_stage].skipped["unreachable_prerequisite_removed"] = (
            builds[child_stage].skipped.get("unreachable_prerequisite_removed", 0) + 1
        )
        removed.append((child_id, blocker_id, child_stage))

    for _ in range(10000):
        stage_by_quest = selected_stages()
        changed = False
        for child_id, child_stage in sorted(stage_by_quest.items(), key=lambda item: (item[1], item[0])):
            required_all, required_one = _prerequisite_sets(data, child_id)

            for parent_id in sorted(required_all):
                parent_stage = stage_by_quest.get(parent_id)
                if parent_stage is not None and parent_stage <= child_stage:
                    continue
                target_stage = target_for(parent_id, child_stage)
                if target_stage is None:
                    remove_child(child_id, parent_id, child_stage)
                else:
                    add_or_move(parent_id, target_stage)
                changed = True
                break
            if changed:
                break

            if required_one:
                fulfilled = [
                    parent_id
                    for parent_id in required_one
                    if stage_by_quest.get(parent_id, child_stage + 1) <= child_stage
                ]
                if not fulfilled:
                    choices: list[tuple[int, int, int]] = []
                    for parent_id in required_one:
                        target_stage = target_for(parent_id, child_stage)
                        if target_stage is None:
                            continue
                        choices.append(
                            (
                                target_stage,
                                -orders[target_stage].get(parent_id, 999999),
                                parent_id,
                            )
                        )
                    if choices:
                        target_stage, _, parent_id = max(choices)
                        add_or_move(parent_id, target_stage)
                    else:
                        remove_child(child_id, min(required_one), child_stage)
                    changed = True
                    break
        if not changed:
            break
    else:
        raise ValueError("任务前置闭包超过迭代上限")

    stage_by_quest = selected_stages()
    unresolved: list[tuple[int, int, int]] = []
    required_parent_ids: set[int] = set()
    for child_id, child_stage in stage_by_quest.items():
        required_all, required_one = _prerequisite_sets(data, child_id)
        for parent_id in required_all:
            parent_stage = stage_by_quest.get(parent_id)
            if parent_stage is None or parent_stage > child_stage:
                unresolved.append((child_id, parent_id, child_stage))
            else:
                required_parent_ids.add(parent_id)
        if required_one:
            fulfilled = [
                parent_id
                for parent_id in required_one
                if stage_by_quest.get(parent_id, child_stage + 1) <= child_stage
            ]
            if not fulfilled:
                unresolved.append((child_id, min(required_one), child_stage))
            else:
                chosen = max(
                    fulfilled,
                    key=lambda parent_id: (stage_by_quest[parent_id], -parent_id),
                )
                required_parent_ids.add(chosen)

    for index, build in enumerate(builds):
        catalog = catalogs[index]
        order = orders[index]
        build.selected_quests = [catalog[qid] for qid in build.selected_qids if qid in catalog]
        build.selected_quests.sort(
            key=lambda quest: (
                order.get(int(quest["quest_id"]), 999999),
                _quest_level(quest),
                int(quest["quest_id"]),
            )
        )

    unique_added = {(quest_id, stage) for quest_id, stage in added}
    unique_removed = {(child, parent, stage) for child, parent, stage in removed}
    return {
        "added_count": len(unique_added),
        "removed_count": len(unique_removed),
        "unresolved": unresolved,
        "required_parent_ids": required_parent_ids,
        "removed": sorted(unique_removed),
    }


def _anchor_name(step: dict[str, Any]) -> str:
    entities = step.get("anchor_details", {}).get("entities", [])
    names: list[str] = []
    for entity in entities:
        name = str(entity.get("name", "")).strip()
        if "：" in name:
            name = name.split("：", 1)[1]
        if not re.search(r"[\u3400-\u9fff]", name):
            continue
        if name and name not in names:
            names.append(name)
        if len(names) == 2:
            break
    return "、".join(names)


def _name_list(data: QuestieData, quest_ids: list[int]) -> str:
    return "、".join(f"《{_quest_name(data, quest_id)}》" for quest_id in quest_ids)


def _make_step(text: str, tags: list[str], quest_ids: list[int] | None = None) -> dict[str, Any]:
    return {"text": text.rstrip("。；") + "。", "tags": list(dict.fromkeys(tags)), "quest_ids": quest_ids or []}


def _objective_group(profile: dict[str, bool], loot_class: str | None) -> str:
    if profile["kill_drop"]:
        return f"loot_{loot_class or 'must'}"
    if profile["ability"]:
        return "ability"
    if profile["object"] or profile["object_drop"]:
        return "object"
    return "kill"


def _objective_text(data: QuestieData, group: str, qids: list[int], anchor: str) -> tuple[str, list[str]]:
    names = _name_list(data, qids)
    place = f"{anchor}：" if anchor else ""
    if group == "loot_must":
        return f"{place}完成{names}，五号分别拾取到齐", ["打怪掉物·必做", "五号分别拾取"]
    if group == "loot_optional":
        return f"{place}经验不足再做{names}；五号分别拾取", ["打怪掉物·可跳", "五号分别拾取"]
    if group == "ability":
        return f"{place}五号分别完成{names}的技能操作", ["五号分别使用技能"]
    if group == "object":
        return f"{place}五号分别完成{names}的点击或拾取", ["五号分别点击"]
    return f"{place}主号完成{names}的击杀目标", []


def _finalize_step_flow(steps: list[dict[str, Any]], next_name: str) -> list[dict[str, Any]]:
    del next_name
    return [
        {**step, "text": str(step["text"]).rstrip("。；") + "。"}
        for step in steps
    ]


def _auto_steps(
    data: QuestieData,
    candidate: dict[str, Any],
    selected_qids: set[int],
    loot_class: dict[int, str],
    segment: dict[str, Any],
    next_name: str,
) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    if segment.get("entry"):
        steps.append(_make_step(str(segment["entry"]), []))

    events: list[dict[str, Any]] = []
    objective_seen: set[int] = set()

    def add_event(kind: str, qids: list[int], anchor: str, anchor_key: tuple[Any, ...]) -> None:
        unique_qids = list(dict.fromkeys(qids))
        if not unique_qids:
            return
        same_area = False
        if events and len(events[-1]["anchor_key"]) == 3 and len(anchor_key) == 3:
            previous_x, previous_y = events[-1]["anchor_key"][1:]
            current_x, current_y = anchor_key[1:]
            if all(
                isinstance(value, (int, float)) and value > -900
                for value in (previous_x, previous_y, current_x, current_y)
            ):
                same_area = (
                    (float(previous_x) - float(current_x)) ** 2
                    + (float(previous_y) - float(current_y)) ** 2
                    <= 6.25
                )
        if (
            events
            and events[-1]["kind"] == kind
            and (events[-1]["anchor_key"] == anchor_key or same_area)
        ):
            merged = list(dict.fromkeys(events[-1]["qids"] + unique_qids))
            if len(merged) <= 4:
                events[-1]["qids"] = merged
                previous_anchors = [
                    value for value in str(events[-1]["anchor"]).split("、") if value
                ]
                if anchor and anchor not in previous_anchors and len(previous_anchors) < 2:
                    events[-1]["anchor"] = "、".join(previous_anchors + [anchor])
                return
        events.append(
            {
                "kind": kind,
                "qids": unique_qids,
                "anchor": anchor,
                "anchor_key": anchor_key,
            }
        )

    for candidate_step in candidate.get("steps", []):
        qids = [qid for qid in candidate_step.get("quest_ids", []) if qid in selected_qids]
        if not qids:
            continue
        action = str(candidate_step.get("action", ""))
        anchor = _anchor_name(candidate_step)
        representative = candidate_step.get("anchor_details", {}).get("representative", {})
        anchor_key = (
            anchor,
            round(float(representative.get("x", -999.0)), 1),
            round(float(representative.get("y", -999.0)), 1),
        )
        if action == "接取":
            add_event("accept", qids, anchor, anchor_key)
            continue
        if action == "交付":
            for quest_id in qids:
                if quest_id in loot_class and quest_id not in objective_seen:
                    add_event(
                        f"loot_{loot_class[quest_id]}",
                        [quest_id],
                        "",
                        ("synthetic", quest_id),
                    )
                    objective_seen.add(quest_id)
            add_event("turnin", qids, anchor, anchor_key)
            continue

        grouped: dict[str, list[int]] = {}
        group_order: list[str] = []
        for quest_id in qids:
            profile = _objective_profile(data, quest_id)
            group = _objective_group(profile, loot_class.get(quest_id))
            if group not in grouped:
                grouped[group] = []
                group_order.append(group)
            grouped[group].append(quest_id)
        for group in group_order:
            add_event(group, grouped[group], anchor, anchor_key)
            objective_seen.update(grouped[group])

    for quest_id in sorted(loot_class):
        if quest_id in selected_qids and quest_id not in objective_seen:
            add_event(
                f"loot_{loot_class[quest_id]}",
                [quest_id],
                "",
                ("synthetic", quest_id),
            )
            objective_seen.add(quest_id)

    for event in events:
        anchor = event["anchor"]
        qids = event["qids"]
        kind = event["kind"]
        if kind == "accept":
            place = f"到{anchor}" if anchor else "在当前任务中心"
            steps.append(_make_step(f"{place}集中接取{_name_list(data, qids)}", ["五号分别接取"], qids))
        elif kind == "turnin":
            place = f"到{anchor}" if anchor else "返回当前任务中心"
            steps.append(_make_step(f"{place}集中交付{_name_list(data, qids)}", ["五号分别交付"], qids))
        else:
            text, tags = _objective_text(data, kind, qids, anchor)
            steps.append(_make_step(text, tags, qids))

    optional_count = sum(1 for value in loot_class.values() if value == "optional")
    if next_name:
        if optional_count:
            branch = f"经验足够：前往{next_name}；经验不足：补做本地区尚未完成的支线任务"
        else:
            branch = f"经验足够：前往{next_name}；经验不足：完成本地区剩余任务"
    else:
        branch = "达到80级：路线结束；经验不足：完成冰冠冰川剩余任务"
    steps.append(_make_step(branch, []))
    return _finalize_step_flow(steps, next_name)


def _steps_from_spec(raw_steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for raw in raw_steps:
        step = _make_step(
            str(raw.get("text") or raw.get("action") or "执行当前步骤"),
            [str(tag) for tag in raw.get("tags", [])],
            [int(value) for value in raw.get("quest_ids", [])],
        )
        for key in ("location", "npc", "target", "action", "coords", "note"):
            if key in raw:
                step[key] = raw[key]
        steps.append(step)
    return steps


def _manual_steps(segment: dict[str, Any], next_name: str) -> list[dict[str, Any]]:
    steps = _steps_from_spec(segment.get("manual_steps", []))
    steps.append(
        _make_step(
            f"经验足够：前往{next_name}；经验不足：补做本地区尚未完成的任务",
            [],
        )
    )
    return _finalize_step_flow(steps, next_name)


def _annotate_quest_kinds(
    data: QuestieData,
    steps: list[dict[str, Any]],
    segment: dict[str, Any] | None = None,
) -> None:
    segment = segment or {}
    detail_overrides = {
        int(key): value
        for key, value in segment.get("quest_details", {}).items()
        if isinstance(value, dict)
    }
    kind_overrides = {
        int(key): str(value)
        for key, value in segment.get("quest_kind_overrides", {}).items()
    }
    for step in steps:
        quest_kinds: dict[str, str] = {}
        quest_details: list[dict[str, Any]] = []
        for raw_quest_id in step.get("quest_ids", []):
            quest_id = int(raw_quest_id)
            detail = _quest_detail(
                data,
                quest_id,
                detail_overrides.get(quest_id),
                kind_overrides.get(quest_id),
            )
            quest_kinds[detail["name"]] = detail["kind"]
            quest_details.append(detail)
        step["quest_kinds"] = quest_kinds
        step["quest_details"] = quest_details


def _build_loot_classifications(
    data: QuestieData,
    builds: list[SegmentBuild],
    manual_overrides: dict[int, dict[str, Any]],
    required_parent_ids: set[int],
) -> dict[int, str]:
    all_selected = set(manual_overrides)
    for build in builds:
        all_selected.update(build.selected_qids)
    classifications: dict[int, str] = {}
    for quest_id in all_selected:
        if quest_id in manual_overrides:
            classifications[quest_id] = str(manual_overrides[quest_id]["classification"])
            continue
        if _objective_profile(data, quest_id)["kill_drop"]:
            classifications[quest_id] = "must" if quest_id in required_parent_ids else "optional"
    return classifications


def _loot_records(
    data: QuestieData,
    qids: set[int],
    classifications: dict[int, str],
    manual_overrides: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for quest_id in sorted(qids):
        classification = classifications.get(quest_id)
        if not classification:
            continue
        override = manual_overrides.get(quest_id, {})
        reason = override.get("reason")
        if not reason:
            reason = "仍有后续选中任务依赖" if classification == "must" else "未被后续选中任务依赖，可作为经验补充"
        records.append(
            {
                "quest_id": quest_id,
                "name": override.get("name") or _quest_name(data, quest_id),
                "classification": classification,
                "reason": reason,
            }
        )
    return records


def build_simple_route(
    data: QuestieData,
    spec_path: Path,
    candidate_root: Path,
    rxp_path: Path | None,
) -> dict[str, Any]:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    rxp = parse_rxp_saved_variables(rxp_path, [str(value) for value in spec.get("rxp_chain", [])])
    builds: list[SegmentBuild] = []
    used_qids: set[int] = set()
    manual_overrides: dict[int, dict[str, Any]] = {}

    for segment in spec["segments"]:
        override_qids: set[int] = set()
        for record in segment.get("loot_tasks", []):
            quest_id = int(record["quest_id"])
            manual_overrides[quest_id] = dict(record)
            override_qids.add(quest_id)
        if segment.get("manual_steps"):
            manual_qids = {
                int(value) for value in segment.get("manual_quest_ids", [])
            } | override_qids
            used_qids.update(manual_qids)
            builds.append(SegmentBuild(segment, None, manual_qids, [], {}, [], []))
            continue
        candidate_path = _candidate_path(candidate_root, int(segment["zone_id"]))
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
        selected, selected_quests, skipped = _select_quests(data, candidate, segment, used_qids)
        candidate_qids = {
            int(quest["quest_id"])
            for quest in candidate.get("quest_catalog", [])
            if isinstance(quest, dict) and isinstance(quest.get("quest_id"), int)
        }
        prefix_qids = {
            int(value) for value in segment.get("manual_prefix_quest_ids", [])
        } | {
            int(value) for value in segment.get("public_optional_quest_ids", [])
        } | override_qids
        selected.update(prefix_qids & candidate_qids)
        used_qids.update(selected)
        builds.append(SegmentBuild(segment, candidate, selected, selected_quests, skipped, [], []))

    prerequisite_audit = _close_route_prerequisites(data, builds)
    if prerequisite_audit["unresolved"]:
        raise ValueError(
            f"路线仍有{len(prerequisite_audit['unresolved'])}条未满足前置"
        )
    classifications = _build_loot_classifications(
        data,
        builds,
        manual_overrides,
        prerequisite_audit["required_parent_ids"],
    )
    segments: list[dict[str, Any]] = []
    for index, build in enumerate(builds):
        segment = build.spec
        next_name = str(builds[index + 1].spec["name"]) if index + 1 < len(builds) else ""
        if segment.get("manual_steps"):
            steps = _manual_steps(segment, next_name)
            public_steps = list(steps)
            loot_tasks = _loot_records(
                data, build.selected_qids, classifications, manual_overrides
            )
            selected_count = len(build.selected_qids)
        else:
            assert build.candidate is not None
            local_class = {
                qid: classifications[qid]
                for qid in build.selected_qids
                if qid in classifications
            }
            prefix_qids = {
                int(value) for value in segment.get("manual_prefix_quest_ids", [])
            } | {
                int(value) for value in segment.get("public_optional_quest_ids", [])
            }
            prefix_steps = _steps_from_spec(
                segment.get("manual_prefix_steps", [])
            )
            auto_segment = dict(segment)
            if prefix_steps:
                auto_segment.pop("entry", None)
            auto_qids = build.selected_qids - prefix_qids
            auto_class = {
                qid: value for qid, value in local_class.items() if qid in auto_qids
            }
            steps = prefix_steps + _auto_steps(
                data,
                build.candidate,
                auto_qids,
                auto_class,
                auto_segment,
                next_name,
            )
            if prefix_steps:
                public_steps = prefix_steps + [
                    _make_step(
                        "本地图后半段尚未人工实跑，暂不提供路线",
                        [],
                    )
                ]
            else:
                public_steps = [
                    _make_step(
                        "本地图尚未人工实跑，暂不提供路线",
                        [],
                    )
                ]
            loot_tasks = _loot_records(
                data, build.selected_qids, classifications, manual_overrides
            )
            selected_count = len(build.selected_qids)
        _annotate_quest_kinds(data, steps, segment)
        _annotate_quest_kinds(data, public_steps, segment)
        _annotate_distances(public_steps)
        optional_tasks = _optional_task_records(data, segment)
        build.steps = steps
        build.loot_tasks = loot_tasks
        segments.append(
            {
                "id": segment["id"],
                "name": segment["name"],
                "level_min": int(segment["level_min"]),
                "level_max": int(segment["level_max"]),
                "audit": segment["audit"],
                "steps": steps,
                "public_steps": public_steps,
                "optional_tasks": optional_tasks,
                "loot_tasks": loot_tasks,
                "selected_quest_ids": sorted(build.selected_qids),
                "selected_quest_count": selected_count,
                "skipped": build.skipped,
            }
        )

    unique_loot: dict[int, dict[str, Any]] = {}
    for segment in segments:
        for record in segment["loot_tasks"]:
            unique_loot[int(record["quest_id"])] = record
    must_count = sum(1 for record in unique_loot.values() if record["classification"] == "must")
    optional_count = sum(1 for record in unique_loot.values() if record["classification"] == "optional")
    removed_details: list[dict[str, Any]] = []
    for child_id, blocker_id, stage_index in prerequisite_audit["removed"]:
        required_all, required_one = _prerequisite_sets(data, child_id)
        reason = (
            "缺少必须全部完成的前置任务"
            if blocker_id in required_all
            else "没有任一可达的可选前置任务"
        )
        removed_details.append(
            {
                "quest_id": child_id,
                "name": _quest_name(data, child_id),
                "blocker_id": blocker_id,
                "blocker_name": _quest_name(data, blocker_id),
                "segment": builds[stage_index].spec["name"],
                "level_min": builds[stage_index].spec["level_min"],
                "level_max": builds[stage_index].spec["level_max"],
                "reason": reason,
            }
        )
    result = {
        "route_id": spec["route_id"],
        "title": spec["title"],
        "character": spec["character"],
        "mode": spec["mode"],
        "source": {"questie_version": data.version, "questie_sha256": data.source_sha256, "rxp": rxp},
        "segments": segments,
        "internal_audit": {"prerequisite_removed": removed_details},
        "stats": {
            "segment_count": len(segments),
            "step_count": sum(len(segment["steps"]) for segment in segments),
            "public_step_count": sum(
                len(segment["public_steps"]) for segment in segments
            ),
            "selected_quest_count": sum(segment["selected_quest_count"] for segment in segments),
            "prerequisite_added_count": prerequisite_audit["added_count"],
            "prerequisite_removed_count": prerequisite_audit["removed_count"],
            "unresolved_prerequisite_count": len(prerequisite_audit["unresolved"]),
            "loot_must_count": must_count,
            "loot_optional_count": optional_count,
        },
    }
    validate_simple_route(result)
    return result


def validate_simple_route(route: dict[str, Any]) -> None:
    if not route.get("segments"):
        raise ValueError("极简路线没有地图")
    ids: set[str] = set()
    for segment in route["segments"]:
        if segment["id"] in ids:
            raise ValueError(f"重复地图阶段ID: {segment['id']}")
        ids.add(segment["id"])
        if not segment.get("steps"):
            raise ValueError(f"地图没有步骤: {segment['name']}")
        for step in segment["steps"]:
            if not str(step.get("text", "")).strip():
                raise ValueError(f"存在空步骤: {segment['name']}")
    for segment in route["segments"]:
        optional_ids = {
            int(record["quest_id"])
            for record in segment.get("optional_tasks", [])
        }
        for quest_id in optional_ids:
            if any(
                quest_id in step.get("quest_ids", [])
                for step in segment.get("public_steps", segment["steps"])
            ):
                raise ValueError(f"可选任务仍混在主流程中: {quest_id}")
        for record in segment["loot_tasks"]:
            if record["classification"] not in {"must", "optional"}:
                raise ValueError(f"掉落任务未分类: {record}")
            quest_id = int(record["quest_id"])
            if quest_id in optional_ids:
                continue
            if any(
                quest_id in step.get("quest_ids", [])
                for step in segment.get("public_steps", segment["steps"])
            ):
                continue
            expected_tag = "打怪掉物·必做" if record["classification"] == "must" else "打怪掉物·可跳"
            if not any(
                quest_id in step.get("quest_ids", []) and expected_tag in step.get("tags", [])
                for step in segment["steps"]
            ):
                raise ValueError(f"掉落任务未在内部步骤或补经验清单中显示: {quest_id} {record['name']}")


def _colored_quest_text(text: str, quest_kinds: dict[str, str]) -> str:
    parts: list[str] = []
    position = 0
    for match in re.finditer(r"《([^》]+)》", text):
        parts.append(html.escape(text[position:match.start()]))
        quest_name = match.group(1)
        kind = quest_kinds.get(quest_name, "simple")
        parts.append(
            f'<span class="quest-name quest-{kind}">《{html.escape(quest_name)}》</span>'
        )
        position = match.end()
    parts.append(html.escape(text[position:]))
    return "".join(parts)


def _prerequisite_html(detail: dict[str, Any]) -> str:
    required_all = detail.get("required_all", [])
    required_one = detail.get("required_one", [])
    if required_all:
        names = "、".join(
            f'《{html.escape(str(record["name"]))}》' for record in required_all
        )
        return f"必须先完成：{names}"
    if required_one:
        names = "、".join(
            f'《{html.escape(str(record["name"]))}》' for record in required_one
        )
        if len(required_one) == 1:
            return f"必须先完成：{names}"
        return f"前置任务（任选其一）：{names}"
    return "无前置任务"


def _quest_detail_html(detail: dict[str, Any], extra_class: str = "") -> str:
    kind = str(detail.get("kind", "simple"))
    name = html.escape(str(detail.get("name", "未知任务")))
    xp = detail.get("base_xp")
    xp_text = f"{int(xp)} 经验" if isinstance(xp, int) else "经验未知"
    level = detail.get("xp_level")
    xp_note = (
        f"任务等级 {int(level)} 的同级基础经验；角色等级变化和临时经验加成会改变实际值。"
        if isinstance(level, int)
        else "未记录可用的经验等级。"
    )
    location = str(detail.get("location", "")).strip()
    note = str(detail.get("note", "")).strip()
    rows = [
        f'<div><dt>经验</dt><dd><strong>{html.escape(xp_text)}</strong><small>{html.escape(xp_note)}</small></dd></div>',
        f'<div><dt>前置</dt><dd>{_prerequisite_html(detail)}</dd></div>',
        f'<div><dt>流程</dt><dd>{html.escape(str(detail.get("flow", "")))}</dd></div>',
        f'<div><dt>五开判断</dt><dd>{html.escape(str(detail.get("fivebox", "")))}</dd></div>',
        f'<div><dt>任务目标</dt><dd>{html.escape(str(detail.get("objective", "")))}</dd></div>',
    ]
    if location:
        rows.insert(2, f'<div><dt>地点</dt><dd>{html.escape(location)}</dd></div>')
    if note:
        rows.append(f'<div><dt>备注</dt><dd>{html.escape(note)}</dd></div>')
    class_name = "quest-detail" + (f" {extra_class}" if extra_class else "")
    return (
        f'<details class="{class_name}"><summary>'
        f'<span class="quest-name quest-{html.escape(kind)}">《{name}》</span>'
        f'<span class="xp-chip">{html.escape(xp_text)}</span></summary>'
        f'<dl>{"".join(rows)}</dl></details>'
    )


def _step_text_html(step: dict[str, Any]) -> str:
    quest_kinds = step.get("quest_kinds", {})
    structured = any(step.get(key) for key in ("location", "npc", "target", "action"))
    blocks: list[str] = []
    if structured:
        fields: list[str] = []
        for label, key in (("地点", "location"), ("NPC", "npc"), ("目标", "target"), ("操作", "action")):
            value = str(step.get(key, "")).strip()
            if not value:
                continue
            fields.append(
                f'<div class="step-field"><span>{label}</span><b>{_colored_quest_text(value, quest_kinds)}</b></div>'
            )
        blocks.append(f'<div class="step-fields">{"".join(fields)}</div>')
    else:
        blocks.append(
            f'<div class="legacy-step-text">{_colored_quest_text(str(step.get("text", "")), quest_kinds)}</div>'
        )
    details = step.get("quest_details", [])
    if details:
        blocks.append(
            '<div class="step-quests">'
            + "".join(_quest_detail_html(detail) for detail in details)
            + "</div>"
        )
    note = str(step.get("note", "")).strip()
    if note:
        blocks.append(f'<p class="step-note">{html.escape(note)}</p>')
    return "".join(blocks)


def _optional_tasks_html(segment: dict[str, Any]) -> str:
    tasks = segment.get("optional_tasks", [])
    if not tasks:
        return ""
    cards = "".join(_quest_detail_html(task, "optional-task") for task in tasks)
    return (
        '<section class="optional-section">'
        '<header><div><p>经验不足时再做</p><h3>补经验任务</h3></div>'
        f'<span>{len(tasks)} 个任务</span></header>'
        '<p class="optional-intro">不计入主流程进度，已按同级基础经验从高到低排列。展开任务名可查看前置、路线和五开操作。</p>'
        f'<div class="optional-list">{cards}</div></section>'
    )


def render_simple_html(route: dict[str, Any]) -> str:
    tabs: list[str] = []
    panels: list[str] = []
    for index, segment in enumerate(route["segments"]):
        active = index == 0
        tabs.append(
            f'<button class="map-tab" role="tab" aria-selected="{str(active).lower()}" '
            f'aria-controls="panel-{html.escape(segment["id"])}" data-panel="{html.escape(segment["id"])}">'
            f'<strong>{html.escape(segment["name"])}</strong><small>{segment["level_min"]}—{segment["level_max"]}</small></button>'
        )
        items: list[str] = []
        visible_steps = segment.get("public_steps", segment["steps"])
        for step_index, step in enumerate(visible_steps, 1):
            step_id = f'{segment["id"]}-{step_index}'
            distance = step.get("distance")
            tools = ""
            if isinstance(distance, dict):
                tools = (
                    f'<div class="step-tools"><span class="distance distance-{html.escape(str(distance["code"]))}">'
                    f'{html.escape(str(distance["label"]))} · {float(distance["value"]):.1f}</span>'
                    f'<button type="button" class="far-mark" aria-pressed="false">标记过远</button></div>'
                )
            items.append(
                f'<li class="route-step" data-step="{html.escape(step_id)}" '
                f'data-map-name="{html.escape(segment["name"])}" data-step-number="{step_index}">'
                f'<div class="step-layout"><label class="step-check"><input type="checkbox" aria-label="完成步骤{step_index}">'
                f'<span class="step-number">{step_index}</span></label>'
                f'<div class="step-copy">{_step_text_html(step)}{tools}</div></div></li>'
            )
        hidden = "" if active else " hidden"
        panels.append(
            f'<section id="panel-{html.escape(segment["id"])}" class="map-panel" role="tabpanel" '
            f'data-panel-id="{html.escape(segment["id"])}"{hidden}>'
            f'<header class="map-heading"><div><p>等级 {segment["level_min"]}—{segment["level_max"]}</p>'
            f'<h2>{html.escape(segment["name"])}</h2></div><span class="map-progress">0 / {len(items)}</span></header>'
            f'<ol>{"".join(items)}</ol>{_optional_tasks_html(segment)}'
            f'<div class="panel-nav"><button class="prev-map">上一地图</button>'
            f'<button class="next-map">下一地图</button></div></section>'
        )

    css = """
:root{--paper:#f7f3e8;--ink:#201d18;--muted:#6f675b;--line:#d8cfbd;--blood:#8f2434;--blood-dark:#641724;--gold:#a96f13;--soft:#eee5d2;--collect:#b51f32;--simple:#27823d;--done:#8c9785;--same:#4f7a56;--near:#7d7023;--separate:#a45f18;--far:#9a2f35}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:18px/1.55 "PingFang SC","Microsoft YaHei","Noto Sans CJK SC",system-ui,sans-serif}button,input{font:inherit}button{cursor:pointer}.top{padding:34px 24px 20px;border-bottom:1px solid var(--line);background:linear-gradient(180deg,#fbf8f0 0%,var(--paper) 100%)}.top-inner{max-width:980px;margin:auto}.eyebrow{margin:0 0 8px;color:var(--blood);font-size:14px;font-weight:800;letter-spacing:.14em}.top h1{margin:0;font-family:"Songti SC","STSong","Noto Serif CJK SC",serif;font-size:clamp(34px,6vw,58px);line-height:1.08;letter-spacing:-.04em}.lede{max-width:760px;margin:16px 0 18px;color:var(--muted)}.route-status{display:flex;gap:14px;align-items:center;flex-wrap:wrap}.progress-pill{display:inline-flex;gap:7px;align-items:baseline;padding:8px 12px;border:1px solid var(--line);background:#fffaf0;border-radius:999px}.progress-pill strong{font-size:22px;color:var(--blood)}.reset{border:0;background:transparent;color:var(--muted);text-decoration:underline;text-underline-offset:4px}.tabs-wrap{position:sticky;top:0;z-index:10;background:rgba(247,243,232,.96);backdrop-filter:blur(12px);border-bottom:1px solid var(--line)}.map-tabs{max-width:100%;display:flex;gap:8px;overflow-x:auto;padding:12px max(18px,calc((100vw - 980px)/2));scrollbar-width:thin}.map-tab{flex:0 0 auto;display:grid;gap:1px;min-width:112px;padding:10px 14px;border:1px solid var(--line);border-radius:8px;background:#fffaf1;color:var(--ink);text-align:left}.map-tab strong{font-size:16px}.map-tab small{color:var(--muted);font-size:12px}.map-tab[aria-selected="true"]{border-color:var(--blood);background:var(--blood);color:white;box-shadow:0 5px 16px rgba(100,23,36,.18)}.map-tab[aria-selected="true"] small{color:#f4dfe3}.map-tab:focus-visible,.route-step input:focus-visible,.panel-nav button:focus-visible,.reset:focus-visible,.copy-far:focus-visible,.far-mark:focus-visible,.quest-detail summary:focus-visible{outline:3px solid #2b68b8;outline-offset:3px}main{max-width:980px;margin:0 auto;padding:34px 20px 80px}.map-panel[hidden]{display:none}.map-heading{display:flex;justify-content:space-between;align-items:end;gap:20px;margin-bottom:22px;padding-bottom:16px;border-bottom:2px solid var(--ink)}.map-heading p{margin:0 0 2px;color:var(--blood);font-size:14px;font-weight:800}.map-heading h2{margin:0;font-family:"Songti SC","STSong","Noto Serif CJK SC",serif;font-size:clamp(32px,5vw,48px)}.map-progress{color:var(--muted);font-variant-numeric:tabular-nums}ol{list-style:none;margin:0;padding:0;counter-reset:route}.route-step{border-bottom:1px solid var(--line)}.route-step:hover{background:rgba(238,229,210,.4)}.step-layout{display:grid;grid-template-columns:82px minmax(0,1fr);align-items:start;gap:12px;padding:18px 8px}.step-check{display:grid;grid-template-columns:28px 42px;align-items:start;gap:8px;cursor:pointer}.route-step input{width:22px;height:22px;margin-top:7px;accent-color:var(--blood)}.step-number{display:grid;place-items:center;width:38px;height:38px;border:1px solid var(--line);border-radius:50%;font-weight:800;font-variant-numeric:tabular-nums}.step-copy{min-width:0;font-size:clamp(17px,2.2vw,20px)}.step-fields{display:grid;gap:7px}.step-field{display:grid;grid-template-columns:58px minmax(0,1fr);gap:12px;align-items:start}.step-field>span{padding-top:2px;color:var(--muted);font-size:13px;font-weight:800;letter-spacing:.08em}.step-field>b{font-weight:700}.legacy-step-text{font-weight:650}.step-quests{display:grid;gap:7px;margin-top:12px}.quest-name{font-weight:900}.quest-collect{color:var(--collect)}.quest-simple{color:var(--simple)}.quest-detail{border:1px solid var(--line);border-radius:8px;background:#fffaf1}.quest-detail summary{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 12px;cursor:pointer;list-style:none}.quest-detail summary::-webkit-details-marker{display:none}.quest-detail summary:before{content:'＋';flex:0 0 auto;color:var(--muted);font-weight:800}.quest-detail[open] summary:before{content:'－'}.quest-detail summary .quest-name{margin-right:auto}.xp-chip{flex:0 0 auto;padding:2px 8px;border:1px solid var(--line);border-radius:999px;color:var(--muted);font-size:12px;font-weight:800}.quest-detail dl{display:grid;gap:0;margin:0;padding:0 12px 12px}.quest-detail dl>div{display:grid;grid-template-columns:70px minmax(0,1fr);gap:12px;padding:8px 0;border-top:1px solid var(--line)}.quest-detail dt{color:var(--muted);font-size:13px;font-weight:800}.quest-detail dd{margin:0;font-size:15px}.quest-detail dd small{display:block;margin-top:3px;color:var(--muted);font-size:12px}.step-tools{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:12px}.distance{display:inline-flex;padding:4px 9px;border-radius:999px;background:#fff;font-size:12px;font-weight:800}.distance-same{color:var(--same);border:1px solid color-mix(in srgb,var(--same) 40%,transparent)}.distance-near{color:var(--near);border:1px solid color-mix(in srgb,var(--near) 40%,transparent)}.distance-separate{color:var(--separate);border:1px solid color-mix(in srgb,var(--separate) 40%,transparent)}.distance-far{color:var(--far);border:1px solid color-mix(in srgb,var(--far) 40%,transparent)}.far-mark{padding:4px 9px;border:1px solid var(--line);border-radius:999px;background:transparent;color:var(--muted);font-size:12px;font-weight:800}.far-mark[aria-pressed="true"]{border-color:var(--far);background:#fff0f1;color:var(--far)}.step-note{margin:10px 0 0;padding:8px 10px;border-left:3px solid var(--gold);background:#fff6df;color:var(--muted);font-size:14px}.route-step.done>.step-layout{opacity:.55}.route-step.done .step-number{background:var(--soft)}.optional-section{margin-top:42px;padding:24px;border:1px solid var(--line);border-radius:12px;background:#f0eadc}.optional-section>header{display:flex;align-items:end;justify-content:space-between;gap:16px;padding-bottom:14px;border-bottom:1px solid var(--line)}.optional-section>header p{margin:0;color:var(--blood);font-size:13px;font-weight:800;letter-spacing:.08em}.optional-section h3{margin:2px 0 0;font-family:"Songti SC","STSong","Noto Serif CJK SC",serif;font-size:30px}.optional-section>header>span{color:var(--muted);font-size:13px;font-weight:800}.optional-intro{margin:14px 0;color:var(--muted);font-size:14px}.optional-list{display:grid;gap:9px}.optional-task{background:#fbf7ed}.distance-legend{display:flex;gap:7px;flex-wrap:wrap;margin:0 0 18px}.distance-legend .distance{background:#fffaf0}.copy-far,.reset{border:0;background:transparent;color:var(--muted);text-decoration:underline;text-underline-offset:4px}.panel-nav{display:flex;justify-content:space-between;gap:12px;margin-top:28px}.panel-nav button{min-width:140px;padding:11px 16px;border:1px solid var(--line);border-radius:7px;background:#fffaf1;color:var(--ink);font-weight:800}.panel-nav button:disabled{opacity:.35;cursor:not-allowed}.next-map{margin-left:auto;background:var(--blood)!important;border-color:var(--blood)!important;color:white!important}.noscript{max-width:980px;margin:20px auto;padding:14px 20px;background:#fff0cf;border:1px solid #d3a651}
@media(max-width:620px){body{font-size:16px}.top{padding:26px 18px 18px}.step-layout{grid-template-columns:66px minmax(0,1fr);gap:7px;padding:15px 2px}.step-check{grid-template-columns:24px 36px;gap:5px}.route-step input{width:20px;height:20px}.step-number{width:34px;height:34px}.step-field{grid-template-columns:48px minmax(0,1fr);gap:8px}.quest-detail summary{align-items:flex-start;flex-wrap:wrap}.xp-chip{margin-left:28px}.quest-detail dl>div{grid-template-columns:1fr;gap:3px}.optional-section{padding:18px 14px}.map-heading{align-items:start}.panel-nav button{min-width:0;flex:1}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
"""
    script = """
(() => {
  const storageKey = 'wow-simple-route-v2';
  const farStorageKey = 'wow-simple-route-far-v1';
  const tabs = [...document.querySelectorAll('.map-tab')];
  const panels = [...document.querySelectorAll('.map-panel')];
  const allSteps = [...document.querySelectorAll('.route-step')];
  let state = {};
  let farState = {};
  try { state = JSON.parse(localStorage.getItem(storageKey) || '{}'); } catch (_) { state = {}; }
  try { farState = JSON.parse(localStorage.getItem(farStorageKey) || '{}'); } catch (_) { farState = {}; }

  function save() { localStorage.setItem(storageKey, JSON.stringify(state)); }
  function saveFar() { localStorage.setItem(farStorageKey, JSON.stringify(farState)); }
  function updateProgress() {
    const done = allSteps.filter(step => state[step.dataset.step]).length;
    document.querySelector('#done-count').textContent = done;
    document.querySelector('#total-count').textContent = allSteps.length;
    panels.forEach(panel => {
      const steps = [...panel.querySelectorAll('.route-step')];
      const count = steps.filter(step => state[step.dataset.step]).length;
      panel.querySelector('.map-progress').textContent = `${count} / ${steps.length}`;
    });
  }
  function activate(index, focus = false) {
    index = Math.max(0, Math.min(index, tabs.length - 1));
    tabs.forEach((tab, i) => {
      const active = i === index;
      tab.setAttribute('aria-selected', String(active));
      panels[i].hidden = !active;
    });
    tabs[index].scrollIntoView({block:'nearest', inline:'center'});
    if (focus) tabs[index].focus();
    history.replaceState(null, '', `#${tabs[index].dataset.panel}`);
    window.scrollTo({top: document.querySelector('.tabs-wrap').offsetTop, behavior:'smooth'});
  }
  function markedStepText(step) {
    const copy = step.querySelector('.step-fields, .legacy-step-text');
    const body = copy ? copy.innerText.trim().replace(/\\s+/g, ' ') : '';
    return `${step.dataset.mapName} 第${step.dataset.stepNumber}步：${body}`;
  }
  async function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return;
    }
    const area = document.createElement('textarea');
    area.value = text;
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    document.execCommand('copy');
    area.remove();
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => activate(index));
    tab.addEventListener('keydown', event => {
      if (event.key === 'ArrowRight') { event.preventDefault(); activate(index + 1, true); }
      if (event.key === 'ArrowLeft') { event.preventDefault(); activate(index - 1, true); }
    });
  });
  allSteps.forEach(step => {
    const box = step.querySelector('input[type="checkbox"]');
    box.checked = Boolean(state[step.dataset.step]);
    step.classList.toggle('done', box.checked);
    box.addEventListener('change', () => {
      state[step.dataset.step] = box.checked;
      step.classList.toggle('done', box.checked);
      save();
      updateProgress();
    });
    const mark = step.querySelector('.far-mark');
    if (mark) {
      const marked = Boolean(farState[step.dataset.step]);
      mark.setAttribute('aria-pressed', String(marked));
      mark.textContent = marked ? '已标记过远' : '标记过远';
      mark.addEventListener('click', () => {
        const next = !Boolean(farState[step.dataset.step]);
        farState[step.dataset.step] = next;
        mark.setAttribute('aria-pressed', String(next));
        mark.textContent = next ? '已标记过远' : '标记过远';
        saveFar();
      });
    }
  });
  panels.forEach((panel, index) => {
    const prev = panel.querySelector('.prev-map');
    const next = panel.querySelector('.next-map');
    prev.disabled = index === 0;
    next.disabled = index === panels.length - 1;
    prev.addEventListener('click', () => activate(index - 1));
    next.addEventListener('click', () => activate(index + 1));
  });
  document.querySelector('.reset').addEventListener('click', () => {
    if (!confirm('清空全部勾选进度？')) return;
    state = {};
    save();
    allSteps.forEach(step => {
      step.querySelector('input[type="checkbox"]').checked = false;
      step.classList.remove('done');
    });
    updateProgress();
  });
  const copyFar = document.querySelector('.copy-far');
  copyFar.addEventListener('click', async () => {
    const marked = allSteps.filter(step => farState[step.dataset.step]);
    if (!marked.length) {
      copyFar.textContent = '还没有标记过远';
      setTimeout(() => { copyFar.textContent = '复制过远标记'; }, 1600);
      return;
    }
    const text = marked.map(markedStepText).join('\\n');
    try {
      await copyText(text);
      copyFar.textContent = `已复制 ${marked.length} 条`;
    } catch (_) {
      copyFar.textContent = '复制失败';
    }
    setTimeout(() => { copyFar.textContent = '复制过远标记'; }, 1600);
  });
  const hash = decodeURIComponent(location.hash.slice(1));
  const initial = tabs.findIndex(tab => tab.dataset.panel === hash);
  activate(initial >= 0 ? initial : 0);
  updateProgress();
})();
"""
    rendered = f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(route["title"])}</title>
<style>{css}</style>
</head>
<body>
<header class="top"><div class="top-inner">
<p class="eyebrow">五开号 · 单一路线</p>
<h1>{html.escape(route["title"])}</h1>
<p class="lede">红色任务名表示需要反复逐号收集、数量较多或掉落不稳定；绿色包括共享击杀、单个必掉物和单次点击。任务名可展开查看前置、经验和完整流程。</p>
<div class="distance-legend" aria-label="地图坐标距离分级"><span class="distance distance-same">0—2.5 同一区域</span><span class="distance distance-near">2.5—5 附近</span><span class="distance distance-separate">5—8 不同任务点</span><span class="distance distance-far">大于8 较远</span></div>
<div class="route-status"><span class="progress-pill"><strong id="done-count">0</strong><span>/</span><span id="total-count">0</span><span>已完成</span></span><button class="copy-far" type="button">复制过远标记</button><button class="reset" type="button">清空勾选</button></div>
</div></header>
<div class="tabs-wrap"><nav class="map-tabs" role="tablist" aria-label="练级地图">{''.join(tabs)}</nav></div>
<noscript><div class="noscript">页面仍可阅读，但勾选保存和地图切换需要启用浏览器脚本。</div></noscript>
<main>{''.join(panels)}</main>
<script>{script}</script>
</body></html>'''
    for term in FORBIDDEN_HTML_TERMS:
        if term in rendered:
            raise ValueError(f"用户页面出现禁止内容: {term}")
    return rendered


def write_simple_html(route: dict[str, Any], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_simple_html(route), encoding="utf-8")
    return output


def render_audit_markdown(route: dict[str, Any]) -> str:
    rxp: RXPInfo = route["source"]["rxp"]
    stats = route["stats"]
    sequence = " → ".join(segment["name"] for segment in route["segments"])
    lines = [
        "# NEAT：1—80级极简任务路线内部归档",
        "",
        "## N — 最终目标和路线策略",
        "",
        "- 最终用户入口只有一个HTML文件，但未经实跑的自动阶段只能视为审阅草稿，不能称为可用攻略。",
        "- 五个角色按一个主控号移动；普通击杀默认由主号完成，个人拾取和点击以五号最低进度为准。",
        "- 收集或点击类任务名直接标红，普通击杀、接交和简单流程标绿；用户页面不显示独立分类标签。",
        "- 第一轮目标是连续升到80级，而不是全地图清空或金币最大化。",
        "- RXP只参考地图阶段；Questie提供任务候选和前置；实际顺序必须由道路、炉石、飞行与实跑决定。",
        f"- 最终地图顺序：{sequence}",
        "",
        "## E — 使用的数据",
        "",
        f"- Questie：v{route['source']['questie_version']}，SHA256 `{route['source']['questie_sha256']}`。",
        "- Questie候选数据：现有68区域候选JSON，仅作为任务清单和接取/目标/交付顺序来源；旧导航页面未复用。",
        "- 逐日岛：人工步骤骨架、五开实测分类和脱敏人物历程。",
        f"- RXP SavedVariables：`{rxp.source}`。当前指南组 `{rxp.current_group}`，当前指南 `{rxp.current_guide}`。",
        f"- RXP指南元数据共 {rxp.metadata_count} 项；本路线预期链命中 {len(rxp.matched_chain)} 项，缺少 {len(rxp.missing_chain)} 项。",
        f"- RXP是否包含逐步路线正文：{'是' if rxp.has_route_body else '否'}。未发现 `.accept/.turnin/.goto/.complete` 或步骤表，因此不得把指南目录虚构成完整路线。",
        "",
        "## A — 禁止恢复的旧方案",
        "",
        "- 不恢复坐标输入、方向计算、抽象地图、圆圈、连线、任务链图、候选评分或实际历程面板。",
        "- 不恢复自制游戏内插件、移动轨迹采集、自动接交、输入广播、自动切窗、客户端注入、内存读取或抓包。",
        "- 不再生成68个区域页面；旧页面保留为历史产物，但新路线不依赖其界面。",
        "",
        "## T — 测试结果和尚未验证的问题",
        "",
        f"- 生成地图阶段：{stats['segment_count']}。",
        f"- 内部候选步骤：{stats['step_count']}；用户页面公开步骤：{stats['public_step_count']}。",
        f"- 进入主路线候选的Questie任务：{stats['selected_quest_count']}。",
        f"- 自动补入可达前置：{stats['prerequisite_added_count']} 个；因主路线无法满足前置而删除：{stats['prerequisite_removed_count']} 个。",
        f"- 最终未满足前置：{stats['unresolved_prerequisite_count']} 条。`preQuestGroup`按全部完成，`preQuestSingle`按任选其一校验。",
        f"- 内部仍分类为必做掉落 {stats['loot_must_count']} 个、可跳掉落 {stats['loot_optional_count']} 个，但用户页面只通过任务名红/绿着色表达操作重点。",
        "- 逐日岛1—6级为人工编排，其中西侧树人/神殿顺序和菲伦德雷任务物品的五开行为仍需继续实跑。",
        "- 永歌森林鹰翼广场至晴风村已根据2026-07-31实测反馈人工修订：加入炉石，拆分鱼头、军备、书页、法力水晶，并把豹皮并入游侠萨蕾恩路线。",
        "- 永歌森林后半段及12—80级仍是自动候选草稿；取消跨地点动作合并后步骤数明显增加，证明其不能直接作为攻略发布。",
        "- Questie WotLK修正层尚未完整叠加到基础库；若实际任务与页面不一致，应先核对修正层再改路线。",
        "- 静态校验会检查：单HTML、地图标签、步骤非空、掉落任务内部分类完整、页面不含旧导航器字段与旧分类标签。",
        "- 2026-07-31验证：`python3 -m unittest discover -s tests` 共13项通过；最终提交前需再次执行页面脚本 `node --check`。",
        "",
        "## RXP与Questie不一致或需要解释的地方",
        "",
        "- RXP把出生段和永歌森林合称为“01-06 永歌森林”；Questie任务字段使用3431，实际地图区域使用3430。用户页面拆成“逐日岛”和“永歌森林”。",
        "- RXP元数据出现“幽冥之地”“幽灵之地”两种译名；Questie和用户实际地图名统一为“幽魂之地”。",
        "- RXP的59—61地狱火半岛与56—60瘟疫之地存在等级重叠；页面按先完成旧世界核心链、约60级进入外域处理。",
        "- RXP的67—69虚空风暴直接衔接68—71嚎风峡湾，说明允许等级重叠并跳过影月谷；本路线照此执行。",
        "- RXP元数据包含38—40希尔斯布莱德回访和42—43尘泥沼泽回访；Questie闭包审计后两段都没有独立可接任务，因此页面分别由尘泥沼泽36—39和荒芜之地40—43承接，不保留空地图标签。",
        "- SavedVariables中的任务缓存混有其他种族和地区任务，它只反映历史状态，不作为血精灵路线任务清单。",
        "",
        "## 被删除或跳过的任务及原因",
        "",
        "| 地图阶段 | 选入任务 | 等级带外 | 已在前段使用 | 名称异常 | 数量上限裁剪 | 前置补入 | 前置不可达删除 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for segment in route["segments"]:
        skipped = segment.get("skipped", {})
        lines.append(
            f"| {segment['name']} {segment['level_min']}—{segment['level_max']} | {segment['selected_quest_count']} | "
            f"{skipped.get('outside_level_band', 0)} | {skipped.get('already_used', 0)} | "
            f"{skipped.get('banned_or_invalid', 0)} | {skipped.get('route_cap', 0)} | "
            f"{skipped.get('prerequisite_added', 0)} | {skipped.get('unreachable_prerequisite_removed', 0)} |"
        )
    lines.extend(["", "因前置不可达删除的任务：", ""])
    removed_records = route.get("internal_audit", {}).get("prerequisite_removed", [])
    for record in removed_records:
        lines.append(
            f"- `{record['quest_id']}` {record['name']}（{record['segment']} {record['level_min']}—{record['level_max']}）："
            f"{record['reason']}；阻断前置示例为 `{record['blocker_id']}` {record['blocker_name']}。"
        )
    if not removed_records:
        lines.append("- 无。")
    lines.extend(["", "可跳掉落任务：", ""])
    optional_records: list[str] = []
    seen: set[int] = set()
    for segment in route["segments"]:
        for record in segment["loot_tasks"]:
            quest_id = int(record["quest_id"])
            if record["classification"] == "optional" and quest_id not in seen:
                seen.add(quest_id)
                optional_records.append(
                    f"- `{quest_id}` {record['name']}：{record['reason']}（{segment['name']} {segment['level_min']}—{segment['level_max']}）"
                )
    lines.extend(optional_records or ["- 无。"])
    lines.extend(["", "## 人工审计状态", ""])
    for segment in route["segments"]:
        lines.append(f"- {segment['name']} {segment['level_min']}—{segment['level_max']}：{segment['audit']}。")
    return "\n".join(lines) + "\n"


def write_audit_markdown(route: dict[str, Any], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_audit_markdown(route), encoding="utf-8")
    return output
