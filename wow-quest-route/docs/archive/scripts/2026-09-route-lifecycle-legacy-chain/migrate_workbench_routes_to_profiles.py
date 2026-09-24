from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.route_profiles import ROUTE_PROFILES_DIR, RouteProfileError, validate_route_profile
from lib.task_cards import load_all_task_cards

WORKBENCH = ROOT / "data/route-atlas/workbench-routes.json"
EVIDENCE_INDEX = ROOT / "_sandbox/task-evidence-index.sqlite"
OVERRIDES = ROOT / "tasks/task-card-migration/workbench-task-id-overrides.json"
ROUTE_MODELS_DIR = ROOT / "data/route-models"
ROUTE_UI_DIR = ROOT / "data/route-ui"
REVIEW_OUT = ROOT / "tasks/route-profile-migration-review.json"

TASK_RE = re.compile(r"《([^》]+)》")
GAME_VARIANT_ID = "timewalking-wotlk-cn"
SYSTEM_PREFIXES = {
    "开飞行点：": "open_flight_point",
    "绑定炉石：": "bind_hearth",
    "炉石绑定：": "bind_hearth",
    "使用炉石：": "use_hearth",
    "系统飞行：": "taxi",
    "固定交通：": "fixed_transport",
    "任务传送：": "quest_transport",
}

# Explicit route correction proven by the latest live Dragonblight run: 12089 is handed in at the
# later step-26 Agmar return. The earlier point64 duplicate is stale legacy display data.
TASK_ACTION_SKIPS = {
    ("dragonblight", 64, 12089, "turnin"): "data/observations/route-timing-runs.json#2026-08-21 step26 correction",
}

PROFILE_META: dict[str, dict[str, str]] = {
    "hellfire": {"profile_id": "hellfire-fivebox", "character_profile": "horde-fivebox-current"},
    "zang": {"profile_id": "zangarmarsh-fivebox", "character_profile": "horde-fivebox-current"},
    "nagrand": {"profile_id": "nagrand-fivebox-67-68", "character_profile": "horde-fivebox-current"},
    "borean": {"profile_id": "borean-fivebox", "character_profile": "horde-fivebox-current"},
    "dragonblight": {"profile_id": "dragonblight-fivebox", "character_profile": "horde-fivebox-current"},
    "dalaran": {"profile_id": "dalaran-mainline-77", "character_profile": "horde-fivebox-current"},
    "storm": {"profile_id": "storm-peaks-fivebox", "character_profile": "horde-fivebox-current"},
    "icecrown": {"profile_id": "icecrown-fivebox", "character_profile": "horde-fivebox-current"},
    "sholazar": {"profile_id": "sholazar-fivebox", "character_profile": "horde-fivebox-current"},
    "zuldrak": {"profile_id": "zuldrak-fivebox", "character_profile": "horde-fivebox-current"},
    "grizzly": {"profile_id": "grizzly-fivebox", "character_profile": "horde-fivebox-current"},
    "howling": {"profile_id": "howling-fivebox", "character_profile": "horde-fivebox-current"},
    "zang_dk": {"profile_id": "zangarmarsh-dk-speed", "character_profile": "dk-twohand-blood-current"},
}


def _load_index() -> tuple[dict[tuple[str, int, str], list[int]], dict[int, dict[str, Any]]]:
    if not EVIDENCE_INDEX.exists():
        raise RuntimeError(f"missing evidence index: {EVIDENCE_INDEX}")
    occurrence_ids: dict[tuple[str, int, str], list[int]] = defaultdict(list)
    questie_by_id: dict[int, dict[str, Any]] = {}
    with sqlite3.connect(EVIDENCE_INDEX) as conn:
        for task_id, payload_json in conn.execute("SELECT task_id, payload_json FROM tasks ORDER BY task_id"):
            payload = json.loads(payload_json)
            questie_by_id[int(task_id)] = payload.get("questie") or {}
            for occ in payload.get("workbench_occurrences") or []:
                key = (str(occ["route_key"]), int(occ["point_index"]), str(occ["task_name"]))
                if int(task_id) not in occurrence_ids[key]:
                    occurrence_ids[key].append(int(task_id))
    return occurrence_ids, questie_by_id


def _load_override_ids() -> dict[tuple[str, int, str], list[int]]:
    payload = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    out: dict[tuple[str, int, str], list[int]] = {}
    for key, value in (payload.get("overrides") or {}).items():
        route_key, point_index, task_name = key.split("|", 2)
        out[(route_key, int(point_index), task_name)] = [int(x) for x in value.get("task_ids") or []]
    return out


def _task_kind(line: str, task_start: int) -> str:
    prefix = line[:task_start]
    candidates = [
        (prefix.rfind("交"), "turnin"),
        (prefix.rfind("接"), "accept"),
        (prefix.rfind("做"), "objective"),
    ]
    position, kind = max(candidates, key=lambda item: item[0])
    if position < 0:
        raise RuntimeError(f"cannot infer task action: {line!r}")
    return kind


def _system_action(line: str, location_ref: str) -> dict[str, Any] | None:
    stripped = line.strip()
    for prefix, kind in SYSTEM_PREFIXES.items():
        if not stripped.startswith(prefix):
            continue
        payload = stripped[len(prefix):].strip()
        action: dict[str, Any] = {"kind": kind, "location_ref": location_ref}
        if kind in {"taxi", "fixed_transport", "quest_transport"}:
            parts = [part.strip() for part in payload.split("→") if part.strip()]
            if len(parts) < 2:
                return None
            action["from_name"] = parts[0]
            action["to_name"] = parts[-1]
        else:
            action["target_name"] = payload
        return action
    return None


def _actor_from_questie(task_id: int, kind: str, line: str, questie_by_id: dict[int, dict[str, Any]]) -> tuple[str, str] | None:
    if kind not in {"accept", "turnin"}:
        return None
    questie = questie_by_id.get(task_id) or {}
    field = "start_entities" if kind == "accept" else "finish_entities"
    entities = [e for e in (questie.get(field) or []) if e.get("name_zhcn")]
    if not entities:
        return None
    if len(entities) > 1:
        in_line = [e for e in entities if str(e["name_zhcn"]) in line]
        if len(in_line) == 1:
            entities = in_line
        elif len({str(e["name_zhcn"]) for e in entities}) == 1:
            entities = [entities[0]]
        else:
            return None
    entity = entities[0]
    key = "npc_name" if entity.get("kind") == "npc" else "target_name"
    return key, str(entity["name_zhcn"])


def _clause_for_match(line: str, match: re.Match[str]) -> str:
    left = max(line.rfind("；", 0, match.start()), line.rfind(";", 0, match.start()))
    right_candidates = [p for p in (line.find("；", match.end()), line.find(";", match.end())) if p >= 0]
    right = min(right_candidates) if right_candidates else len(line)
    return line[left + 1 : right].strip()


def _kind_for_match(line: str, match: re.Match[str]) -> str:
    clause = _clause_for_match(line, match)
    task_token = match.group(0)
    if re.search(re.escape(task_token) + r"\s*则?交", clause):
        return "turnin"
    if re.search(re.escape(task_token) + r"\s*则?接", clause):
        return "accept"
    if re.search(r"推进\s*" + re.escape(task_token), clause):
        return "objective"
    return _task_kind(line, match.start())


def _actor_from_line(line: str, match: re.Match[str]) -> str | None:
    clause = _clause_for_match(line, match)
    verb_pos = max(clause.rfind("交", 0, clause.find(match.group(0)) + 1), clause.rfind("接", 0, clause.find(match.group(0)) + 1))
    if verb_pos < 0:
        # Conditional grammar may place the task name before the verb: 若携带《X》则交.
        verb_pos = max(clause.find("交", clause.find(match.group(0))), clause.find("接", clause.find(match.group(0))))
    prefix = clause[:verb_pos] if verb_pos >= 0 else clause
    parts = [part.strip() for part in prefix.split("→") if part.strip()]
    if not parts:
        return None
    candidate = parts[0]
    candidate = re.sub(r"^若[^：:]*[：:]", "", candidate).strip()
    if candidate.startswith(("若携带", "若已接", "若已完成", "若五号", "若任务", "如果")):
        return None
    if candidate.startswith(("陆路", "系统飞行", "固定交通", "任务传送", "使用炉石", "绑定炉石", "开飞行点")):
        return None
    return candidate or None


def _condition_from_clause(clause: str, task_name: str, task_id: int) -> dict[str, Any] | None:
    stripped_without_tasks = TASK_RE.sub("", clause).strip()
    if "若任务仍在" in stripped_without_tasks or "若已接" in stripped_without_tasks:
        return {"kind": "task_active", "task_id": task_id}
    if "若携带" in clause and f"《{task_name}》" in clause:
        return {"kind": "task_active", "task_id": task_id}
    if "若已完成" in stripped_without_tasks or "若五号均已满足条件" in stripped_without_tasks:
        return {"kind": "task_complete", "task_id": task_id}
    match = re.search(r"若持有([^：:；，,]+)", stripped_without_tasks)
    if match:
        return {"kind": "has_item", "item_name": match.group(1).strip()}
    return None


def _clause_has_condition(clause: str) -> bool:
    value = TASK_RE.sub("", clause)
    return bool(re.search(r"(?:^|→)\s*(?:若|如果)", value))


def _prose_actions(line: str, location_ref: str, point_title: str) -> list[dict[str, Any]] | None:
    value = line.strip()
    if not value or value == point_title:
        return []
    match = re.fullmatch(r"开启(.+?)飞行点", value)
    if match:
        return [{"kind": "open_flight_point", "location_ref": location_ref, "target_name": match.group(1).strip()}]
    match = re.fullmatch(r"(?:任务中途)?使用(.+?)[：:](.+)", value)
    if match:
        device, rest = match.group(1).strip(), match.group(2).strip()
        actions: list[dict[str, Any]] = [{"kind": "interact", "location_ref": location_ref, "target_name": f"使用{device}"}]
        rest = re.sub(r"^(?:进入|前往)", "", rest).strip()
        parts = [part.strip() for part in rest.split("→") if part.strip()]
        if len(parts) >= 2:
            actions.append({"kind": "fixed_transport", "location_ref": location_ref, "from_name": parts[0], "to_name": parts[-1]})
        elif parts:
            actions.append({"kind": "fixed_transport", "location_ref": location_ref, "from_name": point_title, "to_name": parts[0]})
        return actions
    match = re.fullmatch(r"启动(.+?)[：:](?:前往|进入)(.+)", value)
    if match:
        script_name, destination = match.group(1).strip(), match.group(2).strip()
        return [
            {"kind": "interact", "location_ref": location_ref, "target_name": f"启动{script_name}"},
            {"kind": "fixed_transport", "location_ref": location_ref, "from_name": point_title, "to_name": destination},
        ]
    match = re.fullmatch(r"(?:立刻)?使用(.+?)(?:回到|返回)(.+)", value)
    if match:
        device, destination = match.group(1).strip(), match.group(2).strip()
        return [
            {"kind": "interact", "location_ref": location_ref, "target_name": f"使用{device}"},
            {"kind": "fixed_transport", "location_ref": location_ref, "from_name": point_title, "to_name": destination},
        ]
    match = re.fullmatch(r"传送回(.+)", value)
    if match:
        return [{"kind": "fixed_transport", "location_ref": location_ref, "from_name": point_title, "to_name": match.group(1).strip()}]
    if value.startswith("通过") and value.endswith("返回"):
        return [{"kind": "interact", "location_ref": location_ref, "target_name": value}]
    match = re.fullmatch(r"使用(.+)", value)
    if match:
        return [{"kind": "interact", "location_ref": location_ref, "target_name": f"使用{match.group(1).strip()}"}]
    if value == "从这里进入洞穴":
        return [{"kind": "move", "location_ref": location_ref, "to_name": "洞穴内部"}]
    match = re.fullmatch(r"到(.+?)处", value)
    if match:
        return [{"kind": "move", "location_ref": location_ref, "to_name": match.group(1).strip()}]
    match = re.fullmatch(r"抵达(.+)", value)
    if match:
        return [{"kind": "move", "location_ref": location_ref, "to_name": match.group(1).strip()}]
    match = re.fullmatch(r"返回登船点重新登上(.+)", value)
    if match:
        return [{"kind": "interact", "location_ref": location_ref, "target_name": f"重新登上{match.group(1).strip()}"}]
    match = re.fullmatch(r"陆路(?:前往|北上到)(.+)", value)
    if match:
        return [{"kind": "move", "location_ref": location_ref, "to_name": match.group(1).strip()}]
    match = re.fullmatch(r"返回(.+)", value)
    if match:
        return [{"kind": "move", "location_ref": location_ref, "to_name": match.group(1).strip()}]
    if "→" in value:
        actor, target = (part.strip() for part in value.split("→", 1))
        if actor and target:
            return [{"kind": "interact", "location_ref": location_ref, "npc_name": actor, "target_name": target}]
    return None


def _profile_scope(route: dict[str, Any]) -> str:
    display = str(route.get("displayName") or "").strip()
    if display:
        return display.replace("（DK专用）", "")
    title = str(route.get("title") or "").strip()
    return title.split("·", 1)[0].strip() or "route"


def _display_name(route: dict[str, Any]) -> str:
    value = str(route.get("displayName") or "").strip()
    if value:
        return value
    return _profile_scope(route)


def _state_contracts(actions: list[dict[str, Any]], hearth_chain: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    first_kind: dict[int, str] = {}
    active: set[int] = set()
    maybe_active: set[int] = set()
    entry: set[int] = set()
    for action in actions:
        kind = action.get("kind")
        task_id = action.get("task_id")
        if kind not in {"accept", "objective", "turnin"} or not isinstance(task_id, int):
            continue
        first_kind.setdefault(task_id, kind)
    entry = {task_id for task_id, kind in first_kind.items() if kind in {"objective", "turnin"}}
    active = set(entry)
    for action in actions:
        kind = action.get("kind")
        task_id = action.get("task_id")
        if kind not in {"accept", "objective", "turnin"} or not isinstance(task_id, int):
            continue
        condition = action.get("when")
        if kind == "accept":
            if condition is None:
                active.add(task_id)
            elif condition.get("kind") == "has_item":
                maybe_active.add(task_id)
        elif kind == "turnin":
            if condition and condition.get("kind") in {"task_active", "task_complete"}:
                active.discard(task_id)
                maybe_active.discard(task_id)
            elif condition is None:
                active.discard(task_id)
    entry_state: dict[str, Any] = {"active_task_ids": sorted(entry)}
    exit_state: dict[str, Any] = {"active_task_ids": sorted(active)}
    bind_targets = [str(action["target_name"]) for action in actions if action.get("kind") == "bind_hearth"]
    if hearth_chain:
        # The legacy hearthChain is a player-display history, not automatically an entry-state fact.
        # Treat its first value as inherited only when this profile does not bind that value itself.
        if hearth_chain[0] not in bind_targets:
            entry_state["hearth_location"] = hearth_chain[0]
        if bind_targets:
            exit_state["hearth_location"] = bind_targets[-1]
        elif "hearth_location" in entry_state:
            exit_state["hearth_location"] = entry_state["hearth_location"]
    return entry_state, exit_state


def _timing_model(profile_id: str, route_key: str, route: dict[str, Any]) -> dict[str, Any]:
    timing = route.get("timing") or {}
    route_model: dict[str, Any] = {
        "center_minutes": timing.get("centerMinutes"),
        "range_minutes": timing.get("rangeMinutes"),
    }
    for source_key, target_key in (("status", "status"), ("model", "model"), ("actualRuns", "actual_runs")):
        if source_key in timing:
            route_model[target_key] = timing[source_key]
    steps: dict[str, Any] = {}
    for index, group in enumerate(route.get("stepGroups", []), 1):
        step_timing = group.get("timing") or {}
        row: dict[str, Any] = {
            "center_minutes": step_timing.get("centerMinutes"),
            "range_minutes": step_timing.get("rangeMinutes"),
        }
        if "includeInTotal" in step_timing:
            row["include_in_total"] = bool(step_timing["includeInTotal"])
        if step_timing.get("status"):
            row["status"] = step_timing["status"]
        steps[f"step-{index:02d}"] = row
    return {
        "schema_version": 1,
        "profile_id": profile_id,
        "status": str(timing.get("status") or timing.get("model") or "legacy_current_budget"),
        "source_ref": f"data/route-atlas/workbench-routes.json#{route_key}",
        "display_badge": str(route.get("badge") or ""),
        "route": route_model,
        "steps": steps,
    }


def _route_ui(profile_id: str, route: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "profile_id": profile_id,
        "map_labels": [
            {"x": float(label[0]), "y": float(label[1]), "display_name": str(label[2])}
            for label in route.get("labels", [])
            if isinstance(label, list) and len(label) >= 3
        ],
    }


def _step_groups(route: dict[str, Any], action_ids_by_point: dict[int, list[str]]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for index, group in enumerate(route.get("stepGroups", []), 1):
        start, end = int(group["start"]), int(group["end"])
        action_ids: list[str] = []
        for point_index in range(start, end + 1):
            action_ids.extend(action_ids_by_point.get(point_index, []))
        if not action_ids:
            raise RuntimeError(f"step {index} has no actions")
        groups.append({
            "step_id": f"step-{index:02d}",
            "title": str(group.get("title") or f"步骤{index}"),
            "summary": str(group.get("summary") or "") or None,
            "action_ids": action_ids,
        })
    return groups


def migrate_route(
    route_key: str,
    route: dict[str, Any],
    cards: dict[int, dict[str, Any]],
    occurrence_ids: dict[tuple[str, int, str], list[int]],
    override_ids: dict[tuple[str, int, str], list[int]],
    questie_by_id: dict[int, dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    meta = PROFILE_META[route_key]
    profile_id = meta["profile_id"]
    actions: list[dict[str, Any]] = []
    action_ids_by_point: dict[int, list[str]] = defaultdict(list)
    locations: dict[str, dict[str, Any]] = {}
    reviews: list[dict[str, Any]] = []
    serial = 0

    def add(action: dict[str, Any], point_index: int) -> None:
        nonlocal serial
        serial += 1
        action["action_id"] = f"a{serial:04d}"
        actions.append(action)
        action_ids_by_point[point_index].append(action["action_id"])

    for point_index, point in enumerate(route.get("points", [])):
        title = str(point[2] if len(point) > 2 else "").strip() or f"位置{point_index + 1}"
        location_ref = f"{route_key}-p{point_index + 1:03d}"
        x, y = point[0], point[1]
        location = {
            "display_name": title,
            "x": x,
            "y": y,
            "phase": str(point[4] if len(point) > 4 else "default") or "default",
        }
        if len(point) > 6 and str(point[6]).strip():
            location["transport"] = str(point[6]).strip()
        locations[location_ref] = location
        add({"kind": "location", "location_ref": location_ref}, point_index)

        action_text = str(point[3] if len(point) > 3 else "")
        matches_by_name: dict[str, list[re.Match[str]]] = defaultdict(list)
        for match in TASK_RE.finditer(action_text):
            matches_by_name[match.group(1)].append(match)
        multi_cursor: dict[str, int] = defaultdict(int)

        for raw_line in action_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            system = _system_action(line, location_ref)
            if system is not None:
                add(system, point_index)
                continue
            line_matches = list(TASK_RE.finditer(line))
            if not line_matches:
                prose = _prose_actions(line, location_ref, title)
                if prose is None:
                    reviews.append({
                        "route_key": route_key,
                        "point_index": point_index,
                        "point_title": title,
                        "reason": "unparsed_prose_action",
                        "text": line,
                    })
                else:
                    for action in prose:
                        add(action, point_index)
                continue

            for match in line_matches:
                task_name = match.group(1)
                clause = _clause_for_match(line, match)
                if "确认已接" in line and f"《{task_name}》" in line:
                    continue
                if re.search(r"(?:暂不|不要|不再)接\s*" + re.escape(match.group(0)), clause):
                    continue
                key = (route_key, point_index, task_name)
                ids = override_ids.get(key) or occurrence_ids.get(key) or []
                if not ids:
                    reviews.append({"route_key": route_key, "point_index": point_index, "point_title": title, "task_name": task_name, "reason": "task_id_unresolved", "text": line})
                    continue
                if len(ids) == 1:
                    task_id = ids[0]
                else:
                    cursor = multi_cursor[task_name]
                    if cursor >= len(ids):
                        reviews.append({"route_key": route_key, "point_index": point_index, "point_title": title, "task_name": task_name, "reason": "multi_id_occurrence_overflow", "task_ids": ids, "text": line})
                        continue
                    task_id = ids[cursor]
                    multi_cursor[task_name] += 1

                try:
                    kind = _kind_for_match(line, match)
                except RuntimeError:
                    reviews.append({"route_key": route_key, "point_index": point_index, "point_title": title, "task_name": task_name, "reason": "task_kind_unresolved", "text": line})
                    continue
                if (route_key, point_index, task_id, kind) in TASK_ACTION_SKIPS:
                    continue
                action: dict[str, Any] = {"kind": kind, "task_id": task_id, "location_ref": location_ref}
                actor = _actor_from_questie(task_id, kind, line, questie_by_id)
                if actor:
                    action[actor[0]] = actor[1]
                elif kind in {"accept", "turnin"}:
                    fallback_actor = _actor_from_line(line, match)
                    if fallback_actor:
                        action["target_name"] = fallback_actor
                    else:
                        reviews.append({"route_key": route_key, "point_index": point_index, "point_title": title, "task_id": task_id, "task_name": task_name, "reason": "actor_unresolved", "text": line})
                        continue

                clause = _clause_for_match(line, match)
                condition = _condition_from_clause(clause, task_name, task_id)
                if condition:
                    action["when"] = condition
                elif _clause_has_condition(clause) and kind in {"accept", "turnin", "objective"}:
                    reviews.append({"route_key": route_key, "point_index": point_index, "point_title": title, "task_id": task_id, "task_name": task_name, "reason": "condition_unresolved", "text": line})
                    continue
                add(action, point_index)

        for task_name, ids in ((name, override_ids.get((route_key, point_index, name)) or []) for name in matches_by_name):
            if len(ids) > 1 and multi_cursor[task_name] != len(ids):
                reviews.append({
                    "route_key": route_key,
                    "point_index": point_index,
                    "point_title": title,
                    "task_name": task_name,
                    "reason": "multi_id_occurrence_count_mismatch",
                    "task_ids": ids,
                    "used": multi_cursor[task_name],
                })

    if reviews:
        return None, _timing_model(profile_id, route_key, route), _route_ui(profile_id, route), reviews

    task_ids: list[int] = []
    for action in actions:
        task_id = action.get("task_id")
        if isinstance(task_id, int) and task_id not in task_ids:
            task_ids.append(task_id)
    hearth_chain = [str(x) for x in route.get("hearthChain", []) if str(x).strip()]
    entry_state, exit_state = _state_contracts(actions, hearth_chain)
    profile = {
        "schema_version": 1,
        "profile_id": profile_id,
        "version": 1,
        "status": "draft",
        "scope": {
            "route_scope": _profile_scope(route),
            "character_profile": meta["character_profile"],
            "game_variant_id": GAME_VARIANT_ID,
        },
        "entry_state_contract": entry_state,
        "exit_state_contract": exit_state,
        "goal": {"summary": str(route.get("sub") or route.get("title") or profile_id)},
        "display": {
            "publish_key": route_key,
            "order": int(route.get("order", 0)),
            "title": str(route.get("title") or route_key),
            "display_name": _display_name(route),
            "subtitle": str(route.get("sub") or ""),
            "footer": str(route.get("footer") or ""),
            "map_image": str(route.get("image") or ""),
        },
        "task_ids": task_ids,
        "actions": actions,
        "step_groups": _step_groups(route, action_ids_by_point),
        "geometry": {"locations": locations},
        "change_log": [{
            "date": "2026-09-16",
            "kind": "architecture_migration",
            "summary": "从当前正式workbench机械迁移稳定task_id、路线动作、步骤与几何；玩家备注/地图悬浮标签/时间模型分别归属Task Presentation、UI、Timing。",
        }],
    }
    try:
        validate_route_profile(profile, known_task_cards=cards)
    except RouteProfileError as exc:
        reviews.append({
            "route_key": route_key,
            "reason": "profile_validation_error",
            "error": str(exc),
        })
        return None, _timing_model(profile_id, route_key, route), _route_ui(profile_id, route), reviews
    return profile, _timing_model(profile_id, route_key, route), _route_ui(profile_id, route), []


def main() -> None:
    raise SystemExit('RETIRED: Route Profile v2 uses entry_requirements and Replay-derived exit state; do not regenerate formal Profiles from legacy workbench.')
    parser = argparse.ArgumentParser(description="Batch-migrate current workbench routes to Route Profile candidates without semantic guessing.")
    parser.add_argument("route_keys", nargs="*", help="Workbench route keys. Default: all supported routes except hellfire_dk pilot.")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    routes = json.loads(WORKBENCH.read_text(encoding="utf-8"))
    cards = load_all_task_cards()
    occurrence_ids, questie_by_id = _load_index()
    override_ids = _load_override_ids()
    route_keys = args.route_keys or list(PROFILE_META)
    unknown = [key for key in route_keys if key not in PROFILE_META or key not in routes]
    if unknown:
        raise SystemExit(f"unsupported/missing route keys: {unknown}")

    summary: dict[str, Any] = {}
    all_reviews: list[dict[str, Any]] = []
    outputs: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    for route_key in route_keys:
        profile, timing_model, route_ui, reviews = migrate_route(
            route_key, routes[route_key], cards, occurrence_ids, override_ids, questie_by_id
        )
        if reviews:
            all_reviews.extend(reviews)
            summary[route_key] = {"status": "review", "review_count": len(reviews)}
            continue
        assert profile is not None
        outputs.append((profile, timing_model, route_ui))
        summary[route_key] = {
            "status": "ready",
            "profile_id": profile["profile_id"],
            "task_count": len(profile["task_ids"]),
            "action_count": len(profile["actions"]),
            "step_count": len(profile["step_groups"]),
            "entry_active": profile["entry_state_contract"]["active_task_ids"],
            "exit_active": profile["exit_state_contract"]["active_task_ids"],
        }

    result = {
        "routes": summary,
        "ready_count": sum(1 for x in summary.values() if x["status"] == "ready"),
        "review_route_count": sum(1 for x in summary.values() if x["status"] == "review"),
        "review_item_count": len(all_reviews),
        "write": args.write,
    }
    if args.write:
        ROUTE_PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        ROUTE_MODELS_DIR.mkdir(parents=True, exist_ok=True)
        ROUTE_UI_DIR.mkdir(parents=True, exist_ok=True)
        for profile, timing_model, route_ui in outputs:
            profile_id = profile["profile_id"]
            (ROUTE_PROFILES_DIR / f"{profile_id}.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            (ROUTE_MODELS_DIR / f"{profile_id}-timing.json").write_text(json.dumps(timing_model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            (ROUTE_UI_DIR / f"{profile_id}.json").write_text(json.dumps(route_ui, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        REVIEW_OUT.write_text(json.dumps({"schema_version": 1, "review_count": len(all_reviews), "items": all_reviews}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if all_reviews:
        print(json.dumps({"review_preview": all_reviews[:40]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
