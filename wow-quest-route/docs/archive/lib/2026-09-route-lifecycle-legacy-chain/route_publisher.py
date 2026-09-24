from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from .route_profiles import load_route_profile
from .task_cards import load_all_task_cards
from .task_presentation import project_task_presentation

ROOT = Path(__file__).resolve().parents[1]
ROUTE_MODELS_DIR = ROOT / "data/route-models"
ROUTE_UI_DIR = ROOT / "data/route-ui"
SEMANTIC_HUD_STANDARD = "semantic-hud-v45"
TASK_KINDS = {"accept", "objective", "turnin"}


class RoutePublisherError(ValueError):
    """Raised when current truth sources cannot be projected into a route payload."""


def _timing_model_path(profile_id: str) -> Path:
    return ROUTE_MODELS_DIR / f"{profile_id}-timing.json"


def load_route_timing_model(profile_id: str) -> dict[str, Any]:
    path = _timing_model_path(profile_id)
    if not path.exists():
        raise RoutePublisherError(f"missing route timing model: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("profile_id") != profile_id:
        raise RoutePublisherError(
            f"timing model profile_id mismatch: {payload.get('profile_id')!r} != {profile_id!r}"
        )
    route = payload.get("route") or {}
    if not isinstance(route.get("center_minutes"), (int, float)):
        raise RoutePublisherError(f"timing model route center_minutes missing: {profile_id}")
    if not isinstance(route.get("range_minutes"), list) or len(route["range_minutes"]) != 2:
        raise RoutePublisherError(f"timing model route range_minutes missing: {profile_id}")
    return payload


def load_route_ui_config(profile_id: str) -> dict[str, Any]:
    path = ROUTE_UI_DIR / f"{profile_id}.json"
    if not path.exists():
        return {"schema_version": 1, "profile_id": profile_id, "map_labels": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("profile_id") != profile_id:
        raise RoutePublisherError(
            f"route UI profile_id mismatch: {payload.get('profile_id')!r} != {profile_id!r}"
        )
    labels = payload.get("map_labels", [])
    if not isinstance(labels, list):
        raise RoutePublisherError(f"route UI map_labels must be a list: {profile_id}")
    return payload


def _task_name(cards: dict[int, dict[str, Any]], task_id: int) -> str:
    try:
        return str(cards[task_id]["identity"]["name_zhcn"])
    except KeyError as exc:
        raise RoutePublisherError(f"missing Task Card for route task {task_id}") from exc


def _task_html(name: str, kind: str) -> str:
    cls = {"turnin": "ra-turnin", "accept": "ra-accept", "objective": "ra-do-task"}[kind]
    return f'<span class="ra-task {cls}">{html.escape(name)}</span>'


def _verb_html(value: str) -> str:
    return f'<span class="ra-verb">{html.escape(value)}</span>'


def _arrow_html() -> str:
    return '<span class="ra-arrow">→</span>'


def _npc_html(value: str) -> str:
    return f'<span class="ra-npc">{html.escape(value)}</span>'


def _condition_text(action: dict[str, Any]) -> str:
    condition = action.get("when")
    if not isinstance(condition, dict):
        return ""
    kind = condition.get("kind")
    if kind == "has_item":
        item = condition.get("item_name") or condition.get("item_id")
        return f"若持有{item}："
    if kind == "task_active":
        return "若任务仍在："
    if kind == "task_complete":
        return "若已完成："
    raise RoutePublisherError(f"unsupported route action condition: {condition!r}")


def _condition_html(action: dict[str, Any]) -> str:
    value = _condition_text(action)
    if not value:
        return ""
    return f'<span class="ra-key">{html.escape(value)}</span>'


def _render_npc_task_run(
    actions: list[dict[str, Any]],
    start: int,
    cards: dict[int, dict[str, Any]],
) -> tuple[int, str, str]:
    first = actions[start]
    npc_name = str(first["npc_name"])
    run: list[dict[str, Any]] = []
    index = start
    while index < len(actions):
        action = actions[index]
        if (
            action.get("kind") not in {"accept", "turnin"}
            or action.get("npc_name") != npc_name
            or action.get("when") is not None
        ):
            break
        run.append(action)
        index += 1

    atoms_plain: list[str] = []
    atoms_html: list[str] = []
    cursor = 0
    while cursor < len(run):
        kind = str(run[cursor]["kind"])
        names: list[str] = []
        while cursor < len(run) and run[cursor]["kind"] == kind:
            names.append(_task_name(cards, int(run[cursor]["task_id"])))
            cursor += 1
        verb = "交" if kind == "turnin" else "接"
        atoms_plain.append(f"{verb}" + "、".join(f"《{name}》" for name in names))
        atoms_html.append(
            _verb_html(verb)
            + " "
            + "、".join(_task_html(name, kind) for name in names)
        )

    plain = npc_name + " → " + " → ".join(atoms_plain)
    html_line = '<div class="ra-line">' + _npc_html(npc_name)
    for atom in atoms_html:
        html_line += _arrow_html() + atom
    html_line += "</div>"
    return index, plain, html_line


def _render_objective_run(
    actions: list[dict[str, Any]],
    start: int,
    cards: dict[int, dict[str, Any]],
) -> tuple[int, str, str]:
    names: list[str] = []
    index = start
    while index < len(actions):
        action = actions[index]
        if action.get("kind") != "objective" or action.get("when") is not None:
            break
        names.append(_task_name(cards, int(action["task_id"])))
        index += 1
    plain = "↳ 做" + "、".join(f"《{name}》" for name in names)
    html_line = (
        '<div class="ra-line ra-do"><span class="ra-branch">↳</span>'
        + _verb_html("做")
        + " "
        + "、".join(_task_html(name, "objective") for name in names)
        + "</div>"
    )
    return index, plain, html_line


def _render_single_action(
    action: dict[str, Any],
    cards: dict[int, dict[str, Any]],
) -> tuple[str, str]:
    kind = str(action["kind"])
    hide_condition = kind == "accept" and (action.get("when") or {}).get("kind") == "has_item"
    condition_plain = "" if hide_condition else _condition_text(action)
    condition_html = "" if hide_condition else _condition_html(action)

    if kind in TASK_KINDS:
        name = _task_name(cards, int(action["task_id"]))
        verb = {"accept": "接", "objective": "做", "turnin": "交"}[kind]
        actor = action.get("npc_name") or action.get("target_name")
        if actor:
            plain = f"{condition_plain}{actor} → {verb}《{name}》"
            html_line = '<div class="ra-line">' + condition_html
            if action.get("npc_name"):
                html_line += _npc_html(str(actor))
            else:
                html_line += f'<span class="ra-transport">{html.escape(str(actor))}</span>'
            html_line += _arrow_html() + _verb_html(verb) + " " + _task_html(name, kind) + "</div>"
            return plain, html_line
        plain = f"{condition_plain}{verb}《{name}》"
        do_class = " ra-do" if kind == "objective" else ""
        branch = '<span class="ra-branch">↳</span>' if kind == "objective" else ""
        return (
            plain,
            f'<div class="ra-line{do_class}">{condition_html}{branch}{_verb_html(verb)} {_task_html(name, kind)}</div>',
        )

    if kind == "open_flight_point":
        text = f"开飞行点：{action['target_name']}"
        cls = "ra-flightpoint"
    elif kind == "bind_hearth":
        text = f"绑定炉石：{action['target_name']}"
        cls = "ra-hearthstone"
    elif kind == "use_hearth":
        text = f"使用炉石：{action['target_name']}"
        cls = "ra-hearthstone"
    elif kind == "taxi":
        text = f"系统飞行：{action['from_name']} → {action['to_name']}"
        cls = "ra-flightpath"
    elif kind == "fixed_transport":
        text = f"固定交通：{action['from_name']} → {action['to_name']}"
        cls = "ra-transport"
    elif kind == "quest_transport":
        text = f"任务传送：{action['from_name']} → {action['to_name']}"
        cls = "ra-flightpath"
    elif kind == "interact":
        actor = action.get("npc_name")
        target = action.get("target_name") or "交互"
        text = f"{actor} → {target}" if actor else str(target)
        if actor:
            return (
                text,
                '<div class="ra-line">'
                + _npc_html(str(actor))
                + _arrow_html()
                + f'<span class="ra-transport">{html.escape(str(target))}</span></div>',
            )
        cls = "ra-transport"
    elif kind == "move":
        target = action.get("to_name") or action.get("target_name") or action.get("location_ref")
        if action.get("from_name") and action.get("to_name"):
            text = f"陆路：{action['from_name']} → {action['to_name']}"
        else:
            text = f"前往：{target}"
        cls = "ra-transport"
    else:
        raise RoutePublisherError(f"unsupported action kind: {kind!r}")

    return text, f'<div class="ra-line"><span class="ra-system-action {cls}">{html.escape(text)}</span></div>'


def _render_point_actions(
    actions: list[dict[str, Any]],
    cards: dict[int, dict[str, Any]],
) -> tuple[list[str], list[str]]:
    plain_lines: list[str] = []
    html_lines: list[str] = []
    index = 0
    while index < len(actions):
        action = actions[index]
        if (
            action.get("kind") in {"accept", "turnin"}
            and action.get("npc_name")
            and action.get("when") is None
        ):
            index, plain, html_line = _render_npc_task_run(actions, index, cards)
        elif action.get("kind") == "objective" and action.get("when") is None:
            index, plain, html_line = _render_objective_run(actions, index, cards)
        else:
            plain, html_line = _render_single_action(action, cards)
            index += 1
        plain_lines.append(plain)
        html_lines.append(html_line)
    return plain_lines, html_lines


def _status_html(projected: dict[str, Any]) -> str:
    badge = projected.get("badge")
    if badge == "shared":
        return '<span class="ra-shared">共享：</span>'
    if badge == "not_shared":
        return '<span class="ra-not-shared">不共享：</span>'
    if badge == "sequential_loot":
        return '<span class="ra-sequential-loot">依次拾取：</span>'
    if badge == "special":
        return '<span class="ra-special">特殊：</span>'
    if projected.get("pending"):
        return '<span class="ra-fivebox-check">五开待实测：</span>'
    return ""


def _render_step_notes(
    task_ids: list[int],
    cards: dict[int, dict[str, Any]],
    *,
    profile_id: str,
) -> str:
    blocks: list[str] = []
    seen: set[int] = set()
    for task_id in task_ids:
        if task_id in seen:
            continue
        seen.add(task_id)
        projected = project_task_presentation(cards[task_id], profile_id=profile_id)
        body = _status_html(projected)
        note = str(projected.get("note") or "").strip()
        if note:
            body += html.escape(note).replace("\n", "<br>")
        if not body:
            continue
        blocks.append(
            '<div class="ra-note-block">'
            f'<div class="ra-note-task">《{html.escape(str(projected["name"]))}》</div>'
            f'<div class="ra-note-text">{body}</div>'
            "</div>"
        )
    if not blocks:
        return ""
    return '<div class="ra-note-heading">备注</div>' + "".join(blocks)


def build_route_payload(
    profile_id: str,
    *,
    profile: dict[str, Any] | None = None,
    cards: dict[int, dict[str, Any]] | None = None,
    timing_model: dict[str, Any] | None = None,
    route_ui: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = profile or load_route_profile(profile_id, validate=True, validate_task_cards=True)
    cards = cards or load_all_task_cards()
    timing_model = timing_model or load_route_timing_model(profile_id)
    route_ui = route_ui or load_route_ui_config(profile_id)

    actions = profile["actions"]
    locations = profile["geometry"]["locations"]
    action_to_point: dict[str, int] = {}
    points: list[list[Any]] = []
    point_html: list[list[str]] = []
    current_actions: list[dict[str, Any]] = []
    current_location_ref: str | None = None

    def flush() -> None:
        nonlocal current_actions, current_location_ref
        if current_location_ref is None:
            return
        location = locations[current_location_ref]
        plain_lines, html_lines = _render_point_actions(current_actions, cards)
        point_index = len(points)
        points.append(
            [
                location["x"],
                location["y"],
                location["display_name"],
                "\n".join(plain_lines),
                location.get("phase", "default"),
                "",
                location.get("transport", ""),
                False,
                "",
            ]
        )
        point_html.append(html_lines)
        for action in current_actions:
            action_to_point[action["action_id"]] = point_index
        current_actions = []
        current_location_ref = None

    for action in actions:
        if action["kind"] == "location":
            flush()
            current_location_ref = str(action["location_ref"])
            action_to_point[action["action_id"]] = len(points)
            continue
        if current_location_ref is None:
            raise RoutePublisherError(
                f"action {action['action_id']} occurs before any location action in {profile_id}"
            )
        current_actions.append(action)
    flush()

    step_models = timing_model.get("steps") or {}
    step_groups: list[dict[str, Any]] = []
    action_by_id = {action["action_id"]: action for action in actions}
    for step in profile["step_groups"]:
        step_id = str(step["step_id"])
        model = step_models.get(step_id)
        if not isinstance(model, dict):
            raise RoutePublisherError(f"missing step timing model: {profile_id} {step_id}")
        point_indices = [action_to_point[action_id] for action_id in step["action_ids"]]
        start = min(point_indices)
        end = max(point_indices)
        action_html_lines: list[str] = []
        last_point = None
        task_ids: list[int] = []
        for action_id in step["action_ids"]:
            action = action_by_id[action_id]
            point_index = action_to_point[action_id]
            if point_index != last_point:
                location_name = str(points[point_index][2])
                action_html_lines.append(
                    f'<div class="ra-line ra-point-anchor"><span class="ra-location">{html.escape(location_name)}</span></div>'
                )
                action_html_lines.extend(point_html[point_index])
                last_point = point_index
            task_id = action.get("task_id")
            if isinstance(task_id, int) and task_id not in task_ids:
                task_ids.append(task_id)
        step_timing = {
            "centerMinutes": model.get("center_minutes"),
            "rangeMinutes": model.get("range_minutes"),
        }
        if "include_in_total" in model:
            step_timing["includeInTotal"] = bool(model["include_in_total"])
        if model.get("status"):
            step_timing["status"] = model["status"]
        step_groups.append(
            {
                "start": start,
                "end": end,
                "title": step["title"],
                "summary": step.get("summary") or "",
                "timing": step_timing,
                "actionHtml": "\n".join(action_html_lines),
                "noteHtml": _render_step_notes(task_ids, cards, profile_id=profile_id),
            }
        )

    map_labels = route_ui.get("map_labels", [])
    labels = [[row["x"], row["y"], row["display_name"]] for row in map_labels]

    hearth_chain: list[str] = []
    inherited_hearth = profile.get("entry_requirements", {}).get("hearth_location")
    if inherited_hearth:
        hearth_chain.append(str(inherited_hearth))
    for action in actions:
        if action["kind"] == "bind_hearth":
            name = str(action["target_name"])
            if name not in hearth_chain:
                hearth_chain.append(name)

    route_timing = timing_model["route"]
    center = route_timing.get("center_minutes")
    display_badge = str(timing_model.get("display_badge") or "").strip()
    if display_badge:
        badge = display_badge
    else:
        qualifier = str(route_timing.get("display_qualifier") or "").strip()
        timing_suffix = f"（{qualifier}）" if qualifier else ""
        hearth_display = " → ".join(hearth_chain) if hearth_chain else "未记录"
        if isinstance(center, (int, float)):
            badge = f"炉石：{hearth_display}\n预计总时间：{center:g}分钟{timing_suffix}"
        else:
            badge = f"炉石：{hearth_display}\n预计总时间：待重算"
    display = profile["display"]
    return {
        "order": display["order"],
        "title": display["title"],
        "displayName": display["display_name"],
        "sub": display["subtitle"],
        "badge": badge,
        "hearthChain": hearth_chain,
        "timing": {
            "centerMinutes": center,
            "rangeMinutes": route_timing["range_minutes"],
        },
        "uiStandard": SEMANTIC_HUD_STANDARD,
        "image": display["map_image"],
        "legend": "",
        "footer": display["footer"],
        "labels": labels,
        "points": points,
        "defaultIndex": 0,
        "phaseColors": {},
        "stepGroups": step_groups,
        "defaultGroupIndex": 0,
    }
