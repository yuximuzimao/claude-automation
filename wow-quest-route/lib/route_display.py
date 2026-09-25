from __future__ import annotations

from copy import deepcopy
from typing import Any

from .route_dependencies import canonical_json_hash
from .task_presentation import project_task_presentation


TASK_KINDS = {"accept", "objective", "turnin"}
FORBIDDEN_PROCESS_PHRASES = ("已实测", "已验证", "经审计", "实跑确认", "首组实跑", "第二组实跑")
DISPLAY_GATING_UPSTREAM_STAGES = {"canonical_spatial_movement"}


class RouteDisplayError(ValueError):
    """Raised when the Stage 11 display projection contract is invalid."""


def _issue(severity: str, kind: str, **detail: Any) -> dict[str, Any]:
    return {"severity": severity, "kind": kind, **detail}


def _status(issues: list[dict[str, Any]]) -> str:
    if any(row.get("severity") == "error" for row in issues):
        return "blocked"
    if any(row.get("severity") in {"requirement", "unknown"} for row in issues):
        return "requirements"
    return "pass"


def _task_name(cards: dict[int, dict[str, Any]], task_id: int) -> str:
    card = cards.get(task_id)
    if not isinstance(card, dict):
        raise RouteDisplayError(f"missing Task Card for route task {task_id}")
    name = (card.get("identity") or {}).get("name_zhcn")
    if not isinstance(name, str) or not name.strip():
        raise RouteDisplayError(f"missing zhCN task name for route task {task_id}")
    return name.strip()


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
    raise RouteDisplayError(f"unsupported route action condition: {condition!r}")


def _task_ref(cards: dict[int, dict[str, Any]], action: dict[str, Any]) -> dict[str, Any]:
    task_id = int(action["task_id"])
    return {
        "task_id": task_id,
        "name": _task_name(cards, task_id),
        "kind": str(action["kind"]),
    }


def _render_npc_task_run(
    actions: list[dict[str, Any]],
    start: int,
    cards: dict[int, dict[str, Any]],
) -> tuple[int, dict[str, Any]]:
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

    atoms: list[str] = []
    refs: list[dict[str, Any]] = []
    action_ids: list[str] = []
    cursor = 0
    while cursor < len(run):
        kind = str(run[cursor]["kind"])
        names: list[str] = []
        while cursor < len(run) and run[cursor]["kind"] == kind:
            action = run[cursor]
            names.append(_task_name(cards, int(action["task_id"])))
            refs.append(_task_ref(cards, action))
            action_ids.append(str(action["action_id"]))
            cursor += 1
        verb = "交" if kind == "turnin" else "接"
        atoms.append(f"{verb}" + "、".join(f"《{name}》" for name in names))

    return index, {
        "type": "task_action",
        "text": npc_name + " → " + " → ".join(atoms),
        "actor": {"kind": "npc", "name": npc_name},
        "task_refs": refs,
        "action_ids": action_ids,
    }


def _render_objective_run(
    actions: list[dict[str, Any]],
    start: int,
    cards: dict[int, dict[str, Any]],
) -> tuple[int, dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    names: list[str] = []
    action_ids: list[str] = []
    index = start
    while index < len(actions):
        action = actions[index]
        if action.get("kind") != "objective" or action.get("when") is not None:
            break
        refs.append(_task_ref(cards, action))
        names.append(_task_name(cards, int(action["task_id"])))
        action_ids.append(str(action["action_id"]))
        index += 1
    return index, {
        "type": "task_action",
        "text": "↳ 做" + "、".join(f"《{name}》" for name in names),
        "actor": None,
        "task_refs": refs,
        "action_ids": action_ids,
    }


def _render_single_action(action: dict[str, Any], cards: dict[int, dict[str, Any]]) -> dict[str, Any]:
    kind = str(action["kind"])
    condition = "" if kind == "accept" and (action.get("when") or {}).get("kind") == "has_item" else _condition_text(action)
    action_id = str(action["action_id"])

    if kind in TASK_KINDS:
        ref = _task_ref(cards, action)
        verb = {"accept": "接", "objective": "做", "turnin": "交"}[kind]
        actor = action.get("npc_name") or action.get("target_name")
        text = f"{condition}{actor} → {verb}《{ref['name']}》" if actor else f"{condition}{verb}《{ref['name']}》"
        return {
            "type": "task_action",
            "text": text,
            "actor": (
                {"kind": "npc" if action.get("npc_name") else "target", "name": str(actor)}
                if actor
                else None
            ),
            "task_refs": [ref],
            "action_ids": [action_id],
        }

    if kind == "open_flight_point":
        text = f"开飞行点：{action['target_name']}"
    elif kind == "bind_hearth":
        text = f"绑定炉石：{action['target_name']}"
    elif kind == "use_hearth":
        text = f"使用炉石：{action['target_name']}"
    elif kind == "taxi":
        text = f"系统飞行：{action['from_name']} → {action['to_name']}"
    elif kind == "fixed_transport":
        text = f"固定交通：{action['from_name']} → {action['to_name']}"
    elif kind == "quest_transport":
        text = f"任务传送：{action['from_name']} → {action['to_name']}"
    elif kind == "interact":
        actor = action.get("npc_name")
        target = action.get("target_name") or "交互"
        text = f"{actor} → {target}" if actor else str(target)
    elif kind == "move":
        target = action.get("to_name") or action.get("target_name") or action.get("location_ref")
        if action.get("from_name") and action.get("to_name"):
            text = f"陆路：{action['from_name']} → {action['to_name']}"
        else:
            text = f"前往：{target}"
    else:
        raise RouteDisplayError(f"unsupported action kind: {kind!r}")

    return {
        "type": "route_action",
        "text": condition + text,
        "action_kind": kind,
        "task_refs": [],
        "action_ids": [action_id],
    }


def _render_action_sequence(actions: list[dict[str, Any]], cards: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    index = 0
    while index < len(actions):
        action = actions[index]
        if action.get("kind") == "location":
            raise RouteDisplayError("location actions must be projected as location anchors, not action lines")
        if (
            action.get("kind") in {"accept", "turnin"}
            and action.get("npc_name")
            and action.get("when") is None
        ):
            index, line = _render_npc_task_run(actions, index, cards)
        elif action.get("kind") == "objective" and action.get("when") is None:
            index, line = _render_objective_run(actions, index, cards)
        else:
            line = _render_single_action(action, cards)
            index += 1
        lines.append(line)
    return lines


def _merge_location_with_repeated_npc(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse a location label ending in the same NPC as the next task line.

    Route Profile keeps location and NPC as separate atoms. Display may merge them only when the
    location label explicitly ends with the exact NPC name and the immediately following task line
    repeats that same NPC. Pure place labels remain separate so multiple NPC interactions stay clear.
    """

    merged: list[dict[str, Any]] = []
    index = 0
    while index < len(lines):
        current = lines[index]
        if index + 1 < len(lines) and current.get("type") == "location":
            following = lines[index + 1]
            actor = following.get("actor")
            npc_name = actor.get("name") if isinstance(actor, dict) and actor.get("kind") == "npc" else None
            location_name = current.get("text")
            if (
                isinstance(location_name, str)
                and isinstance(npc_name, str)
                and location_name.endswith(f"·{npc_name}")
            ):
                npc_prefix = f"{npc_name} → "
                following_text = following.get("text")
                if isinstance(following_text, str) and following_text.startswith(npc_prefix):
                    row = deepcopy(following)
                    row["text"] = f"{location_name} → {following_text[len(npc_prefix):]}"
                    row["location_ref"] = current.get("location_ref")
                    row["action_ids"] = list(current.get("action_ids") or []) + list(
                        following.get("action_ids") or []
                    )
                    merged.append(row)
                    index += 2
                    continue
        merged.append(current)
        index += 1
    return merged


def _note_visible_for_task(
    task_id: int,
    step_actions: list[dict[str, Any]],
    presentation: dict[str, Any] | None = None,
) -> bool:
    explicit_kinds = set((presentation or {}).get("note_show_on") or [])
    if explicit_kinds:
        return any(
            action.get("task_id") == task_id and action.get("kind") in explicit_kinds
            for action in step_actions
        )
    for action in step_actions:
        if action.get("task_id") != task_id:
            continue
        if action.get("kind") == "objective":
            return True
        if action.get("kind") == "accept" and (action.get("when") or {}).get("kind") == "has_item":
            return True
    return False


def _safe_timing_projection(timing_report: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    if not isinstance(timing_report, dict):
        return {
            "status": "unavailable",
            "center_minutes": None,
            "range_minutes": None,
            "input_fingerprint": None,
        }, {}

    route_timing = {
        "status": str(timing_report.get("status") or "unknown"),
        "center_minutes": timing_report.get("center_minutes") if timing_report.get("complete") is True else None,
        "range_minutes": timing_report.get("range_minutes") if timing_report.get("complete") is True else None,
        "input_fingerprint": timing_report.get("input_fingerprint"),
    }
    step_timings: dict[str, dict[str, Any]] = {}
    for row in timing_report.get("steps") or []:
        if not isinstance(row, dict) or not isinstance(row.get("step_id"), str):
            continue
        step_timings[row["step_id"]] = {
            "status": "pass" if row.get("complete") is True else "requirements",
            "center_minutes": row.get("center_minutes") if row.get("complete") is True else None,
            "range_minutes": row.get("range_minutes") if row.get("complete") is True else None,
        }
    return route_timing, step_timings


def project_route_display(
    profile: dict[str, Any],
    *,
    cards: dict[int, dict[str, Any]],
    movement_report: dict[str, Any] | None = None,
    timing_report: dict[str, Any] | None = None,
    upstream_statuses: dict[str, str] | None = None,
    upstream_fingerprints: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Project Route Profile + Task Cards into Stage 11 semantic player display data.

    This layer deliberately emits no HTML/CSS and never reads legacy workbench, semantic prose, or
    route-model files. It may expose only complete current Timing values; partial/blocked Timing stays
    structurally present but numerically blank.
    """

    profile_id = str(profile.get("profile_id") or "")
    version = profile.get("version")
    if not profile_id:
        raise RouteDisplayError("profile_id missing")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise RouteDisplayError("profile version missing or invalid")

    actions = profile.get("actions")
    steps = profile.get("step_groups")
    locations = (profile.get("geometry") or {}).get("locations")
    if not isinstance(actions, list) or not isinstance(steps, list) or not isinstance(locations, dict):
        raise RouteDisplayError("profile actions/step_groups/geometry.locations are required")

    issues: list[dict[str, Any]] = []
    statuses = upstream_statuses or {}
    for stage_name, status in statuses.items():
        if stage_name not in DISPLAY_GATING_UPSTREAM_STAGES:
            continue
        if status == "blocked":
            issues.append(_issue("error", "display_upstream_blocked", stage_name=stage_name))
        elif status == "requirements":
            issues.append(_issue("requirement", "display_upstream_requirements", stage_name=stage_name))
        elif status != "pass":
            issues.append(_issue("error", "display_upstream_status_invalid", stage_name=stage_name, status=status))

    action_by_id = {str(action["action_id"]): action for action in actions if isinstance(action, dict) and action.get("action_id")}
    action_to_step: dict[str, str] = {}
    for step in steps:
        step_id = str(step["step_id"])
        for action_id in step["action_ids"]:
            action_to_step[str(action_id)] = step_id
    npc_names = {
        str(action["npc_name"])
        for action in actions
        if isinstance(action, dict) and isinstance(action.get("npc_name"), str) and action["npc_name"]
    }
    reviewed_location_refs: set[str] = set()
    projected_steps: list[dict[str, Any]] = []
    route_task_ids: set[int] = set()
    route_timing, step_timings = _safe_timing_projection(timing_report)
    hearth_chain: list[str] = []
    inherited_hearth = (profile.get("entry_requirements") or {}).get("hearth_location")
    if isinstance(inherited_hearth, str) and inherited_hearth.strip():
        hearth_chain.append(inherited_hearth.strip())
    for action in actions:
        if action.get("kind") != "bind_hearth":
            continue
        target_name = action.get("target_name")
        if isinstance(target_name, str) and target_name.strip() and target_name.strip() not in hearth_chain:
            hearth_chain.append(target_name.strip())

    for step in steps:
        step_id = str(step["step_id"])
        step_actions: list[dict[str, Any]] = []
        for action_id in step["action_ids"]:
            action = action_by_id.get(str(action_id))
            if action is None:
                raise RouteDisplayError(f"step {step_id} references missing action {action_id}")
            step_actions.append(action)

        lines: list[dict[str, Any]] = []
        pending_actions: list[dict[str, Any]] = []
        step_task_ids: list[int] = []

        def flush_actions() -> None:
            nonlocal pending_actions
            if pending_actions:
                lines.extend(_render_action_sequence(pending_actions, cards))
                pending_actions = []

        for action in step_actions:
            if action.get("kind") == "location":
                flush_actions()
                location_ref = str(action["location_ref"])
                location = locations.get(location_ref)
                if not isinstance(location, dict) or not isinstance(location.get("display_name"), str):
                    raise RouteDisplayError(f"missing display location for {location_ref}")
                location_name = str(location["display_name"])
                if location_ref not in reviewed_location_refs:
                    reviewed_location_refs.add(location_ref)
                    if location_name in npc_names:
                        issues.append(
                            _issue(
                                "advisory",
                                "location_display_matches_npc_name",
                                location_ref=location_ref,
                                display_name=location_name,
                            )
                        )
                    if "→" in location_name or location_name.startswith(("系统飞行：", "固定交通：", "任务传送：", "陆路：", "前往：")):
                        issues.append(
                            _issue(
                                "advisory",
                                "location_display_encodes_route_action",
                                location_ref=location_ref,
                                display_name=location_name,
                            )
                        )
                lines.append(
                    {
                        "type": "location",
                        "text": location_name,
                        "location_ref": location_ref,
                        "action_ids": [str(action["action_id"])],
                        "task_refs": [],
                    }
                )
                continue
            task_id = action.get("task_id")
            if isinstance(task_id, int):
                projected_task = project_task_presentation(cards[task_id], profile_id=profile_id)
                if str(action.get("kind")) not in set(projected_task.get("suppress_action_kinds") or []):
                    pending_actions.append(action)
                if task_id not in step_task_ids:
                    step_task_ids.append(task_id)
                    route_task_ids.add(task_id)
            else:
                pending_actions.append(action)
        flush_actions()
        lines = _merge_location_with_repeated_npc(lines)

        presentations: list[dict[str, Any]] = []
        for task_id in step_task_ids:
            projected = project_task_presentation(cards[task_id], profile_id=profile_id)
            note_visible = _note_visible_for_task(task_id, step_actions, projected)
            projected["note_visible"] = note_visible
            if not note_visible:
                projected["note"] = None
            presentations.append(projected)
        for projected in presentations:
            note = projected.get("note")
            if isinstance(note, str) and any(phrase in note for phrase in FORBIDDEN_PROCESS_PHRASES):
                issues.append(
                    _issue(
                        "advisory",
                        "player_note_contains_process_language",
                        step_id=step_id,
                        task_id=projected.get("task_id"),
                    )
                )

        projected_steps.append(
            {
                "step_id": step_id,
                "title": str(step["title"]),
                "summary": str(step.get("summary") or ""),
                "action_ids": [str(value) for value in step["action_ids"]],
                "lines": lines,
                "task_presentations": presentations,
                "timing": step_timings.get(
                    step_id,
                    {"status": "unavailable", "center_minutes": None, "range_minutes": None},
                ),
            }
        )

    profile_task_ids = {int(value) for value in profile.get("task_ids") or []}
    missing_card_ids = sorted(task_id for task_id in route_task_ids if task_id not in cards)
    if missing_card_ids:
        issues.append(_issue("error", "display_task_cards_missing", task_ids=missing_card_ids))
    unexpected_action_tasks = sorted(route_task_ids - profile_task_ids)
    if unexpected_action_tasks:
        issues.append(_issue("error", "display_action_task_outside_profile", task_ids=unexpected_action_tasks))

    map_geometry = {
        "status": "unavailable",
        "input_fingerprint": None,
        "visits": [],
        "edges": [],
    }
    if not isinstance(movement_report, dict):
        issues.append(_issue("requirement", "display_movement_report_required"))
    else:
        movement_profile_id = movement_report.get("profile_id")
        if movement_profile_id is not None and movement_profile_id != profile_id:
            issues.append(
                _issue(
                    "error",
                    "display_movement_profile_mismatch",
                    expected_profile_id=profile_id,
                    actual_profile_id=movement_profile_id,
                )
            )
        visits = movement_report.get("visits")
        edges = movement_report.get("edges")
        if not isinstance(visits, list) or not isinstance(edges, list):
            issues.append(_issue("error", "display_movement_geometry_invalid"))
        else:
            projected_visits: list[dict[str, Any]] = []
            visit_ids: set[str] = set()
            for row in visits:
                if not isinstance(row, dict):
                    issues.append(_issue("error", "display_movement_visit_invalid"))
                    continue
                visit_id = row.get("visit_id")
                location_ref = row.get("location_ref")
                x = row.get("x")
                y = row.get("y")
                location_role = row.get("location_role") or "map_anchor"
                if (
                    not isinstance(visit_id, str)
                    or not visit_id
                    or not isinstance(location_ref, str)
                    or not location_ref
                    or location_role not in {"map_anchor", "transition_context"}
                ):
                    issues.append(_issue("error", "display_movement_visit_invalid", visit_id=visit_id))
                    continue

                coordinates_known = (
                    isinstance(x, (int, float))
                    and not isinstance(x, bool)
                    and isinstance(y, (int, float))
                    and not isinstance(y, bool)
                    and 0 <= float(x) <= 100
                    and 0 <= float(y) <= 100
                )
                coordinates_unknown = x is None and y is None
                if not coordinates_known and not coordinates_unknown:
                    issues.append(_issue("error", "display_movement_visit_invalid", visit_id=visit_id))
                    continue
                if location_role == "transition_context" and coordinates_known:
                    issues.append(
                        _issue(
                            "error",
                            "display_transition_context_coordinates_invalid",
                            visit_id=visit_id,
                            location_ref=location_ref,
                        )
                    )
                    continue
                if location_role == "map_anchor" and coordinates_unknown:
                    issues.append(
                        _issue(
                            "requirement",
                            "display_movement_visit_position_unknown",
                            visit_id=visit_id,
                            location_ref=location_ref,
                        )
                    )

                visit_ids.add(visit_id)
                projected_visits.append(
                    {
                        "visit_id": visit_id,
                        "ordinal": row.get("ordinal"),
                        "location_ref": location_ref,
                        "display_name": row.get("display_name"),
                        "location_role": location_role,
                        "x": float(x) if coordinates_known else None,
                        "y": float(y) if coordinates_known else None,
                        "step_id": action_to_step.get(visit_id),
                    }
                )

            projected_edges: list[dict[str, Any]] = []
            for row in edges:
                if not isinstance(row, dict):
                    issues.append(_issue("error", "display_movement_edge_invalid"))
                    continue
                edge_id = row.get("edge_id")
                from_visit_id = row.get("from_visit_id")
                to_visit_id = row.get("to_visit_id")
                if (
                    not isinstance(edge_id, str)
                    or not edge_id
                    or from_visit_id not in visit_ids
                    or to_visit_id not in visit_ids
                ):
                    issues.append(_issue("error", "display_movement_edge_invalid", edge_id=edge_id))
                    continue
                projected_edges.append(
                    {
                        "edge_id": edge_id,
                        "from_visit_id": from_visit_id,
                        "to_visit_id": to_visit_id,
                        "from_location_ref": row.get("from_location_ref"),
                        "to_location_ref": row.get("to_location_ref"),
                        "operation_kind": row.get("operation_kind"),
                        "movement_mode": row.get("movement_mode"),
                        "movement_action_id": row.get("movement_action_id"),
                        "source": row.get("source"),
                    }
                )
            map_geometry = {
                "status": str(movement_report.get("status") or "unknown"),
                "input_fingerprint": movement_report.get("input_fingerprint"),
                "visits": projected_visits,
                "edges": projected_edges,
            }

    display = profile.get("display") or {}
    fingerprint_payload = {
        "profile": {
            "profile_id": profile_id,
            "version": version,
            "display": display,
            "entry_requirements": profile.get("entry_requirements"),
            "actions": actions,
            "step_groups": steps,
            "geometry_locations": locations,
        },
        "task_presentations": {
            str(task_id): {
                "identity": cards[task_id].get("identity"),
                "fivebox": cards[task_id].get("fivebox"),
                "presentation": cards[task_id].get("presentation"),
            }
            for task_id in sorted(route_task_ids)
            if task_id in cards
        },
        "timing_fingerprint": route_timing.get("input_fingerprint"),
        "map_geometry": map_geometry,
        "upstream_fingerprints": upstream_fingerprints or {},
    }

    return {
        "kind": "route_display",
        "profile_id": profile_id,
        "profile_version": version,
        "status": _status(issues),
        "input_fingerprint": canonical_json_hash(fingerprint_payload),
        "display": {
            "publish_key": display.get("publish_key"),
            "order": display.get("order"),
            "title": display.get("title"),
            "display_name": display.get("display_name"),
            "subtitle": display.get("subtitle"),
            "footer": display.get("footer"),
            "map_image": display.get("map_image"),
        },
        "map_geometry": map_geometry,
        "hearth_chain": hearth_chain,
        "route_timing": route_timing,
        "steps": projected_steps,
        "issues": issues,
    }


def refresh_task_card_display(
    display_report: dict[str, Any],
    presentation: dict[str, Any],
    *,
    update_action_text: bool = False,
) -> dict[str, Any]:
    """Incrementally update one task's player-facing fields inside an existing Route Display.

    This helper is intentionally narrow: it does not load or recompute Replay, Program continuity,
    Movement, Service, Timing, XP, or Economy. It exists for SOP-routed Presentation/identity changes.
    """

    if display_report.get("kind") != "route_display":
        raise RouteDisplayError("incremental display refresh requires a route_display artifact")
    task_id = presentation.get("task_id")
    if not isinstance(task_id, int) or isinstance(task_id, bool):
        raise RouteDisplayError("presentation.task_id must be an integer")

    refreshed = deepcopy(display_report)
    steps = refreshed.get("steps")
    if not isinstance(steps, list):
        raise RouteDisplayError("route_display.steps must be an array")

    found_presentation = False
    old_names: set[str] = set()
    new_name = presentation.get("name")
    if not isinstance(new_name, str) or not new_name.strip():
        raise RouteDisplayError("presentation.name missing")
    new_name = new_name.strip()

    for step in steps:
        if not isinstance(step, dict):
            continue
        task_presentations = step.get("task_presentations")
        if not isinstance(task_presentations, list):
            continue
        for index, current in enumerate(task_presentations):
            if not isinstance(current, dict) or current.get("task_id") != task_id:
                continue
            old_name = current.get("name")
            if isinstance(old_name, str) and old_name:
                old_names.add(old_name)
            replacement = deepcopy(presentation)
            note_visible = current.get("note_visible", True)
            replacement["note_visible"] = note_visible
            if not note_visible:
                replacement["note"] = None
            task_presentations[index] = replacement
            found_presentation = True

    if not found_presentation:
        raise RouteDisplayError(f"task {task_id} is not present in route_display task presentations")

    if update_action_text:
        for step in steps:
            if not isinstance(step, dict):
                continue
            lines = step.get("lines")
            if not isinstance(lines, list):
                continue
            for line in lines:
                if not isinstance(line, dict):
                    continue
                refs = line.get("task_refs")
                if not isinstance(refs, list):
                    continue
                line_contains_task = False
                for ref in refs:
                    if not isinstance(ref, dict) or ref.get("task_id") != task_id:
                        continue
                    ref_name = ref.get("name")
                    if isinstance(ref_name, str) and ref_name:
                        old_names.add(ref_name)
                    ref["name"] = new_name
                    line_contains_task = True
                if line_contains_task:
                    text = line.get("text")
                    if isinstance(text, str):
                        for old_name in sorted(old_names, key=len, reverse=True):
                            text = text.replace(f"《{old_name}》", f"《{new_name}》")
                        line["text"] = text

    issues = [
        row
        for row in (refreshed.get("issues") or [])
        if not (
            isinstance(row, dict)
            and row.get("kind") == "player_note_contains_process_language"
            and row.get("task_id") == task_id
        )
    ]
    note = presentation.get("note")
    if isinstance(note, str) and any(phrase in note for phrase in FORBIDDEN_PROCESS_PHRASES):
        issues.append(_issue("advisory", "player_note_contains_process_language", task_id=task_id))
    refreshed["issues"] = issues
    refreshed["status"] = _status(issues)

    fingerprint_payload = {
        key: value
        for key, value in refreshed.items()
        if key != "input_fingerprint"
    }
    refreshed["input_fingerprint"] = canonical_json_hash(fingerprint_payload)
    return refreshed
