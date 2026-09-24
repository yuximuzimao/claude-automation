from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.character_profiles import load_all_character_profiles, validate_route_profile_character_reference
from lib.route_continuity import evaluate_route_program_continuity, evaluate_standalone_continuity
from lib.route_dependencies import (
    build_dependency_index,
    build_profile_dependency_manifest,
    common_source_inventory,
    compose_fingerprint,
)
from lib.route_profiles import load_all_route_profiles, load_route_profile, validate_route_profile
from lib.route_programs import load_all_route_programs
from lib.route_movement import (
    evaluate_profile_movement,
    evaluate_route_program_movement,
    program_member_movement_report,
)
from lib.route_replay import replay_route_profile, replay_summary
from lib.route_service_context import evaluate_profile_service_context
from lib.route_timing import evaluate_profile_timing, evaluate_route_program_timing, load_timing_inputs
from lib.route_xp import evaluate_profile_xp, evaluate_route_program_xp, load_xp_model_config
from lib.route_economy import evaluate_profile_economy, evaluate_route_program_economy, load_economy_inputs
from lib.route_review_trigger import evaluate_review_trigger, load_review_trigger_config
from lib.route_display import project_route_display
from lib.route_publisher_payload import build_publisher_payload, load_route_ui_config
from lib.route_player_assets import WORKBENCH_NAME, PLAYER_VIEW_DIRNAME, evaluate_player_assets, write_player_assets
from lib.route_final_audit import evaluate_profile_final_audit
from lib.task_cards import load_task_card


class PipelineBlocked(RuntimeError):
    pass


def stage(
    name: str,
    *,
    implementation_status: str,
    evaluation_status: str,
    publish_gate_applies: bool = True,
    detail: Any = None,
) -> dict[str, Any]:
    """Report stage capability separately from the current artifact evaluation.

    ``implementation_status`` answers whether this lifecycle stage is actually implemented and
    wired into the sole rebuild path. ``evaluation_status`` answers what happened when the current
    Profile/Program data was evaluated. Business data may legitimately be blocked even when the
    stage implementation is complete; architecture migration must never repair route truth merely
    to turn an evaluation green.

    ``publish_gate_applies`` is execution-context routing, not a success override. For example,
    a Program member's standalone Stage-3 probe may expose requirements, while Stage 4 immediately
    reruns the same Stage-3 engine with the actual Program state; only the context-resolved result
    belongs to that Program's publish gate.

    ``status`` remains a temporary compatibility projection for existing callers; new architecture
    code/tests must read the explicit fields.
    """
    if implementation_status not in {"implemented", "not_implemented"}:
        raise ValueError(f"invalid implementation_status: {implementation_status}")
    if evaluation_status not in {"pass", "requirements", "blocked", "not_run"}:
        raise ValueError(f"invalid evaluation_status: {evaluation_status}")
    if implementation_status == "not_implemented" and evaluation_status != "not_run":
        raise ValueError("unimplemented stages must use evaluation_status=not_run")
    compat_status = {
        "pass": "ok",
        "requirements": "requirements",
        "blocked": "blocked",
        "not_run": "blocked",
    }[evaluation_status]
    row: dict[str, Any] = {
        "name": name,
        "implementation_status": implementation_status,
        "evaluation_status": evaluation_status,
        "publish_gate_applies": publish_gate_applies,
        "status": compat_status,
    }
    if detail is not None:
        row["detail"] = detail
    return row


def _inventory_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    inventory = manifest["source_inventory"]
    return {
        "schemas": inventory["schemas"],
        "rules": {
            "count": len(inventory["rules"]),
            "fingerprint": compose_fingerprint([(row["path"], row["hash"]) for row in inventory["rules"]]),
        },
        "observations": {
            "count": len(inventory["observations"]),
            "fingerprint": compose_fingerprint(
                [(row["path"], row["hash"]) for row in inventory["observations"]]
            ),
        },
        "external_timing_inputs": {
            "count": len(inventory["external_timing_inputs"]),
            "fingerprint": compose_fingerprint(
                [(row["path"], row["hash"]) for row in inventory["external_timing_inputs"]]
            ),
        },
        "external_xp_inputs": {
            "count": len(inventory["external_xp_inputs"]),
            "fingerprint": compose_fingerprint(
                [(row["path"], row["hash"]) for row in inventory["external_xp_inputs"]]
            ),
        },
        "character_profile": inventory["character_profile"],
        "route_ui": inventory["route_ui"],
    }


def _stage3_input_fingerprint(manifest: dict[str, Any]) -> str:
    profile_sections = manifest["profile"]["sections"]
    relevant_rule_paths = {
        "docs/rules/route-profile-and-lifecycle.md",
        "docs/task-library/README.md",
        "docs/verified-routes/ROUTE-DESIGN-PROCESS.md",
    }
    relevant_rules = [
        (row["path"], row["hash"])
        for row in manifest["source_inventory"]["rules"]
        if row["path"] in relevant_rule_paths
    ]
    return compose_fingerprint(
        {
            "contract_version": 2,
            "profile": {
                key: profile_sections[key]
                for key in ("version", "scope", "entry_requirements", "task_ids", "actions")
            },
            "task_cards": {
                task_id: {
                    key: row["sections"][key]
                    for key in ("identity", "availability", "rewards")
                    if key in row["sections"]
                }
                for task_id, row in sorted(manifest["task_cards"].items())
            },
            "character_profile": manifest["source_inventory"]["character_profile"]["hash"],
            "schemas": {
                key: manifest["source_inventory"]["schemas"][key]["hash"]
                for key in ("task_card", "route_profile", "character_profile")
            },
            "rules": relevant_rules,
        }
    )


def _stage4_input_fingerprint(
    *,
    dependency_manifest: dict[str, Any],
    program_id: str | None,
    stage3_input_fingerprints: dict[str, str],
) -> str:
    relevant_rule_paths = {
        "docs/rules/route-profile-and-lifecycle.md",
        "docs/rules/route-atlas-optimization.md",
        "docs/verified-routes/ROUTE-DESIGN-PROCESS.md",
    }
    relevant_rules = [
        (row["path"], row["hash"])
        for row in dependency_manifest["source_inventory"]["rules"]
        if row["path"] in relevant_rule_paths
    ]
    program_fingerprint: dict[str, Any] | None = None
    if program_id is not None:
        program_row = dependency_manifest["route_programs"][program_id]
        program_fingerprint = {
            key: program_row["sections"][key]
            for key in ("version", "status", "scope", "entry_state_contract", "profile_ids")
        }
    return compose_fingerprint(
        {
            "contract_version": 1,
            "program_id": program_id,
            "program": program_fingerprint,
            "stage3_inputs": dict(sorted(stage3_input_fingerprints.items())),
            "rules": relevant_rules,
        }
    )


def _program_stage3_inputs(
    *,
    program: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
    programs: dict[str, dict[str, Any]],
    character_profiles: dict[str, dict[str, Any]],
    current_profile_id: str,
    current_cards: dict[int, dict[str, Any]],
    current_character_profile: dict[str, Any],
    current_stage3_fingerprint: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Prepare Stage 3 inputs for Program-order replay without pre-replaying members.

    Stage 4 owns only Program order/boundaries. The actual state transition for every member
    remains in ``replay_route_profile`` so task/hearth/flight semantics have one execution path.
    """

    shared_inventory = common_source_inventory()
    replay_inputs: dict[str, dict[str, Any]] = {}
    fingerprints: dict[str, str] = {}
    for member_id in program["profile_ids"]:
        if member_id == current_profile_id:
            replay_inputs[member_id] = {
                "task_cards": current_cards,
                "character_profile": current_character_profile,
            }
            fingerprints[member_id] = current_stage3_fingerprint
            continue
        member = profiles[member_id]
        member_cards = {
            int(task_id): load_task_card(int(task_id), validate=True)
            for task_id in member["task_ids"]
        }
        validate_route_profile(member, expected_profile_id=member_id, known_task_cards=member_cards)
        member_manifest = build_profile_dependency_manifest(
            member_id,
            profile=member,
            cards=member_cards,
            programs=programs,
            shared_source_inventory=shared_inventory,
        )
        member_character_profile = character_profiles[member["scope"]["character_profile"]]
        replay_inputs[member_id] = {
            "task_cards": member_cards,
            "character_profile": member_character_profile,
        }
        fingerprints[member_id] = _stage3_input_fingerprint(member_manifest)
    return replay_inputs, fingerprints


def audit_profile(
    profile_id: str,
    *,
    xp_input: dict[str, Any] | None = None,
    economy_input: dict[str, Any] | None = None,
    review_input: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = load_route_profile(profile_id, validate=True, validate_task_cards=False)
    cards = {int(task_id): load_task_card(int(task_id), validate=True) for task_id in profile["task_ids"]}
    validate_route_profile(profile, expected_profile_id=profile_id, known_task_cards=cards)

    stages: list[dict[str, Any]] = []

    # Stage 1: dependency discovery and atomic fingerprints. This stage owns no downstream business
    # interpretation. It inventories stable IDs and section hashes so later stages can compose only
    # the exact inputs they consume instead of invalidating every model on any file change.
    dependency_index = build_dependency_index()
    dependency_manifest = build_profile_dependency_manifest(profile_id, profile=profile, cards=cards)
    unknown_program_refs = dependency_index["unknown_program_profile_refs"]
    stages.append(
        stage(
            "dependency_fingerprint",
            implementation_status="implemented",
            evaluation_status="blocked" if unknown_program_refs else "pass",
            detail={
                "root_fingerprint": dependency_manifest["root_fingerprint"],
                "manifest_fingerprint": dependency_manifest["manifest_fingerprint"],
                "task_card_count": len(dependency_manifest["task_cards"]),
                "route_program_ids": sorted(dependency_manifest["route_programs"]),
                "reverse_index_summary": dependency_index["summary"],
                "unknown_program_profile_refs": unknown_program_refs,
                "source_inventory": _inventory_summary(dependency_manifest),
            },
        )
    )

    # Stage 2: validate the Route Profile itself plus every formal Route Program against its own
    # schema and member Profile contracts. A Profile may be intentionally standalone; membership is
    # not required. Program continuity is Stage 4, not part of this shape/identity gate.
    character_profiles = load_all_character_profiles(validate=True)
    validate_route_profile_character_reference(profile, character_profiles)
    programs = load_all_route_programs(validate=True, validate_profiles=True)
    profile_program_ids = sorted(
        program_id
        for program_id, program in programs.items()
        if profile_id in program["profile_ids"] and program.get("status") != "retired"
    )
    stages.append(
        stage(
            "profile_program_contract",
            implementation_status="implemented",
            evaluation_status="pass",
            detail={
                "profile_contract": "valid",
                "profile_version": profile["version"],
                "character_profile_id": profile["scope"]["character_profile"],
                "character_profile_contract": "valid",
                "route_program_count": len(programs),
                "route_program_ids": profile_program_ids,
                "standalone_profile": not profile_program_ids,
            },
        )
    )

    # Stage 3: the only Route Replay / action-time Availability evaluator. XP-dependent gates are
    # intentionally emitted as deferred inputs for Stage 8; this stage must not duplicate XP logic.
    character_profile_id = profile["scope"]["character_profile"]
    character_profile = character_profiles[character_profile_id]
    replay = replay_route_profile(
        profile,
        task_cards=cards,
        character_profile=character_profile,
    )
    replay_data = replay_summary(replay)
    stage3_input_fingerprint = _stage3_input_fingerprint(dependency_manifest)
    replay_errors = [item for item in replay.issues if item.get("severity") == "error"]
    replay_requirements = [item for item in replay.issues if item.get("severity") == "requirement"]
    accept_action_count = sum(1 for action in profile["actions"] if action["kind"] == "accept")
    stages.append(
        stage(
            "availability_route_replay",
            implementation_status="implemented",
            evaluation_status="blocked" if replay_errors else ("requirements" if replay_requirements or replay.external_state_requirements else "pass"),
            publish_gate_applies=not profile_program_ids,
            detail={
                "input_fingerprint": stage3_input_fingerprint,
                "character_profile_id": character_profile_id,
                "availability_event_count": len(replay.availability_events),
                "accept_action_count": accept_action_count,
                "hard_errors": replay_errors,
                "requirement_count": len(replay_requirements),
                "external_state_requirement_count": len(replay.external_state_requirements),
                "deferred_gate_count": len(replay.deferred_gates),
                "quest_log_peak_upper_bound": replay.quest_log_peak_upper_bound,
                "required_entry_flight_points": sorted(replay.required_entry_flight_points),
                "required_entry_hearth_locations": sorted(replay.required_entry_hearth_locations),
            },
        )
    )

    # Stage 4: the only cross-Profile continuity evaluator. It consumes Stage 3 state and
    # Program order; it does not calculate XP/level values (Stage 8 owns those).
    continuity_reports: list[dict[str, Any]] = []
    continuity_by_program: dict[str, dict[str, Any]] = {}
    program_replay_inputs_by_id: dict[str, dict[str, dict[str, Any]]] = {}
    if profile_program_ids:
        all_profiles = load_all_route_profiles(validate=True, validate_task_cards=False)
        for program_id in profile_program_ids:
            program = programs[program_id]
            member_replay_inputs, member_stage3_fingerprints = _program_stage3_inputs(
                program=program,
                profiles=all_profiles,
                programs=programs,
                character_profiles=character_profiles,
                current_profile_id=profile_id,
                current_cards=cards,
                current_character_profile=character_profile,
                current_stage3_fingerprint=stage3_input_fingerprint,
            )
            program_replay_inputs_by_id[program_id] = member_replay_inputs
            continuity = evaluate_route_program_continuity(program, all_profiles, member_replay_inputs)
            continuity["input_fingerprint"] = _stage4_input_fingerprint(
                dependency_manifest=dependency_manifest,
                program_id=program_id,
                stage3_input_fingerprints=member_stage3_fingerprints,
            )
            continuity_by_program[program_id] = continuity
            continuity_reports.append(continuity)
    else:
        continuity = evaluate_standalone_continuity(profile, replay)
        continuity["input_fingerprint"] = _stage4_input_fingerprint(
            dependency_manifest=dependency_manifest,
            program_id=None,
            stage3_input_fingerprints={profile_id: stage3_input_fingerprint},
        )
        continuity_reports.append(continuity)

    continuity_blocked = [row for row in continuity_reports if row["status"] == "blocked"]
    continuity_requirements = [row for row in continuity_reports if row["status"] == "requirements"]
    stages.append(
        stage(
            "cross_profile_continuity",
            implementation_status="implemented",
            evaluation_status="blocked" if continuity_blocked else ("requirements" if continuity_requirements else "pass"),
            detail={
                "reports": continuity_reports,
                "report_count": len(continuity_reports),
                "blocked_report_count": len(continuity_blocked),
                "requirements_report_count": len(continuity_requirements),
                "note": "Unresolved entry requirements remain explicit inputs for CURRENT/Review Trigger; only continuity contradictions block Stage 4 itself.",
            },
        )
    )

    movement_reports: list[dict[str, Any]] = []
    movement_by_program: dict[str, dict[str, Any]] = {}
    local_movement_report = evaluate_profile_movement(profile)
    if profile_program_ids:
        all_profiles_for_movement = load_all_route_profiles(validate=True, validate_task_cards=False)
        for program_id in profile_program_ids:
            program_movement = evaluate_route_program_movement(programs[program_id], all_profiles_for_movement)
            movement_by_program[program_id] = program_movement
            movement_reports.append(program_movement)
    else:
        movement_reports.append(local_movement_report)

    movement_blocked = [row for row in movement_reports if row["status"] == "blocked"]
    movement_requirements = [row for row in movement_reports if row["status"] == "requirements"]
    stages.append(
        stage(
            "canonical_spatial_movement",
            implementation_status="implemented",
            evaluation_status="blocked" if movement_blocked else ("requirements" if movement_requirements else "pass"),
            detail={
                "local_profile_report": local_movement_report,
                "reports": movement_reports,
                "report_count": len(movement_reports),
                "blocked_report_count": len(movement_blocked),
                "requirements_report_count": len(movement_requirements),
                "note": "Stage 5 is the sole interpreter of visit/edge movement, including Program boundaries. Legacy location.transport is migration evidence only; downstream stages must consume this fresh report rather than reinterpret the old field.",
            },
        )
    )

    service_reports: list[dict[str, Any]] = []
    service_by_program: dict[str, dict[str, Any]] = {}
    if profile_program_ids:
        for program_id in profile_program_ids:
            contextual_movement = program_member_movement_report(movement_by_program[program_id], profile_id)
            service_context = evaluate_profile_service_context(profile, contextual_movement)
            service_context["program_id"] = program_id
            service_by_program[program_id] = service_context
            service_reports.append(service_context)
    else:
        service_context = evaluate_profile_service_context(profile, local_movement_report)
        service_reports.append(service_context)

    service_blocked = [row for row in service_reports if row["status"] == "blocked"]
    service_requirements = [row for row in service_reports if row["status"] == "requirements"]
    stages.append(
        stage(
            "service_context",
            implementation_status="implemented",
            evaluation_status="blocked" if service_blocked else ("requirements" if service_requirements else "pass"),
            detail={
                "reports": service_reports,
                "report_count": len(service_reports),
                "blocked_report_count": len(service_blocked),
                "requirements_report_count": len(service_requirements),
                "note": (
                    "Stage 6 derives foreground services/Target Clusters/visit-level Spatial Instances from "
                    "structured objective actions plus the context-resolved Stage 5 member view. Route-only "
                    "service_overrides are allowed only for non-reconstructable background coverage or proven "
                    "shared service; guide, presentation notes, old target-cluster files and generated HTML are not runtime inputs."
                ),
            },
        )
    )

    timing_inputs = load_timing_inputs()
    timing_reports: list[dict[str, Any]] = []
    if profile_program_ids:
        for program_id in profile_program_ids:
            replay_inputs = program_replay_inputs_by_id[program_id]
            timing_reports.append(
                evaluate_route_program_timing(
                    programs[program_id],
                    all_profiles_for_movement,
                    task_cards_by_profile={
                        member_id: replay_inputs[member_id]["task_cards"]
                        for member_id in programs[program_id]["profile_ids"]
                    },
                    character_profiles_by_profile={
                        member_id: replay_inputs[member_id]["character_profile"]
                        for member_id in programs[program_id]["profile_ids"]
                    },
                    program_movement_report=movement_by_program[program_id],
                    continuity_report=continuity_by_program[program_id],
                    timing_inputs=timing_inputs,
                )
            )
    else:
        timing_reports.append(
            evaluate_profile_timing(
                profile,
                task_cards=cards,
                movement_report=local_movement_report,
                service_report=service_reports[0],
                character_profile=character_profile,
                action_execution=replay.action_execution,
                timing_inputs=timing_inputs,
            )
        )

    timing_blocked = [row for row in timing_reports if row["status"] == "blocked"]
    timing_requirements = [row for row in timing_reports if row["status"] == "requirements"]
    stages.append(
        stage(
            "derived_timing",
            implementation_status="implemented",
            evaluation_status="blocked" if timing_blocked else ("requirements" if timing_requirements else "pass"),
            detail={
                "reports": timing_reports,
                "report_count": len(timing_reports),
                "blocked_report_count": len(timing_blocked),
                "requirements_report_count": len(timing_requirements),
                "note": (
                    "Stage 7 is the sole Timing resolver/builder. It consumes Stage 4 action execution, "
                    "Stage 5 canonical movement/Program boundaries, Stage 6 service context, reviewed Timing "
                    "configs, Effective Quest Source inputs, Leatrix bindings and eligible Observations. Missing "
                    "inputs remain requirements; old step totals and prose are never fallback timing truth."
                ),
            },
        )
    )
    xp_model_config = load_xp_model_config()
    xp_reports: list[dict[str, Any]] = []
    supplied_xp_input = xp_input or {}
    if profile_program_ids:
        program_inputs = supplied_xp_input.get("programs") or {}
        for program_id in profile_program_ids:
            program_xp_input = program_inputs.get(program_id) or {}
            replay_inputs = program_replay_inputs_by_id[program_id]
            xp_reports.append(
                evaluate_route_program_xp(
                    programs[program_id],
                    all_profiles_for_movement,
                    task_cards_by_profile={
                        member_id: replay_inputs[member_id]["task_cards"]
                        for member_id in programs[program_id]["profile_ids"]
                    },
                    continuity_report=continuity_by_program[program_id],
                    entry_state=program_xp_input.get("entry_state"),
                    external_xp_upper_bound_by_profile=program_xp_input.get("external_xp_upper_bound_by_profile"),
                    model_config=xp_model_config,
                )
            )
    else:
        profile_xp_input = ((supplied_xp_input.get("profiles") or {}).get(profile_id) or {})
        xp_reports.append(
            evaluate_profile_xp(
                profile,
                task_cards=cards,
                action_execution=dict(replay.action_execution),
                deferred_gates=list(replay.deferred_gates),
                entry_state=profile_xp_input.get("entry_state"),
                external_xp_upper_bound_by_character=profile_xp_input.get("external_xp_upper_bound_by_character"),
                model_config=xp_model_config,
            )
        )

    xp_blocked = [row for row in xp_reports if row["status"] == "blocked"]
    xp_requirements = [row for row in xp_reports if row["status"] == "requirements"]
    stages.append(
        stage(
            "derived_xp",
            implementation_status="implemented",
            evaluation_status="blocked" if xp_blocked else ("requirements" if xp_requirements else "pass"),
            detail={
                "reports": xp_reports,
                "report_count": len(xp_reports),
                "blocked_report_count": len(xp_blocked),
                "requirements_report_count": len(xp_requirements),
                "model_id": xp_model_config["model_id"],
                "note": (
                    "Stage 8 is the sole level/XP execution stage. It consumes Task Card quest_level/full_xp, "
                    "Stage 4 action execution plus deferred min-level gates, an explicit machine XP entry state, "
                    "and the versioned XP model config. Guaranteed progression excludes unstable natural XP; "
                    "risk upper bounds remain UNKNOWN unless explicitly supplied. Route titles/subtitles and old "
                    "per-zone XP budgets are never fallback inputs."
                ),
            },
        )
    )
    economy_inputs = load_economy_inputs()
    economy_model_config = economy_inputs["model_config"]
    economy_observations = economy_inputs["economy_observations"]
    market_valuations = economy_inputs["market_valuations"]
    economy_reports: list[dict[str, Any]] = []
    supplied_economy_input = economy_input or {}
    if profile_program_ids:
        program_economy_inputs = supplied_economy_input.get("programs") or {}
        timing_by_program = {str(row["program_id"]): row for row in timing_reports}
        xp_by_program = {str(row["program_id"]): row for row in xp_reports}
        for program_id in profile_program_ids:
            replay_inputs = program_replay_inputs_by_id[program_id]
            program_economy_input = program_economy_inputs.get(program_id) or {}
            economy_reports.append(
                evaluate_route_program_economy(
                    programs[program_id],
                    all_profiles_for_movement,
                    task_cards_by_profile={
                        member_id: replay_inputs[member_id]["task_cards"]
                        for member_id in programs[program_id]["profile_ids"]
                    },
                    xp_report=xp_by_program[program_id],
                    timing_report=timing_by_program[program_id],
                    cost_input_by_profile=program_economy_input.get("cost_input_by_profile"),
                    economy_observations=economy_observations,
                    market_valuations=market_valuations,
                    model_config=economy_model_config,
                )
            )
    else:
        profile_economy_input = ((supplied_economy_input.get("profiles") or {}).get(profile_id) or {})
        economy_reports.append(
            evaluate_profile_economy(
                profile,
                task_cards=cards,
                xp_report=xp_reports[0],
                timing_report=timing_reports[0],
                cost_input=profile_economy_input.get("cost_input"),
                economy_observations=economy_observations,
                market_valuations=market_valuations,
                model_config=economy_model_config,
            )
        )

    economy_blocked = [row for row in economy_reports if row["status"] == "blocked"]
    economy_requirements = [row for row in economy_reports if row["status"] == "requirements"]
    stages.append(
        stage(
            "derived_economy",
            implementation_status="implemented",
            evaluation_status="blocked" if economy_blocked else ("requirements" if economy_requirements else "pass"),
            detail={
                "reports": economy_reports,
                "report_count": len(economy_reports),
                "blocked_report_count": len(economy_blocked),
                "requirements_report_count": len(economy_requirements),
                "model_id": economy_model_config["model_id"],
                "note": (
                    "Stage 9 is the sole Derived Economy/G-hour builder. It consumes Task Card reward facts, "
                    "fresh Stage 8 per-character turn-in levels, fresh Stage 7 Timing for G/hour, the versioned "
                    "Economy model, exact-version clean Economy Observations, market valuations, and explicit scoped cost inputs. Missing stable max-level reward flags, cost "
                    "coverage, or timing remain requirements; old route-atlas economy summaries are not runtime truth."
                ),
            },
        )
    )
    review_model_config = load_review_trigger_config()
    review_reports: list[dict[str, Any]] = []
    if profile_program_ids:
        timing_by_program_for_review = {str(row["program_id"]): row for row in timing_reports}
        xp_by_program_for_review = {str(row["program_id"]): row for row in xp_reports}
        economy_by_program_for_review = {str(row["program_id"]): row for row in economy_reports}
        for program_id in profile_program_ids:
            review_reports.append(
                evaluate_review_trigger(
                    target_kind="program",
                    target_id=program_id,
                    target_version=int(programs[program_id]["version"]),
                    upstream_statuses={
                        "cross_profile_continuity": str(continuity_by_program[program_id]["status"]),
                        "canonical_spatial_movement": str(movement_by_program[program_id]["status"]),
                        "service_context": str(service_by_program[program_id]["status"]),
                        "derived_timing": str(timing_by_program_for_review[program_id]["status"]),
                        "derived_xp": str(xp_by_program_for_review[program_id]["status"]),
                        "derived_economy": str(economy_by_program_for_review[program_id]["status"]),
                    },
                    review_input=review_input,
                    model_config=review_model_config,
                )
            )
    else:
        standalone_replay_status = (
            "blocked"
            if replay_errors
            else ("requirements" if replay_requirements or replay.external_state_requirements else "pass")
        )
        review_reports.append(
            evaluate_review_trigger(
                target_kind="profile",
                target_id=profile_id,
                target_version=int(profile["version"]),
                upstream_statuses={
                    "availability_route_replay": standalone_replay_status,
                    "cross_profile_continuity": str(continuity_reports[0]["status"]),
                    "canonical_spatial_movement": str(movement_reports[0]["status"]),
                    "service_context": str(service_reports[0]["status"]),
                    "derived_timing": str(timing_reports[0]["status"]),
                    "derived_xp": str(xp_reports[0]["status"]),
                    "derived_economy": str(economy_reports[0]["status"]),
                },
                review_input=review_input,
                model_config=review_model_config,
            )
        )

    review_blocked = [row for row in review_reports if row["status"] == "blocked"]
    review_requirements = [row for row in review_reports if row["status"] == "requirements"]
    stages.append(
        stage(
            "review_trigger",
            implementation_status="implemented",
            evaluation_status="blocked" if review_blocked else ("requirements" if review_requirements else "pass"),
            detail={
                "reports": review_reports,
                "report_count": len(review_reports),
                "blocked_report_count": len(review_blocked),
                "requirements_report_count": len(review_requirements),
                "model_id": review_model_config["model_id"],
                "note": (
                    "Stage 10 is a diagnosis-only gate. It requires fresh upstream Stage 3/4-9 results plus an "
                    "explicit version-bound review context with complete trigger coverage. Missing context or "
                    "non-fresh upstream inputs remain blocked_unknown; Selection triggers only request Selection "
                    "Review, and Optimization Hard Validator FAIL only requests Optimization Review. This stage "
                    "never chooses now/later/never, deletes tasks, edits Task Cards, or reorders a frozen Profile."
                ),
            },
        )
    )
    display_reports: list[dict[str, Any]] = []
    if profile_program_ids:
        timing_by_program_for_display = {str(row["program_id"]): row for row in timing_reports}
        review_by_program_for_display = {str(row["target_id"]): row for row in review_reports if row.get("kind") == "program"}
        for program_id in profile_program_ids:
            member_movement = program_member_movement_report(movement_by_program[program_id], profile_id)
            member_timing = (timing_by_program_for_display[program_id].get("member_reports") or {}).get(profile_id)
            if not isinstance(member_timing, dict):
                member_timing = {"status": "blocked", "complete": False, "steps": [], "input_fingerprint": None}
            program_review = review_by_program_for_display.get(program_id)
            if not isinstance(program_review, dict):
                program_review = {"status": "blocked", "input_fingerprint": None}
            display_report = project_route_display(
                profile,
                cards=cards,
                movement_report=member_movement,
                timing_report=member_timing,
                upstream_statuses={
                    "canonical_spatial_movement": str(member_movement.get("status") or "blocked"),
                    "derived_timing": str(member_timing.get("status") or "blocked"),
                    "review_trigger": str(program_review.get("status") or "blocked"),
                },
                upstream_fingerprints={
                    "movement": member_movement.get("input_fingerprint"),
                    "timing": member_timing.get("input_fingerprint"),
                    "review": program_review.get("input_fingerprint"),
                },
            )
            display_report["program_id"] = program_id
            display_reports.append(display_report)
    else:
        display_reports.append(
            project_route_display(
                profile,
                cards=cards,
                movement_report=local_movement_report,
                timing_report=timing_reports[0],
                upstream_statuses={
                    "canonical_spatial_movement": str(local_movement_report.get("status") or "blocked"),
                    "derived_timing": str(timing_reports[0].get("status") or "blocked"),
                    "review_trigger": str(review_reports[0].get("status") or "blocked"),
                },
                upstream_fingerprints={
                    "movement": local_movement_report.get("input_fingerprint"),
                    "timing": timing_reports[0].get("input_fingerprint"),
                    "review": review_reports[0].get("input_fingerprint"),
                },
            )
        )

    display_blocked = [row for row in display_reports if row["status"] == "blocked"]
    display_requirements = [row for row in display_reports if row["status"] == "requirements"]
    stages.append(
        stage(
            "display_presentation",
            implementation_status="implemented",
            evaluation_status="blocked" if display_blocked else ("requirements" if display_requirements else "pass"),
            detail={
                "reports": display_reports,
                "report_count": len(display_reports),
                "blocked_report_count": len(display_blocked),
                "requirements_report_count": len(display_requirements),
                "note": (
                    "Stage 11 is the sole semantic player-display projection. It consumes Route Profile atomic "
                    "actions/stepGroups/geometry, current Task Card identity/fivebox/presentation, fresh Stage 7 "
                    "Timing values and upstream Stage 5/10 freshness. It emits structured locations/actions/steps/" 
                    "task presentations only: no HTML/CSS and no legacy workbench, semantic prose or route-model "
                    "files may be parsed as fallback truth."
                ),
            },
        )
    )
    route_ui = load_route_ui_config(profile_id)
    publisher_payloads = [
        build_publisher_payload(display_report, route_ui=route_ui)
        for display_report in display_reports
    ]
    publisher_blocked = [row for row in publisher_payloads if row["status"] == "blocked"]
    publisher_requirements = [row for row in publisher_payloads if row["status"] == "requirements"]
    stages.append(
        stage(
            "publisher_payload",
            implementation_status="implemented",
            evaluation_status="blocked" if publisher_blocked else ("requirements" if publisher_requirements else "pass"),
            detail={
                "payloads": publisher_payloads,
                "payload_count": len(publisher_payloads),
                "publishable_count": sum(1 for row in publisher_payloads if row["publishable"] is True),
                "blocked_payload_count": len(publisher_blocked),
                "requirements_payload_count": len(publisher_requirements),
                "note": (
                    "Stage 12 is the sole pure-JSON Publisher Payload builder. It consumes only Stage 11 semantic "
                    "display reports plus profile-bound Route UI configuration. It never reloads Route Profile, "
                    "Task Cards, old Timing route-model files, workbench JSON, semantic prose or HTML. Non-pass "
                    "Stage 11 reports may be wrapped for diagnostics but always remain publishable=false."
                ),
            },
        )
    )
    player_assets_report = evaluate_player_assets(publisher_payloads, routes_root=ROOT / "data/routes")
    stages.append(
        stage(
            "html_player_view_assets",
            implementation_status="implemented",
            evaluation_status=str(player_assets_report["status"]),
            detail={
                "report": player_assets_report,
                "note": (
                    "Stage 13 renders both the single workbench HTML and cold-read player views directly from Stage 12 "
                    "Publisher payloads. The HTML embeds the payload at build time and may load only relative maps/ assets "
                    "at runtime; it does not read project JSON, Python, network resources, old workbench JSON, old HTML, "
                    "Route Profiles or Task Cards. Diagnostic rendering remains available for non-publishable payloads, "
                    "but the formal write gate refuses them."
                ),
            },
        )
    )
    final_audit_report = evaluate_profile_final_audit(
        profile_id=profile_id,
        profile_version=int(profile["version"]),
        root_fingerprint=str(dependency_manifest["root_fingerprint"]),
        prerequisite_stages=list(stages),
        display_reports=display_reports,
        publisher_payloads=publisher_payloads,
        player_assets_report=player_assets_report,
        source_root=ROOT,
    )
    stages.append(
        stage(
            "mechanical_audit_cold_read",
            implementation_status="implemented",
            evaluation_status=str(final_audit_report["status"]),
            detail={
                "report": final_audit_report,
                "note": (
                    "Stage 14 is the final mechanical/cold-read gate. It does not re-run or infer Stage 1-13 business "
                    "logic: it verifies their implementation/evaluation states, the Stage 11→12→13 fingerprint chain, "
                    "active-consumer legacy boundaries, and final player-view readability. Current business blocked/"
                    "requirements remain explicit; project cutover requires a separate complete set of per-Profile final "
                    "audit reports and must not be inferred from one Profile."
                ),
            },
        )
    )

    unimplemented = [row["name"] for row in stages if row["implementation_status"] != "implemented"]
    evaluation_blocked = [
        row["name"]
        for row in stages
        if row["publish_gate_applies"] and row["evaluation_status"] == "blocked"
    ]
    evaluation_requirements = [
        row["name"]
        for row in stages
        if row["publish_gate_applies"] and row["evaluation_status"] == "requirements"
    ]
    publish_blocked = unimplemented + evaluation_blocked + evaluation_requirements
    return {
        "profile_id": profile_id,
        "profile_version": profile["version"],
        "root_fingerprint": dependency_manifest["root_fingerprint"],
        "task_card_count": len(profile["task_ids"]),
        "implementation_status": "complete" if not unimplemented else "incomplete",
        "artifact_evaluation_status": "blocked" if evaluation_blocked else ("requirements" if evaluation_requirements else "pass"),
        "status": "ready" if not publish_blocked else "blocked",
        "unimplemented_stages": unimplemented,
        "artifact_blocked_stages": evaluation_blocked,
        "artifact_requirement_stages": evaluation_requirements,
        "blocked_stages": publish_blocked,
        "stages": stages,
        "dependency_manifest": dependency_manifest,
        "route_replay": replay_data,
        "cross_profile_continuity": continuity_reports,
        "canonical_spatial_movement": movement_reports,
        "service_context": service_reports,
        "derived_timing": timing_reports,
        "derived_xp": xp_reports,
        "derived_economy": economy_reports,
        "review_trigger": review_reports,
        "display_presentation": display_reports,
        "publisher_payload": publisher_payloads,
        "html_player_view_assets": player_assets_report,
        "mechanical_audit_cold_read": final_audit_report,
    }


def _generated_asset_hashes(output_dir: Path) -> dict[str, str]:
    paths = [output_dir / WORKBENCH_NAME]
    player_dir = output_dir / PLAYER_VIEW_DIRNAME
    if player_dir.exists():
        paths.extend(sorted(player_dir.glob("*.md")))
    hashes: dict[str, str] = {}
    for path in paths:
        if path.exists():
            hashes[str(path.relative_to(output_dir))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def verify_generated_product_rebuild(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    """Prove Stage 13 Generated Product can be deleted and deterministically rebuilt."""
    maps_dir = ROOT / "data/routes/maps"
    if not maps_dir.exists():
        raise PipelineBlocked(f"map asset directory missing: {maps_dir}")
    with tempfile.TemporaryDirectory(prefix="wow-route-rebuild-") as tmp:
        output_dir = Path(tmp)
        os.symlink(maps_dir, output_dir / "maps", target_is_directory=True)
        first = write_player_assets(payloads, output_dir=output_dir)
        first_hashes = _generated_asset_hashes(output_dir)
        (output_dir / WORKBENCH_NAME).unlink(missing_ok=True)
        shutil.rmtree(output_dir / PLAYER_VIEW_DIRNAME, ignore_errors=True)
        second = write_player_assets(payloads, output_dir=output_dir)
        second_hashes = _generated_asset_hashes(output_dir)
        if first_hashes != second_hashes:
            raise PipelineBlocked("Generated Product delete/rebuild hash mismatch")
        return {
            "status": "pass",
            "asset_count": len(second_hashes),
            "hashes": second_hashes,
            "workbench_sha256": second["workbench_sha256"],
            "profile_count": second["profile_count"],
            "first_workbench_sha256": first["workbench_sha256"],
        }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "FULL DIAGNOSTIC ONLY. Runs the complete Route Lifecycle audit for one Profile. "
            "Do not use this command for ordinary route updates or Publisher writes; follow "
            "ROUTE-DESIGN-PROCESS.md and run only the owners required by the actual change."
        )
    )
    parser.add_argument("profile_id")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full machine-readable diagnostic report instead of a compact summary.",
    )
    parser.add_argument(
        "--xp-input",
        type=Path,
        help=(
            "Optional Stage 8 runtime/cold-start JSON for this explicit full diagnostic. "
            "Route titles/goals are never parsed as XP input."
        ),
    )
    parser.add_argument(
        "--economy-input",
        type=Path,
        help="Optional Stage 9 scoped cost JSON for this explicit full diagnostic.",
    )
    parser.add_argument(
        "--review-input",
        type=Path,
        help="Optional Stage 10 version-bound review-context JSON for this explicit full diagnostic.",
    )
    args = parser.parse_args()

    xp_input = json.loads(args.xp_input.read_text(encoding="utf-8")) if args.xp_input else None
    economy_input = json.loads(args.economy_input.read_text(encoding="utf-8")) if args.economy_input else None
    review_input = json.loads(args.review_input.read_text(encoding="utf-8")) if args.review_input else None

    report = audit_profile(
        str(args.profile_id),
        xp_input=xp_input,
        economy_input=economy_input,
        review_input=review_input,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"{report['profile_id']} v{report['profile_version']}: {report['status']}")
        for row in report["stages"]:
            print(
                f"- {row['name']}: implementation={row['implementation_status']}; "
                f"evaluation={row['evaluation_status']}"
            )
        if report["blocked_stages"]:
            print("blocked stages: " + ", ".join(report["blocked_stages"]))

    if report["status"] != "ready":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
