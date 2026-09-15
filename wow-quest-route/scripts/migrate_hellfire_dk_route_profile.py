from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_dk_outland_speed_routes import build_hellfire
from lib.route_profiles import ROUTE_PROFILES_DIR, validate_route_profile
from lib.task_cards import load_all_task_cards

WORKBENCH = ROOT / "data/route-atlas/workbench-routes.json"
OUTPUT = ROUTE_PROFILES_DIR / "hellfire-dk-speed.json"
TASK_RE = re.compile(r"《([^》]+)》")
PROFILE_ID = "hellfire-dk-speed"
GAME_VARIANT_ID = "timewalking-wotlk-cn"

SYSTEM_PREFIXES = {
    "开飞行点：": "open_flight_point",
    "绑定炉石：": "bind_hearth",
    "使用炉石：": "use_hearth",
    "系统飞行：": "taxi",
    "固定交通：": "fixed_transport",
    "任务传送：": "quest_transport",
}

# Existing route decisions that were previously hidden in free-text notes.
OPPORTUNITY_ACCEPTS = {
    "铸魔营地：暴虐": (10393, "燃烧军团信件"),
    "大裂隙": (9373, "被腐蚀的皮箱"),
}


def _load_current_route() -> dict[str, Any]:
    routes = json.loads(WORKBENCH.read_text(encoding="utf-8"))
    base = routes.get("hellfire")
    if not isinstance(base, dict):
        raise RuntimeError("base Hellfire workbench route is missing")
    return build_hellfire(base)


def _task_name_index(cards: dict[int, dict[str, Any]]) -> dict[str, int]:
    result: dict[str, int] = {}
    duplicates: dict[str, list[int]] = {}
    for task_id, card in cards.items():
        name = str(card["identity"]["name_zhcn"])
        if name in result:
            duplicates.setdefault(name, [result[name]]).append(task_id)
        else:
            result[name] = task_id
    if duplicates:
        raise RuntimeError(f"duplicate Task Card names require explicit migration identity: {duplicates}")
    return result


def _task_kind(line: str, task_start: int) -> str:
    prefix = line[:task_start]
    candidates = [
        (prefix.rfind("交"), "turnin"),
        (prefix.rfind("接"), "accept"),
        (prefix.rfind("做"), "objective"),
    ]
    position, kind = max(candidates, key=lambda item: item[0])
    if position < 0:
        raise RuntimeError(f"cannot infer task action from migration input: {line!r}")
    return kind


def _npc_name(line: str) -> str | None:
    stripped = line.strip()
    if stripped.startswith("↳") or "→" not in stripped:
        return None
    first = stripped.split("→", 1)[0].strip()
    if not first:
        return None
    if first.startswith(("陆路", "系统飞行", "固定交通", "任务传送", "使用炉石", "绑定炉石", "开飞行点")):
        return None
    return first


def _system_action(line: str, location_ref: str) -> dict[str, Any] | None:
    stripped = line.strip()
    for prefix, kind in SYSTEM_PREFIXES.items():
        if not stripped.startswith(prefix):
            continue
        payload = stripped[len(prefix) :].strip()
        action: dict[str, Any] = {"kind": kind, "location_ref": location_ref}
        if kind in {"taxi", "fixed_transport", "quest_transport"} and "→" in payload:
            start, end = (part.strip() for part in payload.split("→", 1))
            action["from_name"] = start
            action["to_name"] = end
        else:
            action["target_name"] = payload
        return action
    return None


def _is_confirm_only(line: str, task_name: str) -> bool:
    return "确认已接" in line and f"《{task_name}》" in line


def _inject_after_point(
    actions: list[dict[str, Any]],
    action_ids_by_point: dict[int, list[str]],
    point_index: int,
    action: dict[str, Any],
    add_action,
) -> None:
    add_action(action, point_index)


def _migrate_actions(
    route: dict[str, Any],
    task_name_to_id: dict[str, int],
) -> tuple[list[dict[str, Any]], dict[int, list[str]], dict[str, dict[str, Any]]]:
    actions: list[dict[str, Any]] = []
    action_ids_by_point: dict[int, list[str]] = {}
    locations: dict[str, dict[str, Any]] = {}
    map_labels = {
        (float(label[0]), float(label[1]), str(label[2]))
        for label in route.get("labels", [])
        if isinstance(label, list) and len(label) >= 3
    }
    serial = 0

    def add(action: dict[str, Any], point_index: int) -> None:
        nonlocal serial
        serial += 1
        action_id = f"a{serial:04d}"
        action["action_id"] = action_id
        actions.append(action)
        action_ids_by_point.setdefault(point_index, []).append(action_id)

    for point_index, point in enumerate(route.get("points", [])):
        title = str(point[2] if len(point) > 2 else "").strip() or f"位置{point_index + 1}"
        point_ref = f"hellfire-dk-p{point_index + 1:03d}"
        x, y = point[0], point[1]
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            raise RuntimeError(f"point {point_index + 1} has invalid coordinates")
        locations[point_ref] = {
            "display_name": title,
            "x": x,
            "y": y,
            "phase": str(point[4] if len(point) > 4 else "default") or "default",
            "transport": str(point[6] if len(point) > 6 else "ride") or "ride",
            "show_map_label": (float(x), float(y), title) in map_labels,
        }
        add({"kind": "location", "location_ref": point_ref}, point_index)

        action_text = str(point[3] if len(point) > 3 else "")
        for raw_line in action_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            system = _system_action(line, point_ref)
            if system is not None:
                add(system, point_index)
                continue

            matches = list(TASK_RE.finditer(line))
            if not matches:
                # Only one non-task legacy action currently matters: task flight with an NPC.
                if "乘任务飞行" in line:
                    action: dict[str, Any] = {
                        "kind": "interact",
                        "location_ref": point_ref,
                        "target_name": "乘任务飞行",
                    }
                    npc = _npc_name(line)
                    if npc:
                        action["npc_name"] = npc
                    add(action, point_index)
                # Other prose-only legacy lines are intentionally not persisted as route truth.
                continue

            npc = _npc_name(line)
            for match in matches:
                name = match.group(1)
                if name not in task_name_to_id:
                    raise RuntimeError(f"route action references task without Task Card: {name!r}")
                if _is_confirm_only(line, name):
                    # Redundant state check; the semantic validator proves the earlier accept.
                    continue

                task_id = task_name_to_id[name]
                kind = _task_kind(line, match.start())
                action = {
                    "kind": kind,
                    "task_id": task_id,
                    "location_ref": point_ref,
                }
                if npc and kind in {"accept", "turnin"}:
                    action["npc_name"] = npc

                # 10229 is a fixed route task started from the guaranteed drop item, not an opportunity branch.
                if task_id == 10229 and kind == "accept":
                    action["target_name"] = "神秘典籍"
                if task_id == 10134 and kind == "accept":
                    action["when"] = {"kind": "has_item", "item_name": "火红水晶碎片"}
                if task_id == 10134 and kind == "turnin":
                    action["when"] = {"kind": "task_active", "task_id": 10134}

                # The legacy cross-map line omitted the receiver name; keep the known Zangarmarsh NPC atom.
                if task_id == 9912 and kind == "turnin" and "npc_name" not in action:
                    action["npc_name"] = "伊谢尔·风歌"

                add(action, point_index)

        # Notes that were actually route decisions are migrated explicitly, not parsed generically.
        opportunity = OPPORTUNITY_ACCEPTS.get(title)
        if opportunity is not None:
            task_id, item_name = opportunity
            add(
                {
                    "kind": "accept",
                    "task_id": task_id,
                    "location_ref": point_ref,
                    "when": {"kind": "has_item", "item_name": item_name},
                },
                point_index,
            )

        # Close 10393 on the first natural Thrallmar return after Forge Camp: Mageddon.
        if title == "萨尔玛" and point_index > 0:
            previous_titles = [str(p[2]) for p in route["points"][:point_index]]
            if "铸魔营地：暴虐" in previous_titles and not any(
                action.get("task_id") == 10393 and action["kind"] == "turnin" for action in actions
            ):
                add(
                    {
                        "kind": "turnin",
                        "task_id": 10393,
                        "location_ref": point_ref,
                        "npc_name": "魔导师文森特·血鹰",
                        "when": {"kind": "task_active", "task_id": 10393},
                    },
                    point_index,
                )

        # Missing Missive is an opportunity branch and is handed in on the existing Cenarion visit.
        if title == "塞纳里奥哨站" and any(
            action.get("task_id") == 9373 and action["kind"] == "accept" for action in actions
        ) and not any(action.get("task_id") == 9373 and action["kind"] == "turnin" for action in actions):
            add(
                {
                    "kind": "turnin",
                    "task_id": 9373,
                    "location_ref": point_ref,
                    "npc_name": "塞安·红鬃",
                    "when": {"kind": "task_active", "task_id": 9373},
                },
                point_index,
            )

    return actions, action_ids_by_point, locations


def _migrate_step_groups(
    route: dict[str, Any],
    action_ids_by_point: dict[int, list[str]],
) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for index, group in enumerate(route.get("stepGroups", []), 1):
        start = int(group["start"])
        end = int(group["end"])
        action_ids: list[str] = []
        for point_index in range(start, end + 1):
            action_ids.extend(action_ids_by_point.get(point_index, []))
        if not action_ids:
            raise RuntimeError(f"step group {index} has no migrated actions")
        groups.append(
            {
                "step_id": f"step-{index:02d}",
                "title": str(group.get("title") or f"步骤{index}"),
                "summary": str(group.get("summary") or "") or None,
                "action_ids": action_ids,
            }
        )
    return groups


def build_profile() -> dict[str, Any]:
    route = _load_current_route()
    cards = load_all_task_cards()
    task_name_to_id = _task_name_index(cards)
    actions, action_ids_by_point, locations = _migrate_actions(route, task_name_to_id)

    task_ids: list[int] = []
    for action in actions:
        task_id = action.get("task_id")
        if isinstance(task_id, int) and task_id not in task_ids:
            task_ids.append(task_id)
    if 10103 not in task_ids:
        raise RuntimeError("expected cross-profile task 10103 is missing")

    profile = {
        "schema_version": 1,
        "profile_id": PROFILE_ID,
        "version": 1,
        "status": "draft",
        "scope": {
            "route_scope": "Hellfire Peninsula",
            "character_profile": "dk-twohand-blood-current",
            "game_variant_id": GAME_VARIANT_ID,
        },
        "entry_state_contract": {"active_task_ids": []},
        "exit_state_contract": {"active_task_ids": [10103]},
        "goal": {
            "summary": "从黑暗之门进入地狱火半岛，按当前DK加速路线完成正式任务集合并进入赞加。"
        },
        "display": {
            "publish_key": "hellfire_dk",
            "order": int(route.get("order", 101)),
            "title": str(route.get("title") or "地狱火半岛 · DK专用加速路线"),
            "display_name": str(route.get("displayName") or "地狱火半岛（DK专用）"),
            "subtitle": str(route.get("sub") or ""),
            "footer": str(route.get("footer") or ""),
            "map_image": str(route.get("image") or "maps/3483-hellfire-peninsula-hd.jpg"),
        },
        "task_ids": task_ids,
        "actions": actions,
        "step_groups": _migrate_step_groups(route, action_ids_by_point),
        "geometry": {"locations": locations},
        "change_log": [
            {
                "date": "2026-09-15",
                "kind": "architecture_migration",
                "summary": "从现役DK地狱火路线迁为稳定task_id + 原子结构化action；中文完整执行句不进入正式Profile。",
            }
        ],
    }
    validate_route_profile(profile, known_task_cards=cards)
    return profile


def main() -> None:
    parser = argparse.ArgumentParser(
        description="One-time migration of current DK Hellfire route into Route Profile v1."
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write data/route-profiles/hellfire-dk-speed.json. Default is dry-run validation.",
    )
    args = parser.parse_args()
    profile = build_profile()
    result = {
        "profile_id": profile["profile_id"],
        "status": profile["status"],
        "task_count": len(profile["task_ids"]),
        "action_count": len(profile["actions"]),
        "step_count": len(profile["step_groups"]),
        "conditional_actions": sum("when" in action for action in profile["actions"]),
        "exit_active_task_ids": profile["exit_state_contract"]["active_task_ids"],
        "write": args.write,
    }
    if args.write:
        ROUTE_PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
