from __future__ import annotations

from typing import Any

from lib.route_atlas_exact import representative_point
from scripts.build_zangarmarsh_task_profiles import FIVE_BOX_CHARACTERS, FIXED_KILL_SECONDS, travel_seconds


def _first_local_npc_point(
    refs: list[dict[str, Any]], npc_by_id: dict[int, dict[str, Any]]
) -> tuple[float, float] | None:
    for ref in refs:
        if ref.get("kind") != "npcs":
            continue
        npc = npc_by_id.get(int(ref["id"]))
        if not npc:
            continue
        point = representative_point(npc.get("spawns") or [])
        if point is not None:
            return point
    return None


def materialize_manual_special_time(
    profile: dict[str, Any],
    atlas_quest: dict[str, Any],
    override: dict[str, Any],
    npc_by_id: dict[int, dict[str, Any]],
) -> None:
    """Materialize persisted timing for item-start and manually located script tasks.

    For item-start tasks the acquisition itself creates A(Q). The standalone task-card estimate
    begins at that acquisition source; the global route solver separately pays movement from the
    previous route action to the source.
    """
    components = profile.get("components") or []
    component_points: list[tuple[float, float]] = []
    component_seconds: list[float] = []
    for component in components:
        point = component.get("baseline_point") or (
            component.get("baseline_source") or {}
        ).get("representative_point")
        seconds = component.get("estimated_objective_seconds")
        if point is not None and isinstance(seconds, (int, float)):
            component_points.append((float(point[0]), float(point[1])))
            component_seconds.append(float(seconds))

    finish = _first_local_npc_point(atlas_quest.get("finished_by") or [], npc_by_id)
    acquisition = override.get("start_acquisition")

    if isinstance(acquisition, dict):
        materialized_sources: list[dict[str, Any]] = []
        for source in acquisition.get("sources") or []:
            if not isinstance(source, dict):
                continue
            point = source.get("point")
            rate_percent = source.get("drop_rate_percent")
            acquisition_seconds = source.get("expected_service_seconds")
            row = dict(source)
            if isinstance(rate_percent, (int, float)) and rate_percent > 0:
                probability = float(rate_percent) / 100.0
                expected_kills = FIVE_BOX_CHARACTERS / probability
                failure_wait = 0.0
                respawn = source.get("respawn_seconds_proxy")
                if acquisition.get("mode") == "single_boss_drop_starts_quest" and isinstance(respawn, (int, float)):
                    failure_wait = FIVE_BOX_CHARACTERS * (1.0 - probability) / probability * float(respawn)
                acquisition_seconds = expected_kills * FIXED_KILL_SECONDS + failure_wait
                row["per_character_required_count"] = 1
                row["characters"] = FIVE_BOX_CHARACTERS
                row["five_box_required_count"] = FIVE_BOX_CHARACTERS
                row["expected_kills"] = expected_kills
                row["single_kill_seconds"] = FIXED_KILL_SECONDS
                row["expected_failure_wait_seconds"] = failure_wait
                row["expected_service_seconds"] = acquisition_seconds
            if not (
                isinstance(point, list)
                and len(point) >= 2
                and isinstance(acquisition_seconds, (int, float))
            ):
                continue
            current = (float(point[0]), float(point[1]))
            travel = 0.0
            for work_point in component_points:
                travel += travel_seconds(current, work_point)
                current = work_point
            if finish is not None:
                travel += travel_seconds(current, finish)
            service = float(acquisition_seconds) + sum(component_seconds)
            row["post_acquisition_travel_seconds"] = travel
            row["post_acquisition_component_seconds"] = sum(component_seconds)
            row["standalone_total_seconds"] = service + travel
            materialized_sources.append(row)

        if not materialized_sources:
            return
        baseline = min(
            materialized_sources, key=lambda row: float(row["standalone_total_seconds"])
        )
        profile["start_acquisition"] = {
            **acquisition,
            "sources": materialized_sources,
            "baseline_source_entity_id": baseline.get("entity_id"),
            "baseline_source_name": baseline.get("name"),
            "baseline_source_point": baseline.get("point"),
            "baseline_acquisition_seconds": baseline.get("expected_service_seconds"),
            "baseline_standalone_total_seconds": baseline.get("standalone_total_seconds"),
        }
        profile["effective_time_estimate"] = {
            "mode": "item_start_materialized",
            "travel_to_work_seconds": 0.0,
            "work_internal_travel_seconds": baseline.get("post_acquisition_travel_seconds"),
            "work_to_turnin_seconds": 0.0,
            "total_travel_seconds": baseline.get("post_acquisition_travel_seconds"),
            "objective_seconds": float(baseline.get("expected_service_seconds"))
            + sum(component_seconds),
            "estimated_total_seconds": baseline.get("standalone_total_seconds"),
            "calculation": {
                "formula": "start_item_acquisition_seconds + post_acquisition_travel_seconds + component_seconds",
                "inputs": {
                    "baseline_source_entity_id": baseline.get("entity_id"),
                    "start_item_acquisition_seconds": baseline.get("expected_service_seconds"),
                    "post_acquisition_travel_seconds": baseline.get(
                        "post_acquisition_travel_seconds"
                    ),
                    "component_seconds": component_seconds,
                },
                "result": baseline.get("standalone_total_seconds"),
                "unit": "seconds",
                "source": "manual_start_acquisition_materialization",
                "quality": acquisition.get("quality", "manual_external_proxy"),
            },
            "source": "manual_start_acquisition_materialization",
        }
        return

    # Manually located use/summon tasks usually contain one Objective component. Rebuild their
    # persisted solo estimate after the point override fills the missing Questie spawn location.
    component_overrides = override.get("component_overrides")
    has_manual_point = isinstance(component_overrides, dict) and any(
        isinstance(patch, dict) and patch.get("manual_point") is not None
        for patch in component_overrides.values()
    )
    if not has_manual_point or not component_points or finish is None:
        return
    start = _first_local_npc_point(atlas_quest.get("started_by") or [], npc_by_id)
    if start is None:
        return
    current = start
    travel = 0.0
    for work_point in component_points:
        travel += travel_seconds(current, work_point)
        current = work_point
    travel += travel_seconds(current, finish)
    objective_seconds = sum(component_seconds)
    profile["effective_time_estimate"] = {
        "mode": "manual_service_point_materialized",
        "travel_to_work_seconds": travel_seconds(start, component_points[0]),
        "work_internal_travel_seconds": 0.0 if len(component_points) <= 1 else None,
        "work_to_turnin_seconds": travel_seconds(component_points[-1], finish),
        "total_travel_seconds": travel,
        "objective_seconds": objective_seconds,
        "estimated_total_seconds": travel + objective_seconds,
        "calculation": {
            "formula": "start_to_manual_service_point + manual_service_seconds + service_point_to_turnin",
            "inputs": {
                "component_points": [list(v) for v in component_points],
                "component_seconds": component_seconds,
            },
            "result": travel + objective_seconds,
            "unit": "seconds",
            "source": "manual_component_point_materialization",
            "quality": "manual_verified_mechanic",
        },
        "source": "manual_component_point_materialization",
    }
