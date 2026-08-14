from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.questie_source import QuestieData, load_questie


ZONE_ID = 3521
ZONE_NAME = "赞加沼泽"
DEFAULT_QUESTIE = ROOT.parent / ".ai-bridge" / "Questie.zip"
DEFAULT_MAP = ROOT / "data" / "route-atlas" / "assets" / "zangarmarsh-base.jpg"
DEFAULT_OUTPUT = ROOT / "data" / "routes" / "zangarmarsh-route-atlas-prototype.html"
DEFAULT_JSON = ROOT / "data" / "route-atlas" / "zangarmarsh-npc-validation.json"
DEFAULT_TASK_PROFILES = ROOT / "data" / "route-atlas" / "zangarmarsh-task-profiles.json"
DEFAULT_MACRO_ROUTE = ROOT / "data" / "route-atlas" / "zangarmarsh-macro-route-v1.json"
DEFAULT_MACRO_ACTIONS = ROOT / "data" / "route-atlas" / "zangarmarsh-macro-route-actions-v1.json"
DEFAULT_SPECIAL_MECHANISMS = ROOT / "data" / "route-atlas" / "special-mechanism-registry.json"
DEFAULT_FIRST_RUN = ROOT / "data" / "route-atlas" / "zangarmarsh-first-run-v1.json"

# Questie WotLK compact DB field indexes used by the current project source parser.
Q_NAME = 1
Q_STARTED_BY = 2
Q_FINISHED_BY = 3
Q_REQUIRED_LEVEL = 4
Q_QUEST_LEVEL = 5
Q_OBJECTIVE_TEXT = 8
Q_TRIGGER_END = 9
Q_OBJECTIVES = 10
Q_PRE_GROUP = 12
Q_PRE_SINGLE = 13
Q_ZONE_OR_SORT = 17
Q_NEXT = 22

N_NAME = 1
N_SPAWNS = 7
N_WAYPOINTS = 8
N_ZONE = 9
N_QUEST_STARTS = 10
N_QUEST_ENDS = 11
N_FACTION = 13
N_SUBNAME = 14

O_NAME = 1
O_SPAWNS = 4

I_NAME = 1
I_NPC_DROPS = 2
I_OBJECT_DROPS = 3


def values(table: Any) -> list[Any]:
    if not isinstance(table, dict):
        return []
    return [table[key] for key in sorted((key for key in table if isinstance(key, int)))]


def first_text(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for item in values(value):
            found = first_text(item)
            if found:
                return found
    return None


def local_name(table: dict[Any, Any], entity_id: int, fallback: str) -> str:
    value = table.get(entity_id)
    if isinstance(value, str) and value:
        return value
    if isinstance(value, dict):
        localized = value.get(1)
        if isinstance(localized, str) and localized:
            return localized
    return fallback


def local_subname(table: dict[Any, Any], entity_id: int, fallback: str | None) -> str | None:
    value = table.get(entity_id)
    if isinstance(value, dict):
        localized = value.get(2)
        if isinstance(localized, str) and localized:
            return localized
    return fallback


def entity_refs(raw: Any) -> dict[str, list[int]]:
    """Decode Questie's startedBy / finishedBy {npc, object, item} compact structure."""
    if not isinstance(raw, dict):
        return {"npcs": [], "objects": [], "items": []}

    def ids_at(slot: int) -> list[int]:
        return [int(v) for v in values(raw.get(slot)) if isinstance(v, (int, float))]

    return {
        "npcs": ids_at(1),
        "objects": ids_at(2),
        "items": ids_at(3),
    }


def id_list(raw: Any) -> list[int]:
    return [int(v) for v in values(raw) if isinstance(v, (int, float))]


def trigger_end_payload(raw: Any) -> dict[str, Any] | None:
    """Decode Questie's triggerEnd {text, {zoneID={{x,y},...}}} structure."""
    if not isinstance(raw, dict):
        return None
    text = raw.get(1) if isinstance(raw.get(1), str) else None
    by_zone = raw.get(2)
    points_by_zone: dict[str, list[list[float]]] = {}
    if isinstance(by_zone, dict):
        for zone_id, rows in by_zone.items():
            if not isinstance(zone_id, (int, float)) or not isinstance(rows, dict):
                continue
            points: list[list[float]] = []
            for coords in values(rows):
                if not isinstance(coords, dict):
                    continue
                x, y = coords.get(1), coords.get(2)
                if isinstance(x, (int, float)) and isinstance(y, (int, float)) and x >= 0 and y >= 0:
                    points.append([float(x), float(y)])
            if points:
                points_by_zone[str(int(zone_id))] = points
    if not text and not points_by_zone:
        return None
    return {"text": text, "points_by_zone": points_by_zone}


def quest_objective_refs(raw: Any) -> dict[str, list[int]]:
    """Decode Questie's direct creature/object/item objective IDs from quest field 10."""
    if not isinstance(raw, dict):
        return {"creatures": [], "objects": [], "items": []}

    def objective_ids(slot: int) -> list[int]:
        found: list[int] = []
        for entry in values(raw.get(slot)):
            if not isinstance(entry, dict):
                continue
            entity_id = entry.get(1)
            if isinstance(entity_id, (int, float)):
                found.append(int(entity_id))
        return found

    return {
        "creatures": objective_ids(1),
        "objects": objective_ids(2),
        "items": objective_ids(3),
    }


def entity_label(questie: QuestieData, kind: str, entity_id: int) -> str:
    if kind == "npcs":
        raw = questie.npcs.get(entity_id, {})
        fallback = raw.get(N_NAME, f"NPC {entity_id}") if isinstance(raw, dict) else f"NPC {entity_id}"
        return local_name(questie.npc_names, entity_id, str(fallback))
    if kind == "objects":
        raw = questie.objects.get(entity_id, {})
        fallback = raw.get(1, f"Object {entity_id}") if isinstance(raw, dict) else f"Object {entity_id}"
        return local_name(questie.object_names, entity_id, str(fallback))
    raw = questie.items.get(entity_id, {})
    fallback = raw.get(1, f"Item {entity_id}") if isinstance(raw, dict) else f"Item {entity_id}"
    return local_name(questie.item_names, entity_id, str(fallback))


def quest_payload(questie: QuestieData, quest_id: int) -> dict[str, Any]:
    raw = questie.quests.get(quest_id)
    if not isinstance(raw, dict):
        return {
            "id": quest_id,
            "name": f"任务 {quest_id}",
            "missing": True,
        }

    fallback_name = raw.get(Q_NAME, f"任务 {quest_id}")
    localized = questie.quest_names.get(quest_id)
    objective_zh = None
    if isinstance(localized, dict):
        objective_zh = first_text(localized.get(2))
    objective = objective_zh or first_text(raw.get(Q_OBJECTIVE_TEXT))

    started = entity_refs(raw.get(Q_STARTED_BY))
    finished = entity_refs(raw.get(Q_FINISHED_BY))
    objective_refs = quest_objective_refs(raw.get(Q_OBJECTIVES))
    trigger_end = trigger_end_payload(raw.get(Q_TRIGGER_END))

    def refs_with_names(refs: dict[str, list[int]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        labels = {"npcs": "NPC", "objects": "物体", "items": "物品"}
        for kind in ("npcs", "objects", "items"):
            for entity_id in refs[kind]:
                rows.append(
                    {
                        "kind": kind,
                        "kind_label": labels[kind],
                        "id": entity_id,
                        "name": entity_label(questie, kind, entity_id),
                    }
                )
        return rows

    pre_single = id_list(raw.get(Q_PRE_SINGLE))
    pre_group = id_list(raw.get(Q_PRE_GROUP))
    prereq = sorted(set(pre_single + pre_group))
    next_id = raw.get(Q_NEXT)
    if not isinstance(next_id, (int, float)):
        next_id = None

    return {
        "id": quest_id,
        "name": local_name(questie.quest_names, quest_id, str(fallback_name)),
        "required_level": raw.get(Q_REQUIRED_LEVEL),
        "quest_level": raw.get(Q_QUEST_LEVEL),
        "zone_or_sort": raw.get(Q_ZONE_OR_SORT),
        "objective": objective,
        "started_by": refs_with_names(started),
        "finished_by": refs_with_names(finished),
        "objective_refs": objective_refs,
        "trigger_end": trigger_end,
        "pre_quest_single": pre_single,
        "pre_quest_group": pre_group,
        "prerequisite_ids": prereq,
        "next_quest_id": int(next_id) if next_id is not None else None,
        "missing": False,
    }


def npc_spawn_points(raw: dict[Any, Any], zone_id: int) -> list[list[float]]:
    spawns = raw.get(N_SPAWNS)
    if not isinstance(spawns, dict):
        return []
    zone_spawns = spawns.get(zone_id)
    points: list[list[float]] = []
    for coords in values(zone_spawns):
        if not isinstance(coords, dict):
            continue
        x = coords.get(1)
        y = coords.get(2)
        if isinstance(x, (int, float)) and isinstance(y, (int, float)) and x >= 0 and y >= 0:
            points.append([float(x), float(y)])
    return points


def npc_waypoints(raw: dict[Any, Any], zone_id: int) -> list[list[float]]:
    waypoints = raw.get(N_WAYPOINTS)
    if not isinstance(waypoints, dict):
        return []
    raw_zone = waypoints.get(zone_id)
    points: list[list[float]] = []

    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        x = node.get(1)
        y = node.get(2)
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            if x >= 0 and y >= 0:
                points.append([float(x), float(y)])
            return
        for child in values(node):
            walk(child)

    walk(raw_zone)
    return points


def object_spawn_points(raw: dict[Any, Any], zone_id: int) -> list[list[float]]:
    spawns = raw.get(O_SPAWNS)
    if not isinstance(spawns, dict):
        return []
    points: list[list[float]] = []
    for coords in values(spawns.get(zone_id)):
        if not isinstance(coords, dict):
            continue
        x = coords.get(1)
        y = coords.get(2)
        if isinstance(x, (int, float)) and isinstance(y, (int, float)) and x >= 0 and y >= 0:
            points.append([float(x), float(y)])
    return points


def build_objective_targets(questie: QuestieData, quest: dict[str, Any], zone_id: int) -> list[dict[str, Any]]:
    refs = quest.get("objective_refs") or {}
    targets: list[dict[str, Any]] = []

    def add_target(kind: str, entity_id: int, name: str, points: list[list[float]], source_item_id: int | None = None) -> None:
        targets.append(
            {
                "kind": kind,
                "entity_id": entity_id,
                "name": name,
                "spawns": points,
                "source_item_id": source_item_id,
                "source_item_name": entity_label(questie, "items", source_item_id) if source_item_id else None,
            }
        )

    for npc_id in refs.get("creatures", []):
        raw = questie.npcs.get(npc_id)
        if not isinstance(raw, dict):
            continue
        add_target(
            "creature",
            npc_id,
            local_name(questie.npc_names, npc_id, str(raw.get(N_NAME, npc_id))),
            npc_spawn_points(raw, zone_id),
        )

    for object_id in refs.get("objects", []):
        raw = questie.objects.get(object_id)
        if not isinstance(raw, dict):
            continue
        add_target(
            "object",
            object_id,
            local_name(questie.object_names, object_id, str(raw.get(O_NAME, object_id))),
            object_spawn_points(raw, zone_id),
        )

    trigger_end = quest.get("trigger_end")
    if isinstance(trigger_end, dict):
        points = (trigger_end.get("points_by_zone") or {}).get(str(zone_id)) or []
        if points:
            add_target(
                "trigger",
                -int(quest["id"]),
                str(trigger_end.get("text") or "探索/触发点"),
                points,
            )

    seen_item_sources: set[tuple[str, int, int]] = set()
    for item_id in refs.get("items", []):
        raw_item = questie.items.get(item_id)
        if not isinstance(raw_item, dict):
            continue
        for npc_id in id_list(raw_item.get(I_NPC_DROPS)):
            key = ("item_npc", item_id, npc_id)
            if key in seen_item_sources:
                continue
            seen_item_sources.add(key)
            raw = questie.npcs.get(npc_id)
            if not isinstance(raw, dict):
                continue
            add_target(
                "item_npc",
                npc_id,
                local_name(questie.npc_names, npc_id, str(raw.get(N_NAME, npc_id))),
                npc_spawn_points(raw, zone_id),
                source_item_id=item_id,
            )
        for object_id in id_list(raw_item.get(I_OBJECT_DROPS)):
            key = ("item_object", item_id, object_id)
            if key in seen_item_sources:
                continue
            seen_item_sources.add(key)
            raw = questie.objects.get(object_id)
            if not isinstance(raw, dict):
                continue
            add_target(
                "item_object",
                object_id,
                local_name(questie.object_names, object_id, str(raw.get(O_NAME, object_id))),
                object_spawn_points(raw, zone_id),
                source_item_id=item_id,
            )

    return targets


def build_zone_data(questie: QuestieData, zone_id: int) -> dict[str, Any]:
    npcs: list[dict[str, Any]] = []
    quest_ids: set[int] = set()

    for npc_id, raw in questie.npcs.items():
        if not isinstance(npc_id, int) or not isinstance(raw, dict):
            continue
        points = npc_spawn_points(raw, zone_id)
        starts = id_list(raw.get(N_QUEST_STARTS))
        if not points or not starts:
            continue

        faction = raw.get(N_FACTION)
        # This first Route Atlas is for the Horde paladin route: keep Horde and neutral/both-faction NPCs.
        if faction not in ("H", "AH", None):
            continue

        ends = id_list(raw.get(N_QUEST_ENDS))
        quest_ids.update(starts)
        quest_ids.update(ends)
        name = local_name(questie.npc_names, npc_id, str(raw.get(N_NAME, npc_id)))
        subname = local_subname(questie.npc_names, npc_id, raw.get(N_SUBNAME))
        npcs.append(
            {
                "id": npc_id,
                "name": name,
                "subname": subname,
                "faction": faction or "unknown",
                "zone_id": raw.get(N_ZONE),
                "spawns": points,
                "waypoints": npc_waypoints(raw, zone_id),
                "quest_starts": starts,
                "quest_ends": ends,
            }
        )

    quests = {str(quest_id): quest_payload(questie, quest_id) for quest_id in sorted(quest_ids)}

    # Add chain-adjacent quests so prerequisite/next links in the detail pane have names even if started elsewhere.
    adjacent: set[int] = set()
    for row in quests.values():
        adjacent.update(row.get("prerequisite_ids") or [])
        next_id = row.get("next_quest_id")
        if next_id:
            adjacent.add(next_id)
    for quest_id in sorted(adjacent):
        quests.setdefault(str(quest_id), quest_payload(questie, quest_id))

    for row in quests.values():
        if not row.get("missing"):
            row["objective_targets"] = build_objective_targets(questie, row, zone_id)

    npcs.sort(key=lambda row: (row["spawns"][0][0], row["spawns"][0][1], row["id"]))
    return {
        "meta": {
            "zone_id": zone_id,
            "zone_name": ZONE_NAME,
            "questie_version": questie.version,
            "questie_sha256": questie.source_sha256,
            "source_layer": "WotLK base tables from the supplied Questie package; Titan effective resolver is still a separate pending layer",
            "coordinate_space": "Questie zone-local x/y percentages, 0..100",
            "faction_scope": "Horde + neutral/both-faction quest-start NPCs",
        },
        "npcs": npcs,
        "quests": quests,
    }


def build_exact_route_circles(first_run: dict[str, Any]) -> dict[str, Any]:
    route = [row for row in first_run.get("incumbent", {}).get("route", []) if "x" in row and "y" in row]
    stops: list[dict[str, Any]] = []
    for action in route:
        x = float(action["x"])
        y = float(action["y"])
        key = (round(x, 4), round(y, 4))
        compact_action = {
            "type": action.get("type"),
            "name": action.get("name"),
            "quest_ids": list(action.get("quest_ids") or []),
            "position": action.get("position"),
            "travel_seconds": float(action.get("travel_seconds") or 0.0),
            "service_seconds": float(action.get("service_seconds") or 0.0),
        }
        if stops and stops[-1]["key"] == key:
            stops[-1]["actions"].append(compact_action)
            stops[-1]["seconds"] += compact_action["travel_seconds"] + compact_action["service_seconds"]
        else:
            stops.append({
                "key": key,
                "x": x,
                "y": y,
                "actions": [compact_action],
                "seconds": compact_action["travel_seconds"] + compact_action["service_seconds"],
            })

    def ghost(stop: dict[str, Any]) -> dict[str, Any]:
        return {"key": stop["key"], "x": stop["x"], "y": stop["y"], "actions": [], "seconds": 0.0}

    raw_circles: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    seen: set[tuple[float, float]] = set()
    for stop in stops:
        key = stop["key"]
        if not current:
            current = [stop]
            seen = {key}
            continue
        if key in seen:
            if key == current[0]["key"]:
                current.append(stop)
                raw_circles.append(current)
                current = [ghost(stop)]
                seen = {key}
            else:
                previous = current[-1]
                raw_circles.append(current)
                current = [ghost(previous), stop]
                seen = {previous["key"], key}
        else:
            current.append(stop)
            seen.add(key)
    if len(current) > 1:
        raw_circles.append(current)

    circles = []
    for index, circle in enumerate(raw_circles, start=1):
        real_actions = [action for stop in circle for action in stop["actions"]]
        first_name = next((str(a.get("name")) for a in real_actions if a.get("name")), "开始")
        last_name = next((str(a.get("name")) for a in reversed(real_actions) if a.get("name")), "结束")
        estimated_seconds = sum(float(stop.get("seconds") or 0.0) for stop in circle)
        circles.append({
            "id": index,
            "title": f"第{index}圈",
            "summary": f"{len(circle)}个真实停靠点 · {first_name} → {last_name}",
            "estimated_seconds": estimated_seconds,
            "points": [
                {
                    "x": float(stop["x"]),
                    "y": float(stop["y"]),
                    "actions": stop["actions"],
                }
                for stop in circle
            ],
        })

    total_seconds = sum(float(circle["estimated_seconds"]) for circle in circles)
    return {
        "version": "exact-display-circles-v1",
        "rule": "Built directly from the current incumbent action x/y coordinates. Consecutive identical coordinates are merged. A new display circle starts before a non-start coordinate would repeat within the same circle.",
        "total_estimated_seconds": total_seconds,
        "circles": circles,
    }


def html_document(data: dict[str, Any], map_relative_path: str, image_source: str) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    meta = data["meta"]
    safe_map = html.escape(map_relative_path, quote=True)
    safe_source = html.escape(image_source)
    title = f"{ZONE_NAME} · Route Atlas 点位验证"
    backText = "{backText}"  # Preserve the inner JavaScript template placeholder through this Python f-string.

    return f"""<!doctype html>
<html lang=\"zh-CN\">
<head>
<meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>{title}</title>
<style>
:root {{
  color-scheme: dark;
  --bg: #0c0f13;
  --panel: #131820;
  --panel-2: #191f28;
  --line: #2a3440;
  --text: #e9eef5;
  --muted: #94a2b3;
  --accent: #72d1a8;
  --horde: #ff786e;
  --neutral: #f1cd63;
  --selected: #f7f9fb;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 14px/1.55 -apple-system,BlinkMacSystemFont,\"Segoe UI\",\"PingFang SC\",\"Microsoft YaHei\",sans-serif; }}
header {{ min-height: 68px; display:flex; align-items:center; gap:18px; padding:12px 18px; border-bottom:1px solid var(--line); background:#10141a; position:sticky; top:0; z-index:20; }}
header h1 {{ font-size:18px; margin:0; white-space:nowrap; }}
.meta {{ color:var(--muted); font-size:12px; white-space:nowrap; }}
.toolbar {{ margin-left:auto; display:flex; align-items:center; gap:12px; flex-wrap:wrap; justify-content:flex-end; }}
.toolbar label {{ display:flex; align-items:center; gap:6px; color:#c9d3df; white-space:nowrap; }}
.toolbar input[type=\"search\"] {{ width:220px; background:#0b0e12; color:var(--text); border:1px solid var(--line); border-radius:8px; padding:8px 10px; outline:none; }}
.toolbar input[type=\"range\"] {{ width:90px; }}
.layout {{ display:block; min-height:calc(100vh - 69px); background:#080a0d; }}
.map-pane {{ min-width:0; background:#080a0d; display:flex; flex-direction:column; align-items:center; padding:18px; }}
.circle-summary {{ width:min(100%,1500px); margin:0 0 12px; padding:12px 14px; border:1px solid var(--line); border-radius:10px; background:#111720; display:flex; align-items:flex-start; gap:18px; }}
.circle-summary-main {{ flex:1; min-width:0; }}
.circle-summary-title {{ font-size:16px; font-weight:780; color:#fff0ac; }}
.circle-summary-text {{ color:#c1ccd8; margin-top:3px; }}
.circle-summary-time {{ white-space:nowrap; text-align:right; color:#aeb9c5; }}
.circle-summary-time strong {{ display:block; color:#ffd36a; font-size:18px; }}
.map-viewport {{ position:relative; width:min(100%,1500px); height:clamp(420px,74vh,900px); overflow:hidden; border:1px solid var(--line); border-radius:12px; background:#05070a; box-shadow:0 18px 60px rgba(0,0,0,.45); }}
.map-wrap {{ position:absolute; left:0; top:0; width:1887px; height:1259px; transform-origin:0 0; user-select:none; will-change:transform; transition:transform .24s cubic-bezier(.2,.7,.2,1); }}
.map-wrap img {{ width:100%; height:100%; display:block; object-fit:fill; }}
.view-controls {{ position:absolute; top:12px; right:12px; z-index:15; display:flex; gap:6px; padding:5px; border:1px solid rgba(255,255,255,.12); border-radius:9px; background:rgba(9,12,16,.86); box-shadow:0 6px 20px rgba(0,0,0,.28); backdrop-filter:blur(8px); }}
.view-btn {{ border:1px solid #3a4654; background:#171d25; color:#dbe4ee; border-radius:6px; padding:6px 10px; cursor:pointer; font-weight:700; }}
.view-btn:hover {{ border-color:#ffd36a; }}
.view-btn.active {{ background:#ffd36a; color:#151515; border-color:#ffd36a; }}
.overlay {{ position:absolute; inset:0; }}
.grid {{ position:absolute; inset:0; pointer-events:none; opacity:0; background-image:linear-gradient(to right,rgba(255,255,255,.18) 1px,transparent 1px),linear-gradient(to bottom,rgba(255,255,255,.18) 1px,transparent 1px); background-size:10% 10%; transition:opacity .15s; }}
.grid.show {{ opacity:1; }}
.marker {{ position:absolute; width:var(--marker-size,14px); height:var(--marker-size,14px); transform:translate(-50%,-50%); border-radius:50%; border:2px solid rgba(8,10,13,.92); padding:0; cursor:pointer; box-shadow:0 0 0 1px rgba(255,255,255,.28),0 2px 8px rgba(0,0,0,.6); z-index:3; }}
.marker.horde {{ background:var(--horde); }}
.marker.neutral {{ background:var(--neutral); }}
.marker:hover {{ z-index:8; box-shadow:0 0 0 3px rgba(255,255,255,.85),0 2px 10px rgba(0,0,0,.7); }}
.marker.selected {{ background:var(--selected); z-index:9; box-shadow:0 0 0 4px rgba(114,209,168,.95),0 2px 10px rgba(0,0,0,.7); }}
.target-marker {{ position:absolute; width:8px; height:8px; transform:translate(-50%,-50%); border-radius:50%; background:#69c7ff; border:1px solid rgba(5,8,12,.85); pointer-events:auto; z-index:5; box-shadow:0 0 0 1px rgba(255,255,255,.24); }}
.target-marker.item-source {{ background:#bd8cff; }}
.target-marker.object-target {{ border-radius:2px; background:#6fe0c1; }}
.route-svg {{ position:absolute; inset:0; width:100%; height:100%; pointer-events:none; z-index:6; overflow:visible; }}
.route-line {{ fill:none; stroke:#ffd36a; stroke-width:3; opacity:.88; vector-effect:non-scaling-stroke; }}
.route-node {{ position:absolute; width:28px; height:28px; transform:translate(-50%,-50%); border-radius:50%; border:2px solid #1b1b16; background:#ffd36a; color:#151515; font-size:12px; font-weight:850; cursor:pointer; z-index:12; box-shadow:0 2px 9px rgba(0,0,0,.65),0 0 0 1px rgba(255,255,255,.28); }}
.route-node:hover,.route-node.selected {{ background:#fff0ac; box-shadow:0 0 0 4px rgba(255,211,106,.45),0 2px 10px rgba(0,0,0,.7); }}
.route-label {{ position:absolute; transform:translate(17px,-50%); pointer-events:none; white-space:nowrap; padding:3px 6px; border-radius:6px; color:#fff2c2; background:rgba(9,10,8,.9); border:1px solid rgba(255,211,106,.5); font-size:11px; font-weight:720; z-index:11; }}
.route-circle-nav {{ display:flex; align-items:center; gap:7px; flex-wrap:wrap; }}
.route-circle-buttons {{ display:flex; flex-wrap:wrap; gap:4px; }}
.circle-btn,.next-circle-btn {{ border:1px solid #3a4654; background:#171d25; color:#dbe4ee; border-radius:7px; padding:5px 9px; cursor:pointer; font-weight:750; }}
.circle-btn:hover,.next-circle-btn:hover {{ border-color:#ffd36a; }}
.circle-btn.active {{ background:#ffd36a; color:#151515; border-color:#ffd36a; }}
.next-circle-btn:disabled {{ opacity:.4; cursor:default; }}
.view-btn:focus-visible,.circle-btn:focus-visible,.next-circle-btn:focus-visible {{ outline:2px solid #fff0ac; outline-offset:2px; }}
.special-warning {{ margin:10px 0; padding:10px 11px; border-radius:9px; border:1px solid rgba(255,183,77,.65); background:rgba(92,53,9,.3); color:#ffe0a3; }}
.marker-label {{ position:absolute; transform:translate(9px,-50%); display:none; pointer-events:none; white-space:nowrap; padding:3px 6px; border-radius:5px; color:#fff; background:rgba(7,9,12,.92); border:1px solid rgba(255,255,255,.18); font-size:11px; font-weight:650; z-index:10; }}
.marker:hover + .marker-label, .marker-label.force {{ display:block; }}
.side {{ width:min(100%,1500px); margin:0 auto 30px; border:1px solid var(--line); border-radius:12px; background:var(--panel); overflow:visible; }}
.side-inner {{ padding:18px 20px 24px; }}
.empty {{ color:var(--muted); padding:30px 4px; }}
.eyebrow {{ color:var(--accent); font-size:11px; font-weight:750; letter-spacing:.08em; text-transform:uppercase; }}
.name {{ font-size:22px; font-weight:750; margin:2px 0 2px; }}
.subname {{ color:var(--muted); margin-bottom:10px; }}
.chips {{ display:flex; flex-wrap:wrap; gap:6px; margin:8px 0 14px; }}
.chip {{ padding:3px 7px; border-radius:999px; border:1px solid var(--line); background:var(--panel-2); color:#bac5d1; font-size:12px; }}
.coord {{ font-variant-numeric:tabular-nums; }}
.section {{ margin-top:20px; padding-top:16px; border-top:1px solid var(--line); }}
.section h2 {{ font-size:13px; margin:0 0 8px; color:#c9d3df; }}
.quest-list {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:8px; }}
.quest-btn {{ width:100%; text-align:left; border:1px solid var(--line); border-radius:9px; background:var(--panel-2); color:var(--text); padding:8px 9px; cursor:pointer; }}
.quest-btn:hover {{ border-color:#526173; background:#202834; }}
.quest-btn strong {{ display:block; font-size:13px; }}
.quest-btn small {{ color:var(--muted); }}
.quest-card {{ background:#0e1218; border:1px solid var(--line); border-radius:11px; padding:13px; }}
.quest-title {{ font-size:17px; font-weight:720; margin-bottom:6px; }}
.kv {{ display:grid; grid-template-columns:72px 1fr; gap:5px 8px; margin:8px 0; }}
.kv dt {{ color:var(--muted); }}
.kv dd {{ margin:0; }}
.objective {{ margin:10px 0; color:#d9e1ea; }}
.refs {{ color:#b8c3cf; font-size:12px; }}
.relation {{ margin-top:8px; padding:8px 9px; border-radius:8px; background:#151c24; }}
.relation b {{ color:#d8e5f2; }}
.relation button {{ border:0; background:transparent; color:#8fd9bc; padding:0 3px; cursor:pointer; font:inherit; }}
footer {{ color:#728093; font-size:11px; padding:18px 0 4px; }}
.hidden {{ display:none !important; }}
@media (max-width:1050px) {{ .layout {{ grid-template-columns:1fr; height:auto; }} .side {{ border-left:0; border-top:1px solid var(--line); min-height:420px; }} .map-pane {{ overflow:visible; }} header {{ position:static; }} }}
@media (max-width:640px) {{ .map-pane {{ padding:10px; }} .circle-summary {{ flex-direction:column; gap:8px; }} .circle-summary-time {{ text-align:left; }} .view-controls {{ top:8px; right:8px; }} }}
@media (prefers-reduced-motion:reduce) {{ .map-wrap {{ transition:none; }} }}
</style>
</head>
<body>
<header>
  <div>
    <h1>{title}</h1>
    <div class=\"meta\">Questie {html.escape(str(meta['questie_version']))} · zone {meta['zone_id']} · NPC坐标已验收 · 当前验证任务目标点云</div>
  </div>
  <div class=\"toolbar\">
    <label><input id=\"showNeutral\" type=\"checkbox\" checked>中立 NPC</label>
    <label><input id=\"showHorde\" type=\"checkbox\" checked>部落 NPC</label>
    <label><input id=\"levelingOnly\" type=\"checkbox\" checked>58–68练级任务</label>
    <label><input id=\"showLabels\" type=\"checkbox\">常显名称</label>
    <div class=\"route-circle-nav\"><span>路线</span><div id=\"routeCircleButtons\" class=\"route-circle-buttons\"></div><button id=\"nextCircle\" class=\"next-circle-btn\" type=\"button\">下一圈 →</button></div>
    <label><input id=\"showTargets\" type=\"checkbox\" checked>选中任务目标点</label>
    <label><input id=\"showGrid\" type=\"checkbox\">10%网格</label>
    <label>点位<input id=\"markerScale\" type=\"range\" min=\"9\" max=\"24\" value=\"14\"></label>
    <input id=\"search\" type=\"search\" placeholder=\"搜索 NPC / 任务名 / ID\">
  </div>
</header>
<div class=\"layout\">
  <main class=\"map-pane\">
    <div class=\"circle-summary\" id=\"circleSummary\"></div>
    <div class=\"map-viewport\" id=\"mapViewport\">
      <div class=\"view-controls\" aria-label=\"地图视图\">
        <button id=\"fitCircle\" class=\"view-btn active\" type=\"button\" aria-pressed=\"true\">适应本圈</button>
        <button id=\"showFullMap\" class=\"view-btn\" type=\"button\" aria-pressed=\"false\">全图</button>
      </div>
      <div class=\"map-wrap\" id=\"mapWrap\">
        <img id=\"mapImage\" src=\"{safe_map}\" alt=\"赞加沼泽地图\">
        <div class=\"grid\" id=\"grid\"></div>
        <div class=\"overlay\" id=\"overlay\"></div>
      </div>
    </div>
  </main>
  <aside class=\"side\"><div class=\"side-inner\" id=\"detail\"><div class=\"empty\">点击地图上的 NPC 点。<br><br>第一轮只看坐标是否和游戏里的 Questie 对齐：重点检查塞纳里奥庇护所、沼泽鼠岗哨、萨布拉金、孢子村几个相距较远的任务中心。</div></div></aside>
</div>
<script id=\"atlas-data\" type=\"application/json\">{payload}</script>
<script>
const DATA = JSON.parse(document.getElementById('atlas-data').textContent);
const overlay = document.getElementById('overlay');
const detail = document.getElementById('detail');
const controls = {{
  neutral: document.getElementById('showNeutral'),
  horde: document.getElementById('showHorde'),
  leveling: document.getElementById('levelingOnly'),
  labels: document.getElementById('showLabels'),
  circleButtons: document.getElementById('routeCircleButtons'),
  nextCircle: document.getElementById('nextCircle'),
  fitCircle: document.getElementById('fitCircle'),
  fullMap: document.getElementById('showFullMap'),
  mapViewport: document.getElementById('mapViewport'),
  mapWrap: document.getElementById('mapWrap'),
  mapImage: document.getElementById('mapImage'),
  targets: document.getElementById('showTargets'),
  grid: document.getElementById('showGrid'),
  scale: document.getElementById('markerScale'),
  search: document.getElementById('search'),
}};
let selectedNpcId = null;
let selectedQuestId = null;
const ROUTE_CIRCLES = DATA.exact_route_circles?.circles || [];
let selectedCircleId = ROUTE_CIRCLES.length ? Number(ROUTE_CIRCLES[0].id) : 0;
const MAP_WIDTH = 1887;
const MAP_HEIGHT = 1259;
let viewMode = 'circle';
let pendingFitFrame = 0;
function formatDuration(seconds) {{
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hours) return `${{hours}}小时${{String(minutes).padStart(2,'0')}}分`;
  return `${{minutes}}分${{String(secs).padStart(2,'0')}}秒`;
}}
function applyMapTransform(scale, centerX, centerY) {{
  const vw = controls.mapViewport.clientWidth;
  const vh = controls.mapViewport.clientHeight;
  if (!vw || !vh || !Number.isFinite(scale)) return;
  const scaledWidth = MAP_WIDTH * scale;
  const scaledHeight = MAP_HEIGHT * scale;
  const centeredX = vw / 2 - scale * centerX;
  const centeredY = vh / 2 - scale * centerY;
  const tx = scaledWidth >= vw ? Math.min(0, Math.max(vw - scaledWidth, centeredX)) : (vw - scaledWidth) / 2;
  const ty = scaledHeight >= vh ? Math.min(0, Math.max(vh - scaledHeight, centeredY)) : (vh - scaledHeight) / 2;
  controls.mapWrap.style.transform = `translate(${{tx}}px, ${{ty}}px) scale(${{scale}})`;
}}
function updateViewButtons() {{
  const circleActive = viewMode === 'circle';
  controls.fitCircle.classList.toggle('active', circleActive);
  controls.fullMap.classList.toggle('active', !circleActive);
  controls.fitCircle.setAttribute('aria-pressed', String(circleActive));
  controls.fullMap.setAttribute('aria-pressed', String(!circleActive));
}}
function showFullMap() {{
  const vw = controls.mapViewport.clientWidth;
  const vh = controls.mapViewport.clientHeight;
  if (!vw || !vh) return;
  const scale = Math.min(vw / MAP_WIDTH, vh / MAP_HEIGHT);
  applyMapTransform(scale, MAP_WIDTH / 2, MAP_HEIGHT / 2);
}}
function fitCurrentCircle() {{
  const circle = ROUTE_CIRCLES.find(c => Number(c.id) === selectedCircleId);
  const points = circle?.points || [];
  if (!points.length) {{ showFullMap(); return; }}
  const xs = points.map(p => Number(p.x));
  const ys = points.map(p => Number(p.y));
  let minX = Math.min(...xs), maxX = Math.max(...xs);
  let minY = Math.min(...ys), maxY = Math.max(...ys);
  const spanX = Math.max(1, maxX - minX), spanY = Math.max(1, maxY - minY);
  const padX = Math.max(2.5, spanX * 0.12), padY = Math.max(2.5, spanY * 0.12);
  minX = Math.max(0, minX - padX); maxX = Math.min(100, maxX + padX);
  minY = Math.max(0, minY - padY); maxY = Math.min(100, maxY + padY);
  const cropW = Math.max(1, MAP_WIDTH * (maxX - minX) / 100);
  const cropH = Math.max(1, MAP_HEIGHT * (maxY - minY) / 100);
  const vw = controls.mapViewport.clientWidth;
  const vh = controls.mapViewport.clientHeight;
  if (!vw || !vh) return;
  const scale = Math.min(8, Math.min(vw / cropW, vh / cropH) * 0.96);
  const cx = MAP_WIDTH * (minX + maxX) / 200;
  const cy = MAP_HEIGHT * (minY + maxY) / 200;
  applyMapTransform(scale, cx, cy);
}}
function scheduleViewFit() {{
  cancelAnimationFrame(pendingFitFrame);
  pendingFitFrame = requestAnimationFrame(() => {{
    pendingFitFrame = requestAnimationFrame(() => {{
      if (viewMode === 'full') showFullMap();
      else fitCurrentCircle();
    }});
  }});
}}
function useCircleView() {{
  viewMode = 'circle';
  updateViewButtons();
  scheduleViewFit();
}}
function useFullMapView() {{
  viewMode = 'full';
  updateViewButtons();
  scheduleViewFit();
}}
function renderCircleSummary() {{
  const circle = ROUTE_CIRCLES.find(c => Number(c.id) === selectedCircleId);
  const box = document.getElementById('circleSummary');
  if (!circle) {{ box.innerHTML = ''; return; }}
  const total = DATA.exact_route_circles?.total_estimated_seconds || 0;
  box.innerHTML = `<div class=\"circle-summary-main\"><div class=\"circle-summary-title\">${{esc(circle.title)}}</div><div class=\"circle-summary-text\">${{esc(circle.summary || '')}}</div></div><div class=\"circle-summary-time\"><strong>${{formatDuration(circle.estimated_seconds)}}</strong>本圈预计 · 全图 ${{formatDuration(total)}}</div>`;
}}
function renderCircleButtons() {{
  controls.circleButtons.innerHTML = ROUTE_CIRCLES.map(c => `<button type=\"button\" class=\"circle-btn${{Number(c.id) === selectedCircleId ? ' active' : ''}}\" data-circle=\"${{c.id}}\">${{c.id}}</button>`).join('');
  controls.circleButtons.querySelectorAll('[data-circle]').forEach(btn => btn.addEventListener('click', () => {{
    selectedCircleId = Number(btn.dataset.circle);
    renderCircleButtons();
    renderCircleSummary();
    renderMarkers();
    useCircleView();
  }}));
  const lastId = ROUTE_CIRCLES.length ? Number(ROUTE_CIRCLES[ROUTE_CIRCLES.length - 1].id) : 0;
  controls.nextCircle.disabled = !ROUTE_CIRCLES.length || selectedCircleId === lastId;
}}

function esc(value) {{
  return String(value ?? '').replace(/[&<>\"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}})[c]);
}}
function quest(qid) {{ return DATA.quests[String(qid)]; }}
function questIsLeveling(qid) {{
  const q = quest(qid);
  if (!q || q.missing) return false;
  const ql = Number(q.quest_level);
  const rl = Number(q.required_level);
  return Number.isFinite(ql) && ql >= 58 && ql <= 68 && Number.isFinite(rl) && rl <= 68;
}}
function npcIsLeveling(npc) {{ return npc.quest_starts.some(questIsLeveling); }}
function npcMatches(npc, term) {{
  if (!term) return true;
  term = term.toLowerCase();
  if (String(npc.id).includes(term) || npc.name.toLowerCase().includes(term) || String(npc.subname || '').toLowerCase().includes(term)) return true;
  return npc.quest_starts.concat(npc.quest_ends).some(qid => {{
    const q = quest(qid); return String(qid).includes(term) || (q && q.name.toLowerCase().includes(term));
  }});
}}
function npcVisible(npc) {{
  if (npc.faction === 'H' && !controls.horde.checked) return false;
  if (npc.faction !== 'H' && !controls.neutral.checked) return false;
  if (controls.leveling.checked && !npcIsLeveling(npc)) return false;
  return npcMatches(npc, controls.search.value.trim());
}}
function specialMechanismWarnings(qids) {{
  const rows = [];
  for (const qid of qids || []) {{
    const q = quest(qid);
    const s = q?.special_mechanism;
    if (!s || s.route_anchor !== 'mechanism_entry') continue;
    rows.push({{qid, quest_name:q.name, ...s}});
  }}
  return rows;
}}
function renderRouteLayer() {{
  const circle = ROUTE_CIRCLES.find(c => Number(c.id) === selectedCircleId);
  const points = circle?.points || [];
  if (points.length < 2) return;
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('class', 'route-svg');
  svg.setAttribute('viewBox', '0 0 100 100');
  svg.setAttribute('preserveAspectRatio', 'none');
  const defs = document.createElementNS(ns, 'defs');
  const marker = document.createElementNS(ns, 'marker');
  const arrowSize = 8 / 3;
  const arrowMid = arrowSize / 2;
  marker.setAttribute('id', 'routeArrow');
  marker.setAttribute('markerWidth', String(arrowSize));
  marker.setAttribute('markerHeight', String(arrowSize));
  marker.setAttribute('refX', String(arrowSize * 6 / 7));
  marker.setAttribute('refY', String(arrowMid));
  marker.setAttribute('orient', 'auto');
  marker.setAttribute('markerUnits', 'strokeWidth');
  const arrow = document.createElementNS(ns, 'path');
  arrow.setAttribute('d', `M0,0 L${{arrowSize}},${{arrowMid}} L0,${{arrowSize}} z`);
  arrow.setAttribute('fill', '#ffd36a');
  marker.appendChild(arrow);
  defs.appendChild(marker);
  svg.appendChild(defs);
  for (let i=0; i<points.length-1; i++) {{
    const a = points[i], b = points[i+1];
    const line = document.createElementNS(ns, 'line');
    line.setAttribute('class', 'route-line');
    line.setAttribute('x1', a.x); line.setAttribute('y1', a.y);
    line.setAttribute('x2', b.x); line.setAttribute('y2', b.y);
    line.setAttribute('marker-end', 'url(#routeArrow)');
    svg.appendChild(line);
  }}
  overlay.appendChild(svg);
}}
function routeActionGroup(title, ids) {{
  if (!ids || !ids.length) return '';
  return `<div class=\"section\"><h2>${{esc(title)}}</h2><div class=\"quest-list\">${{ids.map(qid => questButton(qid)).join('')}}</div></div>`;
}}
function showRouteNode(id) {{
  selectedRouteNodeId = id;
  selectedNpcId = null;
  selectedQuestId = null;
  renderMarkers();
  const node = (DATA.macro_route?.nodes || []).find(n => n.id === id);
  if (!node) return;
  const warnings = specialMechanismWarnings(node.quest_ids);
  const warningHtml = warnings.map(s => `<div class=\"special-warning\"><b>⚠ 特殊机制 · ${{esc(s.quest_name)}}：</b>${{esc(s.warning || '实际执行入口与普通目标点不同')}}${{s.entry?.name ? `<br><span class=\"refs\">实际入口：${{esc(s.entry.name)}}</span>` : ''}}</div>`).join('');
  const actionHtml = routeActionGroup('接任务', node.actions?.accept) + routeActionGroup('做任务', node.actions?.do) + routeActionGroup('交任务', node.actions?.turnin);
  detail.innerHTML = `
    <div class=\"eyebrow\">Route Atlas 宏观路线</div>
    <div class=\"name\">${{node.id}}. ${{esc(node.title)}}</div>
    <div class=\"chips\"><span class=\"chip\">${{esc(node.short_action)}}</span><span class=\"chip coord\">${{node.point[0].toFixed(1)}}, ${{node.point[1].toFixed(1)}}</span><span class=\"chip\">任务 ${{node.quest_ids.length}} 个</span></div>
    <div class=\"relation\">${{esc(node.note || '')}}</div>
    ${{warningHtml}}
    ${{actionHtml || `<div class=\"section\"><h2>本段任务</h2><div class=\"quest-list\">${{node.quest_ids.map(qid => questButton(qid)).join('')}}</div></div>`}}
    <footer>主图只表达宏观方向；进入任务目标区域后继续以游戏内 Questie 点位为准。特殊机制任务例外：Route Atlas 应优先指向实际机制入口。</footer>`;
  bindQuestButtons();
}}
function renderMarkers() {{
  overlay.innerHTML = '';
  renderRouteLayer();
  const size = controls.scale.value + 'px';
  for (const npc of DATA.npcs) {{
    if (!npcVisible(npc)) continue;
    npc.spawns.forEach((xy, idx) => {{
      const marker = document.createElement('button');
      marker.className = 'marker ' + (npc.faction === 'H' ? 'horde' : 'neutral') + (npc.id === selectedNpcId ? ' selected' : '');
      marker.style.left = xy[0] + '%';
      marker.style.top = xy[1] + '%';
      marker.style.setProperty('--marker-size', size);
      marker.title = `${{npc.name}} · NPC ${{npc.id}} · ${{xy[0].toFixed(2)}}, ${{xy[1].toFixed(2)}}`;
      marker.setAttribute('aria-label', marker.title);
      marker.addEventListener('click', () => selectNpc(npc.id, idx));
      overlay.appendChild(marker);
      const label = document.createElement('span');
      label.className = 'marker-label' + (controls.labels.checked ? ' force' : '');
      label.style.left = xy[0] + '%';
      label.style.top = xy[1] + '%';
      label.textContent = npc.name;
      overlay.appendChild(label);
    }});
  }}
  if (controls.targets.checked && selectedQuestId) {{
    const q = quest(selectedQuestId);
    for (const target of (q?.objective_targets || [])) {{
      const targetClass = target.kind === 'object' ? ' object-target' : (target.kind.startsWith('item_') ? ' item-source' : '');
      for (const xy of (target.spawns || [])) {{
        const dot = document.createElement('span');
        dot.className = 'target-marker' + targetClass;
        dot.style.left = xy[0] + '%';
        dot.style.top = xy[1] + '%';
        const source = target.source_item_name ? ` · 来源物品：${{target.source_item_name}}` : '';
        dot.title = `${{target.name}} · ${{target.entity_id}}${{source}} · ${{xy[0].toFixed(2)}}, ${{xy[1].toFixed(2)}}`;
        overlay.appendChild(dot);
      }}
    }}
  }}
}}
function questButton(qid, prefix='') {{
  const q = quest(qid);
  if (!q) return '';
  const levels = q.missing ? '' : `需求 ${{q.required_level ?? '—'}} · 等级 ${{q.quest_level ?? '—'}}`;
  return `<button class=\"quest-btn\" data-qid=\"${{qid}}\"><strong>${{prefix}}${{esc(q.name)}}</strong><small>ID ${{qid}}${{levels ? ' · ' + levels : ''}}</small></button>`;
}}
function bindQuestButtons() {{
  detail.querySelectorAll('[data-qid]').forEach(btn => btn.addEventListener('click', () => showQuest(Number(btn.dataset.qid))));
  detail.querySelectorAll('[data-npcid]').forEach(btn => btn.addEventListener('click', () => selectNpc(Number(btn.dataset.npcid), 0)));
}}
function selectNpc(id, spawnIndex=0) {{
  if ((id === null || id === undefined) && selectedRouteNodeId) {{ showRouteNode(selectedRouteNodeId); return; }}
  selectedNpcId = id;
  selectedQuestId = null;
  selectedRouteNodeId = null;
  renderMarkers();
  const npc = DATA.npcs.find(n => n.id === id);
  if (!npc) return;
  const xy = npc.spawns[spawnIndex] || npc.spawns[0];
  const factionLabel = npc.faction === 'H' ? '部落' : '中立/双方';
  const starts = npc.quest_starts.filter(qid => !controls.leveling.checked || questIsLeveling(qid));
  const ends = npc.quest_ends.filter(qid => !controls.leveling.checked || questIsLeveling(qid));
  detail.innerHTML = `
    <div class=\"eyebrow\">Questie NPC</div>
    <div class=\"name\">${{esc(npc.name)}}</div>
    <div class=\"subname\">${{esc(npc.subname || '')}}</div>
    <div class=\"chips\"><span class=\"chip\">NPC ID ${{npc.id}}</span><span class=\"chip\">${{factionLabel}}</span><span class=\"chip coord\">${{xy[0].toFixed(2)}}, ${{xy[1].toFixed(2)}}</span></div>
    <div class=\"section\"><h2>此 NPC 可以开启以下任务</h2><div class=\"quest-list\">${{starts.length ? starts.map(id => questButton(id)).join('') : '<span class=\"refs\">当前筛选下无任务</span>'}}</div></div>
    <div class=\"section\"><h2>此 NPC 可以完成以下任务</h2><div class=\"quest-list\">${{ends.length ? ends.map(id => questButton(id)).join('') : '<span class=\"refs\">当前筛选下无任务</span>'}}</div></div>
    <footer>数据：用户提供的 Questie v${{esc(DATA.meta.questie_version)}} · 坐标直接使用 Questie zone-local 0–100 百分比。<br>底图来源：${{esc({json.dumps(image_source, ensure_ascii=False)})}}</footer>`;
  bindQuestButtons();
}}
function refsHtml(rows) {{
  if (!rows || !rows.length) return '—';
  return rows.map(r => r.kind === 'npcs' ? `<button data-npcid=\"${{r.id}}\">${{esc(r.name)}} (${{r.id}})</button>` : `${{esc(r.name)}} (${{r.id}})`).join('、');
}}
function relationQuestLinks(ids) {{
  const clean = [...new Set(ids)].filter(Boolean);
  return clean.length ? clean.map(id => `<button data-qid=\"${{id}}\">${{esc(quest(id)?.name || '任务 ' + id)}} (${{id}})</button>`).join('、') : '—';
}}
function sharedNpcRelations(qid, field) {{
  const hits = [];
  for (const npc of DATA.npcs) {{
    const list = field === 'start' ? npc.quest_starts : npc.quest_ends;
    if (list.includes(qid)) hits.push(...list.filter(id => id !== qid));
  }}
  return hits;
}}
function objectiveTargetSummary(q) {{
  const rows = (q.objective_targets || []).map(target => {{
    const kind = target.kind === 'creature' ? '目标怪' : target.kind === 'object' ? '目标物体' : target.kind === 'item_npc' ? '任务物掉落怪' : '任务物来源物体';
    const source = target.source_item_name ? ` → ${{esc(target.source_item_name)}}` : '';
    const local = (target.spawns || []).length ? `${{target.spawns.length}}个本图点位` : '本图无点位';
    return `<div class=\"relation\"><b>${{kind}}：</b>${{esc(target.name)}} (${{target.entity_id}})${{source}} · ${{local}}</div>`;
  }});
  return rows.length ? rows.join('') : '<span class=\"refs\">Questie没有可直接投影的怪物/Object目标；可能是触发、交谈、法术或其他特殊目标。</span>';
}}
function fmtSeconds(value) {{
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return '—';
  const sec = Math.max(0, Number(value));
  if (sec < 60) return `${{sec.toFixed(1)}}秒`;
  const min = Math.floor(sec / 60);
  const rest = Math.round(sec - min * 60);
  return rest ? `${{min}}分${{rest}}秒` : `${{min}}分钟`;
}}
function fmtTimeRange(lower, estimate, upper) {{
  if (estimate === null || estimate === undefined || !Number.isFinite(Number(estimate))) return '—';
  const lo = Number(lower), mid = Number(estimate), hi = Number(upper);
  if (Number.isFinite(lo) && Number.isFinite(hi) && (Math.abs(lo-mid) > 0.01 || Math.abs(hi-mid) > 0.01)) {{
    return `${{fmtSeconds(mid)}}（代理范围 ${{fmtSeconds(lo)}}–${{fmtSeconds(hi)}}）`;
  }}
  return fmtSeconds(mid);
}}
function profileSummary(q) {{
  const p = q.route_profile;
  if (!p) return '<span class=\"refs\">尚未生成本任务的 Route Atlas 基础标签。</span>';
  const typeLabels = {{
    handoff:'纯交接/跑腿', kill:'打怪', mob_drop:'怪物掉落物', object_interact_single:'固定物品交互',
    object_collect_multi:'多刷新物拾取', escort:'护送', explore_trigger:'探索/触发', spell_use:'技能/道具使用',
    reputation:'声望', mixed:'混合型', other:'其他',
    scripted_transport:'固定脚本移动', find_npc_handoff:'寻找NPC并交付', profession_object_collect:'专业采集任务',
    dungeon_item_turnin:'副本物品交付', dungeon_item_turnin_repeatable:'副本物品重复交付',
    ambient_inventory_turnin:'背景库存交付', ambient_inventory_turnin_repeatable:'背景库存重复交付',
    profession_specialization_quest:'专业专精任务', profession_handoff:'专业跑腿', seasonal_handoff:'节日跑腿',
    class_quest_handoff:'职业任务跑腿', class_quest_material_collection:'职业任务材料收集',
    class_quest_scripted_action:'职业任务脚本动作', class_quest_escort_defense:'职业任务护送/防守',
    class_quest_kill_or_drop:'职业任务击杀/掉落', class_quest_scripted_item:'职业任务特殊物品',
    class_quest_boss_kill:'职业任务Boss击杀', item_start_explore_trigger:'掉落物起始+探索',
    scripted_item_use:'固定点使用道具', item_start_mob_drop_handoff:'掉落物起始+交付',
    scripted_summon_kill:'使用道具召唤击杀', conditional_inventory_item_start:'条件库存起始任务',
    item_start_boss_drop_handoff:'Boss掉落起始+交付'
  }};
  const tags = (p.labels || []).map(tag => `<span class=\"chip\">${{esc(tag)}}</span>`).join('');
  const effectiveType = p.classification?.effective_primary || p.classification?.primary;
  const t = p.effective_time_estimate || p.solo_time_estimate;
  const timeRows = t ? `
    <div class=\"relation\"><b>接取→首个任务点：</b>${{fmtSeconds(t.travel_to_work_seconds)}}</div>
    <div class=\"relation\"><b>任务点之间移动：</b>${{fmtSeconds(t.work_internal_travel_seconds)}}</div>
    <div class=\"relation\"><b>目标执行时间：</b>${{fmtTimeRange(t.objective_seconds_lower, t.objective_seconds, t.objective_seconds_upper)}}</div>
    <div class=\"relation\"><b>最后任务点→提交：</b>${{fmtSeconds(t.work_to_turnin_seconds)}}</div>
    <div class=\"relation\"><b>单独完成总估算：</b>${{fmtTimeRange(t.estimated_total_seconds_lower, t.estimated_total_seconds, t.estimated_total_seconds_upper)}}</div>` : '<div class=\"relation\">当前类型尚不能完整估算单任务耗时。</div>';
  const componentRows = (p.components || []).map(c => {{
    let detail = `<div class=\"relation\"><b>${{esc(c.label || c.family)}}：</b>类型 ${{esc(typeLabels[c.family] || c.family)}} · 数量 ${{c.needed_count ?? '—'}} · 目标执行 ${{fmtSeconds(c.estimated_objective_seconds)}}</div>`;
    if (c.count_inference) {{
      detail += `<div class=\"relation\" style=\"padding-left:12px\">↳ 数量来源：${{esc(c.count_inference.source || '—')}} · 置信度 ${{esc(c.count_inference.confidence || '—')}}</div>`;
    }}
    if (c.family === 'mob_drop') {{
      detail += (c.sources || []).map(s => {{
        const shortcut = s.low_density_shortcut ? ' · <b>额外快捷来源</b>' : '';
        const totalNeed = s.calculations?.expected_kills?.inputs?.five_box_required_count;
        return `<div class=\"relation\" style=\"padding-left:12px\">↳ ${{esc(s.name)}} (${{s.entity_id}})：掉落率 ${{s.drop_rate_percent == null ? '—' : Number(s.drop_rate_percent).toFixed(2) + '%'}} · 五号总需求 ${{totalNeed ?? '—'}} · 公式 五号总需求÷掉率 = ${{s.expected_kills == null ? '—' : Number(s.expected_kills).toFixed(1)}}只期望击杀 · 按15秒/怪预计 ${{fmtSeconds(s.expected_service_seconds)}}${{shortcut}}</div>`;
      }}).join('');
    }} else if (c.family === 'object_collect_multi') {{
      const calc = c.calculation?.inputs || {{}};
      const ev = calc.respawn_evidence || {{}};
      const range = ev.min_seconds == null ? '' : ` · 来源范围 ${{fmtSeconds(ev.min_seconds)}}–${{fmtSeconds(ev.max_seconds)}}${{ev.uniform ? '（一致）' : '（按当前点估计规则取值）'}}`;
      detail += `<div class=\"relation\" style=\"padding-left:12px\">↳ 单号需求 ${{calc.per_character_required_count ?? '—'}} · 五号总需求 ${{calc.five_box_required_count ?? '—'}} · 唯一刷新点 ${{calc.unique_spawn_points ?? '—'}} · 共 ${{calc.rounds ?? '—'}} 轮 / 等待 ${{calc.wait_rounds ?? '—'}} 次 · 刷新输入 ${{fmtSeconds(calc.respawn_seconds)}} · 来源 ${{esc(calc.respawn_seconds_source || '—')}}${{range}} · 公式 刷新时间×(刷新轮数-1)</div>`;
    }} else if (c.family === 'kill') {{
      const source = c.baseline_source || {{}};
      detail += `<div class=\"relation\" style=\"padding-left:12px\">↳ 单怪估算 ${{fmtSeconds(source.single_kill_seconds)}} · 固定按15秒/怪计算</div>`;
    }}
    return detail;
  }}).join('');
  const startAcq = p.start_acquisition;
  const startAcqRows = startAcq ? `
    <div class=\"section\"><h2>起始物获取基础数据</h2>
      <div class=\"relation\"><b>起始物：</b>${{esc(startAcq.item_name || '—')}}${{startAcq.item_id ? ` (${{startAcq.item_id}})` : ''}}</div>
      <div class=\"relation\"><b>基准来源：</b>${{esc(startAcq.baseline_source_name || '—')}}${{startAcq.baseline_source_entity_id ? ` (${{startAcq.baseline_source_entity_id}})` : ''}} · 获取时间 ${{fmtSeconds(startAcq.baseline_acquisition_seconds)}}</div>
      ${{(startAcq.sources || []).map(s => `<div class=\"relation\" style=\"padding-left:12px\">↳ ${{esc(s.name)}} (${{s.entity_id ?? '—'}})：掉落率 ${{s.drop_rate_percent == null ? '—' : Number(s.drop_rate_percent).toFixed(2) + '%'}} · 期望击杀 ${{s.expected_kills == null ? '—' : Number(s.expected_kills).toFixed(1)}}只 · 获取耗时 ${{fmtSeconds(s.expected_service_seconds)}}${{s.expected_failure_wait_seconds == null ? '' : ` · 其中期望刷新等待 ${{fmtSeconds(s.expected_failure_wait_seconds)}}`}}</div>`).join('')}}
    </div>` : '';
  const manualNotes = (p.manual_override?.notes || []).map(n => `<div class=\"relation\">${{esc(n)}}</div>`).join('');
  const policy = p.route_policy || 'include';
  const confidence = p.classification?.confidence || '—';
  const effectiveFormula = t?.calculation?.formula || t?.calculations?.quest_total?.formula || '—';
  return `
    <div class=\"chips\"><span class=\"chip\">任务类型：${{esc(typeLabels[effectiveType] || effectiveType || '—')}}</span><span class=\"chip\">分类置信度：${{esc(confidence)}}</span><span class=\"chip\">路线策略：${{esc(policy)}}</span>${{tags}}</div>
    ${{timeRows}}
    <div class=\"relation\"><b>当前总耗时公式：</b>${{esc(effectiveFormula)}}</div>
    ${{startAcqRows}}
    ${{manualNotes ? `<div class=\"section\"><h2>人工覆盖 / 特殊说明</h2>${{manualNotes}}</div>` : ''}}
    <div class=\"section\"><h2>目标耗时基础数据</h2>${{componentRows || '<span class=\"refs\">无额外目标执行数据。</span>'}}</div>
    <div class=\"refs\">任务卡读取的是已落盘的计算结果；只有底层参数或规则改变并重建数据时结果才更新。移动暂按平面直线距离统一估算，后续可被实跑数据覆盖。</div>`;
}}
function sharedObjectiveRelations(qid) {{
  const currentQuest = quest(qid);
  const current = currentQuest?.objective_refs || {{}};
  const sets = {{
    creatures: new Set(current.creatures || []),
    objects: new Set(current.objects || []),
    items: new Set(current.items || []),
    resolvedNpcs: new Set((currentQuest?.objective_targets || []).filter(t => t.kind === 'creature' || t.kind === 'item_npc').map(t => t.entity_id)),
    resolvedObjects: new Set((currentQuest?.objective_targets || []).filter(t => t.kind === 'object' || t.kind === 'item_object').map(t => t.entity_id)),
  }};
  const result = {{creatures:[], objects:[], items:[], resolvedNpcs:[], resolvedObjects:[]}};
  for (const other of Object.values(DATA.quests)) {{
    if (!other || other.id === qid || other.missing) continue;
    const refs = other.objective_refs || {{}};
    for (const kind of ['creatures','objects','items']) {{
      if ((refs[kind] || []).some(id => sets[kind].has(id))) result[kind].push(other.id);
    }}
    const actualNpcs = (other.objective_targets || []).filter(t => t.kind === 'creature' || t.kind === 'item_npc').map(t => t.entity_id);
    const actualObjects = (other.objective_targets || []).filter(t => t.kind === 'object' || t.kind === 'item_object').map(t => t.entity_id);
    if (actualNpcs.some(id => sets.resolvedNpcs.has(id))) result.resolvedNpcs.push(other.id);
    if (actualObjects.some(id => sets.resolvedObjects.has(id))) result.resolvedObjects.push(other.id);
  }}
  return result;
}}
function showQuest(qid) {{
  const q = quest(qid);
  if (!q) return;
  selectedQuestId = qid;
  const sameStart = sharedNpcRelations(qid, 'start');
  const sameEnd = sharedNpcRelations(qid, 'end');
  const sameObjective = sharedObjectiveRelations(qid);
  const chain = [...(q.prerequisite_ids || []), q.next_quest_id].filter(Boolean);
  const special = q.special_mechanism;
  const specialHtml = special?.route_anchor === 'mechanism_entry' ? `<div class=\"special-warning\"><b>⚠ 特殊机制：</b>${{esc(special.warning || '实际执行入口与普通地图目标不同')}}${{special.entry?.name ? `<br><span class=\"refs\">实际入口：${{esc(special.entry.name)}}</span>` : ''}}</div>` : '';
  const backText = selectedRouteNodeId ? '← 返回路线节点' : '← 返回 NPC';
  renderMarkers();
  detail.innerHTML = `
    <button class=\"quest-btn\" id=\"backNpc\"><small>${backText}</small></button>
    <div class=\"section\" style=\"margin-top:12px;padding-top:0;border-top:0\">
      <div class=\"eyebrow\">Questie 单任务信息</div>
      <div class=\"quest-card\">
        <div class=\"quest-title\">${{esc(q.name)}}</div>
        <div class=\"chips\"><span class=\"chip\">任务 ID ${{q.id}}</span><span class=\"chip\">任务等级 ${{q.quest_level ?? '—'}}</span><span class=\"chip\">需要等级 ${{q.required_level ?? '—'}}</span></div>
        <dl class=\"kv\"><dt>接取</dt><dd class=\"refs\">${{refsHtml(q.started_by)}}</dd><dt>提交</dt><dd class=\"refs\">${{refsHtml(q.finished_by)}}</dd></dl>
        <div class=\"objective\">${{esc(q.objective || 'Questie 无目标文本')}}</div>
        <div class=\"section\"><h2>Questie 目标实体 / 点位来源</h2>${{objectiveTargetSummary(q)}}</div>
        <div class=\"section\"><h2>Route Atlas 基础标签 / 单任务耗时</h2>${{profileSummary(q)}}</div>
      </div>
    </div>
    <div class=\"section\"><h2>关联信息（独立于任务卡事实）</h2>
      <div class=\"relation\"><b>同接取 NPC：</b>${{relationQuestLinks(sameStart)}}</div>
      <div class=\"relation\"><b>同提交 NPC：</b>${{relationQuestLinks(sameEnd)}}</div>
      <div class=\"relation\"><b>相同直接目标怪：</b>${{relationQuestLinks(sameObjective.creatures)}}</div>
      <div class=\"relation\"><b>相同实际怪/掉落来源：</b>${{relationQuestLinks(sameObjective.resolvedNpcs)}}</div>
      <div class=\"relation\"><b>相同直接目标物体：</b>${{relationQuestLinks(sameObjective.objects)}}</div>
      <div class=\"relation\"><b>相同实际物体/来源：</b>${{relationQuestLinks(sameObjective.resolvedObjects)}}</div>
      <div class=\"relation\"><b>相同任务物品：</b>${{relationQuestLinks(sameObjective.items)}}</div>
      <div class=\"relation\"><b>直接链关系：</b>${{relationQuestLinks(chain)}}</div>
    </div>
    <footer>Questie事实与我们新增的关联信息保持分层。当前已加入同目标怪/物体/任务物品；下一步再基于点云计算距离、重叠和相邻区域关系。</footer>`;
  document.getElementById('backNpc').addEventListener('click', () => selectNpc(selectedNpcId, 0));
  bindQuestButtons();
}}
for (const key of ['neutral','horde','leveling','labels']) controls[key].addEventListener('change', () => {{ renderMarkers(); if (selectedNpcId && !selectedQuestId) selectNpc(selectedNpcId,0); }});
controls.nextCircle.addEventListener('click', () => {{
  const idx = ROUTE_CIRCLES.findIndex(c => Number(c.id) === selectedCircleId);
  if (idx >= 0 && idx < ROUTE_CIRCLES.length - 1) {{
    selectedCircleId = Number(ROUTE_CIRCLES[idx + 1].id);
    renderCircleButtons();
    renderCircleSummary();
    renderMarkers();
    useCircleView();
  }}
}});
controls.fitCircle.addEventListener('click', useCircleView);
controls.fullMap.addEventListener('click', useFullMapView);
controls.targets.addEventListener('change', renderMarkers);
controls.grid.addEventListener('change', () => document.getElementById('grid').classList.toggle('show', controls.grid.checked));
controls.scale.addEventListener('input', renderMarkers);
controls.search.addEventListener('input', renderMarkers);
renderCircleButtons();
renderCircleSummary();
renderMarkers();
updateViewButtons();
if (!controls.mapImage.complete) controls.mapImage.addEventListener('load', scheduleViewFit, {{once:true}});
scheduleViewFit();
window.addEventListener('resize', scheduleViewFit);
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the first Route Atlas offline Questie NPC-position prototype.")
    parser.add_argument("--questie", type=Path, default=DEFAULT_QUESTIE)
    parser.add_argument("--map", dest="map_path", type=Path, default=DEFAULT_MAP)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    args = parser.parse_args()

    questie = load_questie(args.questie)
    data = build_zone_data(questie, ZONE_ID)
    if DEFAULT_TASK_PROFILES.exists():
        profile_payload = json.loads(DEFAULT_TASK_PROFILES.read_text(encoding="utf-8"))
        profiles = profile_payload.get("quests", {})
        for qid, row in data["quests"].items():
            if qid in profiles:
                row["route_profile"] = profiles[qid]
        data["meta"]["task_profile_version"] = "zangarmarsh-task-profiles-v1"
    if DEFAULT_SPECIAL_MECHANISMS.exists():
        special_payload = json.loads(DEFAULT_SPECIAL_MECHANISMS.read_text(encoding="utf-8"))
        for qid, special in special_payload.get("quests", {}).items():
            if qid in data["quests"]:
                data["quests"][qid]["special_mechanism"] = special
        data["meta"]["special_mechanism_version"] = special_payload.get("meta", {}).get("version")
    if DEFAULT_FIRST_RUN.exists():
        first_run_payload = json.loads(DEFAULT_FIRST_RUN.read_text(encoding="utf-8"))
        data["exact_route_circles"] = build_exact_route_circles(first_run_payload)
        data["meta"]["exact_route_circle_version"] = data["exact_route_circles"]["version"]
    if DEFAULT_MACRO_ROUTE.exists():
        data["macro_route"] = json.loads(DEFAULT_MACRO_ROUTE.read_text(encoding="utf-8"))
        if DEFAULT_MACRO_ACTIONS.exists():
            action_groups = json.loads(DEFAULT_MACRO_ACTIONS.read_text(encoding="utf-8"))
            for node in data["macro_route"].get("nodes", []):
                node["actions"] = action_groups.get(str(node.get("id")), {"accept": [], "do": [], "turnin": []})
        node_by_id = {int(node["id"]): node for node in data["macro_route"].get("nodes", [])}
        circle_specs = [
            (1, "第1圈 · 东部开局环", "塞纳里奥庇护所/沼泽鼠岗哨接齐第一批任务，向东南和泻湖清理后回东部开后续；身上有9472时顺手买塞纳里奥烈酒。", 7740.5, [1, 2, 3, 4]),
            (2, "第2圈 · 东部转西部", "从东部沿蒸汽泵、阴冷之地、血鳞与水库入口一路向西，最终进入萨布拉金任务群。", 3724.3, [4, 5, 6, 7]),
            (3, "第3圈 · 西部第一环", "萨布拉金接齐西部任务，清孢子村/孢殖林与西北第一趟，再回萨布拉金开后续。", 4527.9, [7, 8, 9, 10]),
            (4, "第4圈 · 西北任务链", "完成安葛洛什与偷回蘑菇后回萨布拉金，开启最终西北链。", 1389.7, [10, 11, 12]),
            (5, "第5圈 · 西部回东部", "清西北最终目标与博哈姆/蛮沼任务，然后跨图回东部集中交付。", 2545.2, [12, 13, 14, 15]),
            (6, "第6圈 · 东北尤尔巴环", "从东部去东北找到尤尔巴、处理未完职责与枯萎区，再回东部。", 345.5, [15, 16, 15]),
            (7, "第7圈 · 东南观察者环", "从东部去东南完成保护观察者与拯救孢子人，再回东部。", 731.1, [15, 17, 15]),
            (8, "第8圈 · 最终西部收尾", "最后转西部完成泥爪及萨布拉金两条Boss收尾链。", 621.0, [15, 18]),
        ]
        data["route_circles"] = {
            "version": "display-circles-v1",
            "rule": "Only one circle is rendered at a time; no visual offsets; duplicate coordinates are allowed only when the first and last node are the same route anchor.",
            "total_estimated_seconds": 21625.196,
            "estimate_note": "Current first-run five-box materialized estimate; conservative for independent quest drops and intended to be replaced by actual run timing.",
            "circles": [
                {"id": cid, "title": title, "summary": summary, "estimated_seconds": estimated_seconds, "nodes": [dict(node_by_id[nid]) for nid in node_ids]}
                for cid, title, summary, estimated_seconds, node_ids in circle_specs
            ],
        }
        data["meta"]["macro_route_version"] = data["macro_route"].get("meta", {}).get("version")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)

    map_path = args.map_path.resolve()
    output_dir = args.output.resolve().parent
    map_relative = Path(__import__("os").path.relpath(map_path, output_dir)).as_posix()
    source = "The Ancient Gaming Noob / bc07_zangarmarsh.jpg (game map screenshot, downloaded 2026-08-13)"

    args.json_output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output.write_text(html_document(data, map_relative, source), encoding="utf-8")

    leveling_npcs = sum(1 for npc in data["npcs"] if any(
        58 <= (data["quests"].get(str(qid), {}).get("quest_level") or -999) <= 68
        and (data["quests"].get(str(qid), {}).get("required_level") or 999) <= 68
        for qid in npc["quest_starts"]
    ))
    print(f"Questie={questie.version} sha256={questie.source_sha256}")
    print(f"zone={ZONE_ID} npc_markers={len(data['npcs'])} leveling_npcs={leveling_npcs} quests={len(data['quests'])}")
    print(f"html={args.output}")
    print(f"json={args.json_output}")


if __name__ == "__main__":
    main()
