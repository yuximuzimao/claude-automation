from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.questie_source import load_questie
from lib.route_atlas_exact import representative_point

QUESTIE_ZIP = ROOT / "data" / "sources" / "questie" / "Questie.zip"
ATLAS = ROOT / "data" / "route-atlas" / "zangarmarsh-npc-validation.json"
PROFILES = ROOT / "data" / "route-atlas" / "zangarmarsh-task-profiles.json"
OUTPUT = ROOT / "data" / "route-atlas" / "zangarmarsh-global-solver-input-audit.json"
REPORT = ROOT / "docs" / "analysis" / "2026-08-13-zangarmarsh-global-solver-input-audit.md"
ZONE_ID = 3521
MIN_QL = 58
MAX_QL = 68


def seq(table: Any) -> list[Any]:
    if not isinstance(table, dict):
        return []
    return [table[k] for k in sorted(k for k in table if isinstance(k, int))]


def zone_points(raw: dict[Any, Any] | None, field: int) -> list[tuple[float, float]]:
    if not raw:
        return []
    spawns = raw.get(field)
    if not isinstance(spawns, dict):
        return []
    rows = spawns.get(ZONE_ID)
    if not isinstance(rows, dict):
        return []
    points: list[tuple[float, float]] = []
    for row in seq(rows):
        if isinstance(row, dict):
            vals = seq(row)
        else:
            vals = row
        if isinstance(vals, (list, tuple)) and len(vals) >= 2:
            try:
                points.append((float(vals[0]), float(vals[1])))
            except (TypeError, ValueError):
                pass
    return points


def ref_location_status(ref: dict[str, Any], questie: Any) -> dict[str, Any]:
    kind = ref.get("kind")
    entity_id = int(ref.get("id"))
    if kind == "npcs":
        points = zone_points(questie.npcs.get(entity_id), 7)
    elif kind == "objects":
        points = zone_points(questie.objects.get(entity_id), 4)
    else:
        points = []
    point = representative_point(points) if points else None
    return {
        "kind": kind,
        "id": entity_id,
        "name": ref.get("name"),
        "local_points": len(points),
        "representative_point": list(point) if point else None,
        "local_executable": bool(point),
    }


def component_status(component: dict[str, Any]) -> dict[str, Any]:
    sources = component.get("sources") or []
    usable_sources = []
    for source in sources:
        point = source.get("representative_point")
        cost = source.get("expected_service_seconds")
        if cost is None:
            cost = component.get("estimated_objective_seconds")
        if point is not None and isinstance(cost, (int, float)):
            usable_sources.append({
                "kind": source.get("kind"),
                "entity_id": source.get("entity_id"),
                "name": source.get("name"),
                "point": point,
                "service_seconds": cost,
                "shortcut": bool(source.get("low_density_shortcut")),
            })
    family = component.get("family")
    if family in {"explore_trigger", "scripted_interact"}:
        # These families may store their execution point in baseline_source even if `sources`
        # is empty. Treat a materialized zero-duration interaction at a known point as usable.
        base = component.get("baseline_source") or {}
        point = base.get("representative_point")
        cost = component.get("estimated_objective_seconds")
        if point is not None and isinstance(cost, (int, float)):
            usable_sources.append({
                "kind": base.get("kind") or family,
                "entity_id": base.get("entity_id"),
                "name": base.get("name") or component.get("label"),
                "point": point,
                "service_seconds": cost,
                "shortcut": False,
            })
    return {
        "id": component.get("id"),
        "family": family,
        "label": component.get("label"),
        "needed_count": component.get("needed_count"),
        "estimated_objective_seconds": component.get("estimated_objective_seconds"),
        "usable_sources": usable_sources,
        "usable": bool(usable_sources),
    }


def candidate_ids(atlas: dict[str, Any], profiles: dict[str, Any]) -> list[int]:
    ids: list[int] = []
    for qid_text, quest in atlas["quests"].items():
        profile = profiles["quests"].get(qid_text) or {}
        ql = quest.get("quest_level")
        req = quest.get("required_level")
        if profile.get("route_policy") != "include":
            continue
        if not profile.get("time_model_valid_for_global_optimizer"):
            continue
        if not isinstance(ql, (int, float)) or not (MIN_QL <= ql <= MAX_QL):
            continue
        if not isinstance(req, (int, float)) or req > MAX_QL:
            continue
        ids.append(int(qid_text))
    return sorted(ids)


def main() -> None:
    atlas = json.loads(ATLAS.read_text(encoding="utf-8"))
    profiles = json.loads(PROFILES.read_text(encoding="utf-8"))
    questie = load_questie(QUESTIE_ZIP)
    candidates = candidate_ids(atlas, profiles)
    selected = set(candidates)

    rows: dict[str, Any] = {}
    hard_blockers: list[dict[str, Any]] = []
    external_prereq_rows: list[dict[str, Any]] = []

    for qid in candidates:
        qid_text = str(qid)
        quest = atlas["quests"][qid_text]
        profile = profiles["quests"][qid_text]
        raw = questie.quests.get(qid) or {}

        starts = [ref_location_status(r, questie) for r in quest.get("started_by") or []]
        finishes = [ref_location_status(r, questie) for r in quest.get("finished_by") or []]
        local_starts = [r for r in starts if r["local_executable"]]
        local_finishes = [r for r in finishes if r["local_executable"]]
        start_kinds = sorted({str(r.get("kind")) for r in quest.get("started_by") or []})
        finish_kinds = sorted({str(r.get("kind")) for r in quest.get("finished_by") or []})

        pre_any = [int(v) for v in quest.get("pre_quest_single") or []]
        pre_all = [abs(int(v)) for v in quest.get("pre_quest_group") or []]
        external_any = [p for p in pre_any if p not in selected]
        external_all = [p for p in pre_all if p not in selected]
        if external_any or external_all:
            external_prereq_rows.append({
                "quest_id": qid,
                "name": profile.get("name"),
                "external_pre_any": external_any,
                "external_pre_all": external_all,
            })

        components = [component_status(c) for c in profile.get("components") or []]
        start_acquisition = profile.get("start_acquisition") or {}
        acquisition_sources = [
            source
            for source in start_acquisition.get("sources") or []
            if isinstance(source, dict)
            and isinstance(source.get("point"), list)
            and len(source.get("point")) >= 2
            and isinstance(source.get("expected_service_seconds"), (int, float))
        ]
        effective_type = profile.get("classification", {}).get("effective_primary")
        effective_time = profile.get("effective_time_estimate") or {}
        objective_seconds = effective_time.get("objective_seconds")
        total_seconds = effective_time.get("estimated_total_seconds")

        issues: list[str] = []
        notes: list[str] = []

        if not local_starts:
            if acquisition_sources:
                notes.append("accept_is_materialized_start_acquisition")
            elif "items" in start_kinds:
                issues.append("item_start_requires_source_event")
            elif "objects" in start_kinds:
                issues.append("object_start_missing_local_point")
            else:
                issues.append("no_local_accept_location")
        if not local_finishes:
            issues.append("no_local_turnin_location")

        if effective_type == "handoff" or effective_type == "find_npc_handoff":
            pass
        elif effective_type == "scripted_transport":
            if not isinstance(total_seconds, (int, float)):
                issues.append("missing_script_duration")
        elif effective_type == "escort":
            if not isinstance(total_seconds, (int, float)):
                issues.append("missing_escort_duration")
        else:
            if components and any(not c["usable"] for c in components):
                issues.append("component_without_service_point_or_cost")
            elif not components and not isinstance(objective_seconds, (int, float)):
                issues.append("no_service_event_model")

        if not isinstance(total_seconds, (int, float)) and effective_type not in {"handoff"}:
            notes.append("solo_total_missing_or_not_materialized")

        # External prerequisites do not necessarily invalidate a route: they can be declared
        # complete in the initial state. Keep them separate from true geometric/time blockers.
        hard = bool(issues)
        row = {
            "quest_id": qid,
            "name": profile.get("name"),
            "effective_type": effective_type,
            "quest_level": quest.get("quest_level"),
            "required_level": quest.get("required_level"),
            "local_starts": local_starts,
            "local_finishes": local_finishes,
            "all_starts": starts,
            "all_finishes": finishes,
            "start_kinds": start_kinds,
            "finish_kinds": finish_kinds,
            "pre_any": pre_any,
            "pre_all": pre_all,
            "external_pre_any": external_any,
            "external_pre_all": external_all,
            "components": components,
            "start_acquisition": {
                "item_id": start_acquisition.get("item_id"),
                "item_name": start_acquisition.get("item_name"),
                "mode": start_acquisition.get("mode"),
                "sources": acquisition_sources,
            } if acquisition_sources else None,
            "objective_seconds": objective_seconds,
            "estimated_total_seconds": total_seconds,
            "issues": issues,
            "notes": notes,
            "hard_blocker": hard,
        }
        rows[qid_text] = row
        if hard:
            hard_blockers.append(row)

    issue_counts: dict[str, int] = {}
    for row in hard_blockers:
        for issue in row["issues"]:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1

    payload = {
        "meta": {
            "zone_id": ZONE_ID,
            "quest_level_window": [MIN_QL, MAX_QL],
            "candidate_rule": "route_policy=include AND time_model_valid AND quest_level 58..68 AND required_level<=68",
            "questie_version": atlas["meta"]["questie_version"],
            "questie_sha256": atlas["meta"]["questie_sha256"],
        },
        "summary": {
            "candidate_quests": len(candidates),
            "hard_blockers": len(hard_blockers),
            "solver_ready": len(candidates) - len(hard_blockers),
            "external_prerequisite_quests": len(external_prereq_rows),
            "issue_counts": issue_counts,
        },
        "candidate_ids": candidates,
        "external_prerequisites": external_prereq_rows,
        "quests": rows,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 赞加沼泽第四层 4A：全局求解输入审计",
        "",
        f"- 候选任务：{len(candidates)}",
        f"- 可直接进入全局求解器：{len(candidates) - len(hard_blockers)}",
        f"- 硬阻塞：{len(hard_blockers)}",
        f"- 含候选集外前置：{len(external_prereq_rows)}（单独作为初始状态/路线边界处理，不与硬缺数据混淆）",
        "",
        "## 硬阻塞分类",
        "",
    ]
    for issue, count in sorted(issue_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"- `{issue}`：{count}")
    lines.extend(["", "## 硬阻塞任务", ""])
    for row in hard_blockers:
        lines.append(f"- {row['quest_id']}《{row['name']}》：{', '.join(row['issues'])}")
    lines.extend(["", "## 候选集外前置", ""])
    for row in external_prereq_rows:
        lines.append(
            f"- {row['quest_id']}《{row['name']}》：OR外部={row['external_pre_any']}；AND外部={row['external_pre_all']}"
        )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(OUTPUT)
    print(REPORT)


if __name__ == "__main__":
    main()
