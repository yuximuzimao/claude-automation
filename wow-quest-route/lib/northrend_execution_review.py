from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SPECIAL_TASK_CLASSES = {
    "fixed_object_interaction",
    "world_object_collection",
    "world_object_item_collection",
    "scripted_use_or_event",
    "mixed_with_personal_item",
    "item_source_not_in_questie",
}

SPATIAL_KEYWORDS = {
    "cave": ("cave", "cavern", "洞穴", "洞口", "洞内", "洞里", "墓穴", "pit", "坑", "巢"),
    "vertical_layer": ("floor", "basement", "upper", "lower level", "top level", "underground", "上层", "下层", "底层", "顶层", "地下", "一层", "二层", "楼层", "电梯"),
    "cliff_or_mountain": ("cliff", "mountain", "ridge", "悬崖", "峭壁", "山顶", "绕山"),
    "water_or_underwater": ("underwater", "deep-sea", "dive", "water", "水下", "潜水", "深海", "湖中"),
    "bridge_or_crossing": ("bridge", "桥", "crossing"),
    "scripted_transport_or_phase": ("teleporter", "transport", "scripted flight", "scripted_transport", "phased", "phase", "传送", "脚本飞行", "相位", "载具", "vehicle"),
}


def _load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _slot_count(objectives: Any, slot: int) -> int:
    if not isinstance(objectives, dict):
        return 0
    value = objectives.get(slot)
    if not isinstance(value, dict):
        return 0
    return len([key for key in value if isinstance(key, int)])


def detect_execution_risk_signals(raw: dict[Any, Any] | None, task: dict[str, Any]) -> list[str]:
    raw = raw or {}
    objectives = raw.get(10)
    signals: set[str] = set()

    if raw.get(11) and any(_slot_count(objectives, slot) for slot in (1, 2, 3, 4, 5, 6)):
        signals.add("provided_item_with_objective")
    if _slot_count(objectives, 5):
        signals.add("credit_objective")
    if _slot_count(objectives, 6):
        signals.add("spell_objective")
    if raw.get(29) or task.get("extra_objectives"):
        signals.add("hidden_or_extra_objective")

    task_class = str(task.get("task_class") or "")
    if task_class in SPECIAL_TASK_CLASSES:
        signals.add(f"special_task_class:{task_class}")
    for flag in task.get("task_flags") or []:
        if flag in {"active_item_or_spell_use", "escort_or_defense_text"}:
            signals.add(f"task_flag:{flag}")
    for review in task.get("objective_review") or []:
        signals.add(f"objective_review:{review}")

    started_by = raw.get(2)
    if _slot_count(started_by, 3):
        signals.add("item_started_quest")
    if _slot_count(started_by, 2):
        signals.add("object_started_quest")
    return sorted(signals)


def _keyword_present(haystack: str, keyword: str) -> bool:
    needle = keyword.lower()
    if re.fullmatch(r"[a-z0-9 _-]+", needle):
        return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", haystack) is not None
    return needle in haystack


def _spatial_signals(strings: list[str]) -> list[str]:
    haystack = "\n".join(strings).lower()
    found: list[str] = []
    for signal, keywords in SPATIAL_KEYWORDS.items():
        if any(_keyword_present(haystack, keyword) for keyword in keywords):
            found.append(signal)
    return sorted(found)


def _merge_entry(target: dict[int, dict[str, Any]], qid: int, entry: dict[str, Any]) -> None:
    current = target.setdefault(
        qid,
        {
            "decisions": [],
            "facts": [],
            "fivebox_checks": [],
            "mechanism_codes": [],
            "spatial_tags": [],
            "evidence_sources": [],
        },
    )
    entry_decisions = [str(x) for x in entry.get("decisions") or []]
    no_extra_entry = "reviewed_no_extra_note" in entry_decisions and "must_note" not in entry_decisions
    for key in ("decisions", "facts", "fivebox_checks", "mechanism_codes", "spatial_tags", "evidence_sources"):
        if no_extra_entry and key in {"facts", "mechanism_codes", "spatial_tags"}:
            continue
        for value in entry.get(key) or []:
            if value not in current[key]:
                current[key].append(value)


def load_known_reviews(root: Path) -> tuple[dict[int, dict[str, Any]], dict[str, Any]]:
    reviews: dict[int, dict[str, Any]] = {}
    source_counts: Counter[str] = Counter()

    dragon_overrides = _load(root / "data/route-atlas/dragonblight-task-overrides.json", {})
    dragon_foundation = _load(root / "data/route-atlas/dragonblight-task-foundation.json", {"tasks": []})
    dragon_formal = {int(task["quest_id"]) for task in dragon_foundation.get("tasks", []) if isinstance(task.get("quest_id"), int)}
    default_decision = str((dragon_overrides.get("policy") or {}).get("default_included_world_task_note_decision") or "")
    if default_decision == "reviewed_no_extra_note":
        for qid in dragon_formal:
            _merge_entry(reviews, qid, {"decisions": ["reviewed_no_extra_note"], "evidence_sources": ["dragonblight_manual_foundation_review"]})
            source_counts["dragonblight_default_reviewed"] += 1
    for qid_text, note in (dragon_overrides.get("notes") or {}).items():
        qid = int(qid_text)
        decision = str(note.get("decision") or "")
        _merge_entry(
            reviews,
            qid,
            {
                "decisions": [decision] if decision else [],
                "facts": [str(x) for x in note.get("facts") or []],
                "fivebox_checks": [str(x) for x in note.get("verification") or []],
                "evidence_sources": ["dragonblight_task_overrides"],
            },
        )
        source_counts["dragonblight_explicit_notes"] += 1

    borean_override = _load(root / "data/route-atlas/borean-task-overrides.json", {})
    for qid in borean_override.get("reviewed_no_extra_note_ids") or []:
        _merge_entry(
            reviews,
            int(qid),
            {
                "decisions": ["reviewed_no_extra_note"],
                "evidence_sources": ["borean_manual_universe_review"],
            },
        )
        source_counts["borean_reviewed_no_extra_note"] += 1
    for qid_text, note in (borean_override.get("notes") or {}).items():
        _merge_entry(
            reviews,
            int(qid_text),
            {
                "decisions": [str(note.get("decision") or "must_note")],
                "facts": [str(x) for x in note.get("facts") or []],
                "fivebox_checks": [str(x) for x in note.get("fivebox_checks") or []],
                "mechanism_codes": [str(x) for x in note.get("mechanism_codes") or []],
                "spatial_tags": [str(x) for x in note.get("spatial_tags") or []],
                "evidence_sources": [str(x) for x in note.get("evidence_sources") or ["borean_task_overrides"]],
            },
        )
        source_counts["borean_explicit_notes"] += 1

    dalaran_scope = _load(root / "data/route-atlas/dalaran-scope-audit.json", {})
    for qid in dalaran_scope.get("current_formal_ids") or []:
        _merge_entry(
            reviews,
            int(qid),
            {
                "decisions": ["reviewed_no_extra_note"],
                "evidence_sources": ["dalaran_formal_route_human_executability_gate"],
            },
        )
        source_counts["dalaran_formal_reviewed"] += 1
    dalaran_override = _load(root / "data/route-atlas/dalaran-task-overrides.json", {})
    for qid in dalaran_override.get("reviewed_no_extra_note_ids") or []:
        _merge_entry(
            reviews,
            int(qid),
            {
                "decisions": ["reviewed_no_extra_note"],
                "evidence_sources": ["dalaran_manual_universe_review"],
            },
        )
        source_counts["dalaran_reviewed_no_extra_note"] += 1
    for qid_text, note in (dalaran_override.get("notes") or {}).items():
        _merge_entry(
            reviews,
            int(qid_text),
            {
                "decisions": [str(note.get("decision") or "must_note")],
                "facts": [str(x) for x in note.get("facts") or []],
                "fivebox_checks": [str(x) for x in note.get("fivebox_checks") or []],
                "mechanism_codes": [str(x) for x in note.get("mechanism_codes") or []],
                "spatial_tags": [str(x) for x in note.get("spatial_tags") or []],
                "evidence_sources": [str(x) for x in note.get("evidence_sources") or ["dalaran_task_overrides"]],
            },
        )
        source_counts["dalaran_explicit_notes"] += 1

    hrothgar_override = _load(root / "data/route-atlas/hrothgar-task-overrides.json", {})
    for qid_text, note in (hrothgar_override.get("notes") or {}).items():
        _merge_entry(
            reviews,
            int(qid_text),
            {
                "decisions": [str(note.get("decision") or "must_note")],
                "facts": [str(x) for x in note.get("facts") or []],
                "fivebox_checks": [str(x) for x in note.get("fivebox_checks") or []],
                "mechanism_codes": [str(x) for x in note.get("mechanism_codes") or []],
                "spatial_tags": [str(x) for x in note.get("spatial_tags") or []],
                "evidence_sources": [str(x) for x in note.get("evidence_sources") or ["hrothgar_task_overrides"]],
            },
        )
        source_counts["hrothgar_explicit_notes"] += 1

    storm = _load(root / "data/route-atlas/storm-peaks-task-overrides.json", {})
    storm_foundation = _load(root / "data/route-atlas/storm-peaks-task-foundation.json", {})
    for qid in storm.get("reviewed_no_extra_note_ids") or []:
        _merge_entry(
            reviews,
            int(qid),
            {
                "decisions": ["reviewed_no_extra_note"],
                "evidence_sources": ["storm_manual_universe_review"],
            },
        )
        source_counts["storm_reviewed_no_extra_note"] += 1
    for qid in storm_foundation.get("formal_task_ids") or []:
        _merge_entry(
            reviews,
            int(qid),
            {
                "decisions": ["reviewed_no_extra_note"],
                "evidence_sources": ["storm_formal_route_human_executability_gate"],
            },
        )
        source_counts["storm_formal_reviewed"] += 1
    storm_notes = storm.get("mechanism_notes") or {}
    storm_codes = storm.get("mechanism_codes") or {}
    for qid_text in sorted(set(storm_notes) | set(storm_codes), key=int):
        qid = int(qid_text)
        note = storm_notes.get(qid_text)
        codes = [str(x) for x in storm_codes.get(qid_text) or []]
        _merge_entry(
            reviews,
            qid,
            {
                "decisions": ["must_note"],
                "facts": [str(note)] if note else [],
                "mechanism_codes": codes,
                "evidence_sources": ["storm_peaks_task_overrides"],
            },
        )
        source_counts["storm_explicit_notes"] += 1

    grizzly_override = _load(root / "data/route-atlas/grizzly-hills-task-overrides.json", {})
    for qid in grizzly_override.get("reviewed_no_extra_note_ids") or []:
        _merge_entry(
            reviews,
            int(qid),
            {
                "decisions": ["reviewed_no_extra_note"],
                "evidence_sources": ["grizzly_manual_universe_review"],
            },
        )
        source_counts["grizzly_reviewed_no_extra_note"] += 1
    for qid_text, note in (grizzly_override.get("notes") or {}).items():
        qid = int(qid_text)
        _merge_entry(
            reviews,
            qid,
            {
                "decisions": [str(note.get("decision") or "must_note")],
                "facts": [str(x) for x in note.get("facts") or []],
                "fivebox_checks": [str(x) for x in note.get("fivebox_checks") or []],
                "mechanism_codes": [str(x) for x in note.get("mechanism_codes") or []],
                "spatial_tags": [str(x) for x in note.get("spatial_tags") or []],
                "evidence_sources": [str(x) for x in note.get("evidence_sources") or ["grizzly_task_overrides"]],
            },
        )
        source_counts["grizzly_explicit_notes"] += 1

    grizzly = _load(root / "data/route-atlas/grizzly-hills-special-mechanism-audit.json", {})
    grizzly_foundation = _load(root / "data/route-atlas/grizzly-hills-task-foundation.json", {})
    for qid in grizzly_foundation.get("formal_task_ids") or []:
        _merge_entry(
            reviews,
            int(qid),
            {
                "decisions": ["reviewed_no_extra_note"],
                "evidence_sources": ["grizzly_formal_route_human_executability_gate"],
            },
        )
        source_counts["grizzly_formal_reviewed"] += 1
    for row in grizzly.get("rows") or []:
        qid = int(row["quest_id"])
        _merge_entry(
            reviews,
            qid,
            {
                "decisions": ["must_note"] if row.get("player_note_required") else ["reviewed_no_extra_note"],
                "facts": [str(x) for x in row.get("facts") or []],
                "fivebox_checks": [str(row["fivebox_check"])] if row.get("fivebox_check") else [],
                "evidence_sources": ["grizzly_hills_special_mechanism_audit"],
            },
        )
        source_counts["grizzly_explicit_rows"] += 1

    howling = _load(root / "data/route-atlas/howling-fjord-task-overrides.json", {})
    for qid in howling.get("reviewed_no_extra_note_ids") or []:
        _merge_entry(
            reviews,
            int(qid),
            {
                "decisions": ["reviewed_no_extra_note"],
                "evidence_sources": ["howling_manual_universe_review"],
            },
        )
        source_counts["howling_reviewed_no_extra_note"] += 1
    for qid_text, note in (howling.get("notes") or {}).items():
        qid = int(qid_text)
        _merge_entry(
            reviews,
            qid,
            {
                "decisions": [str(note.get("decision") or "must_note")],
                "facts": [str(x) for x in note.get("facts") or []],
                "fivebox_checks": [str(x) for x in note.get("fivebox_checks") or []],
                "mechanism_codes": [str(x) for x in note.get("mechanism_codes") or []],
                "spatial_tags": [str(x) for x in note.get("spatial_tags") or []],
                "evidence_sources": [str(x) for x in note.get("evidence_sources") or ["howling_task_overrides"]],
            },
        )
        source_counts["howling_explicit_notes"] += 1

    icecrown = _load(root / "data/route-atlas/icecrown-task-overrides.json", {})
    for qid in icecrown.get("reviewed_no_extra_note_ids") or []:
        _merge_entry(
            reviews,
            int(qid),
            {
                "decisions": ["reviewed_no_extra_note"],
                "evidence_sources": ["icecrown_manual_low_signal_review"],
            },
        )
        source_counts["icecrown_reviewed_no_extra_note"] += 1
    for qid_text, note in (icecrown.get("notes") or {}).items():
        qid = int(qid_text)
        decision = str(note.get("decision") or "must_note")
        _merge_entry(
            reviews,
            qid,
            {
                "decisions": [decision],
                "facts": [str(x) for x in note.get("facts") or []],
                "fivebox_checks": [str(x) for x in note.get("fivebox_checks") or []],
                "mechanism_codes": [str(x) for x in note.get("mechanism_codes") or []],
                "spatial_tags": [str(x) for x in note.get("spatial_tags") or []],
                "evidence_sources": [str(x) for x in note.get("evidence_sources") or ["icecrown_task_overrides"]],
            },
        )
        source_counts["icecrown_explicit_notes"] += 1

    sholazar = _load(root / "data/route-atlas/sholazar-task-overrides.json", {})
    for qid in sholazar.get("reviewed_no_extra_note_ids") or []:
        _merge_entry(
            reviews,
            int(qid),
            {
                "decisions": ["reviewed_no_extra_note"],
                "evidence_sources": ["sholazar_manual_review"],
            },
        )
        source_counts["sholazar_reviewed_no_extra_note"] += 1
    for qid_text, note in (sholazar.get("notes") or {}).items():
        qid = int(qid_text)
        decision = str(note.get("decision") or "must_note")
        _merge_entry(
            reviews,
            qid,
            {
                "decisions": [decision],
                "facts": [str(x) for x in note.get("facts") or []],
                "fivebox_checks": [str(x) for x in note.get("fivebox_checks") or []],
                "mechanism_codes": [str(x) for x in note.get("mechanism_codes") or []],
                "spatial_tags": [str(x) for x in note.get("spatial_tags") or []],
                "evidence_sources": [str(x) for x in note.get("evidence_sources") or ["sholazar_task_overrides"]],
            },
        )
        source_counts["sholazar_explicit_notes"] += 1

    zuldrak_override = _load(root / "data/route-atlas/zuldrak-task-overrides.json", {})
    for qid in zuldrak_override.get("reviewed_no_extra_note_ids") or []:
        _merge_entry(
            reviews,
            int(qid),
            {
                "decisions": ["reviewed_no_extra_note"],
                "evidence_sources": ["zuldrak_manual_universe_review"],
            },
        )
        source_counts["zuldrak_reviewed_no_extra_note"] += 1
    for qid_text, note in (zuldrak_override.get("notes") or {}).items():
        qid = int(qid_text)
        _merge_entry(
            reviews,
            qid,
            {
                "decisions": [str(note.get("decision") or "must_note")],
                "facts": [str(x) for x in note.get("facts") or []],
                "fivebox_checks": [str(x) for x in note.get("fivebox_checks") or []],
                "mechanism_codes": [str(x) for x in note.get("mechanism_codes") or []],
                "spatial_tags": [str(x) for x in note.get("spatial_tags") or []],
                "evidence_sources": [str(x) for x in note.get("evidence_sources") or ["zuldrak_task_overrides"]],
            },
        )
        source_counts["zuldrak_explicit_notes"] += 1

    zuldrak = _load(root / "data/route-atlas/zuldrak-special-mechanism-audit.json", {})
    for row in zuldrak.get("rows") or []:
        qid = int(row["quest_id"])
        decision = str(row.get("decision") or "")
        facts: list[str] = []
        if row.get("player_operation_fact"):
            facts.append(str(row["player_operation_fact"]))
        facts.extend(str(x) for x in row.get("extra_objective_facts") or [])
        _merge_entry(
            reviews,
            qid,
            {
                "decisions": [decision] if decision else [],
                "facts": facts,
                "fivebox_checks": [str(x) for x in row.get("fivebox_checks") or []],
                "mechanism_codes": [str(x) for x in row.get("mechanism_codes") or []],
                "evidence_sources": ["zuldrak_per_task_human_executability_screen"],
            },
        )
        source_counts["zuldrak_per_task_rows"] += 1

    return reviews, {"source_counts": dict(source_counts)}


def apply_execution_reviews(root: Path, tasks: list[dict[str, Any]], raw_rows: dict[int, dict[Any, Any]]) -> dict[str, Any]:
    known, source_audit = load_known_reviews(root)
    status_counts: Counter[str] = Counter()
    spatial_counts: Counter[str] = Counter()
    by_zone: dict[str, Counter[str]] = defaultdict(Counter)
    review_queue: list[dict[str, Any]] = []

    for task in tasks:
        qid = int(task["quest_id"])
        risk_signals = detect_execution_risk_signals(raw_rows.get(qid), task)
        known_row = known.get(qid, {})
        decisions = known_row.get("decisions") or []
        facts = [str(x) for x in known_row.get("facts") or []]
        mechanism_codes = [str(x) for x in known_row.get("mechanism_codes") or []]
        fivebox_checks = [str(x) for x in known_row.get("fivebox_checks") or []]
        evidence_sources = [str(x) for x in known_row.get("evidence_sources") or []]

        if "must_note" in decisions:
            status = "reviewed_note_required"
            player_note_required: bool | None = True
        elif "reviewed_no_extra_note" in decisions:
            status = "reviewed_no_extra_note"
            player_note_required = False
            facts = []
        elif risk_signals:
            status = "review_required_high_signal"
            player_note_required = None
        else:
            status = "review_required_low_signal"
            player_note_required = None

        spatial_signals = sorted(set(_spatial_signals(facts + mechanism_codes)) | set(str(x) for x in known_row.get("spatial_tags") or []))

        if status == "reviewed_note_required" and spatial_signals:
            spatial_status = "confirmed_non_flat_or_special_access"
            merge_policy = "requires_verified_spatial_anchor"
        elif status in {"review_required_high_signal", "review_required_low_signal"}:
            spatial_status = "unverified"
            merge_policy = "block_flat_coordinate_auto_merge_until_reviewed"
        else:
            spatial_status = "reviewed_no_known_spatial_exception"
            merge_policy = "flat_coordinate_merge_allowed_subject_to_cluster_geometry"

        execution_review = {
            "status": status,
            "player_note_required": player_note_required,
            "risk_signals": risk_signals,
            "spatial_status": spatial_status,
            "spatial_risk_signals": spatial_signals,
            "route_merge_policy": merge_policy,
            "facts": facts,
            "mechanism_codes": mechanism_codes,
            "fivebox_checks": fivebox_checks,
            "evidence_sources": evidence_sources,
        }
        task["execution_review"] = execution_review
        status_counts[status] += 1
        spatial_counts[spatial_status] += 1
        zone = str(task.get("assigned_zone_name") or "跨区/未知")
        by_zone[zone][status] += 1

        if status.startswith("review_required") and task.get("eligibility", {}).get("status") != "impossible_or_excluded":
            review_queue.append(
                {
                    "quest_id": qid,
                    "name": task.get("name"),
                    "zone": zone,
                    "eligibility": task.get("eligibility", {}).get("status"),
                    "risk_signals": risk_signals,
                    "route_merge_policy": merge_policy,
                }
            )

    review_queue.sort(key=lambda row: (0 if row["risk_signals"] else 1, row["zone"], row["quest_id"]))
    queue_by_zone: dict[str, Counter[str]] = defaultdict(Counter)
    for row in review_queue:
        queue_by_zone[row["zone"]]["total"] += 1
        queue_by_zone[row["zone"]]["high_signal" if row["risk_signals"] else "low_signal"] += 1
    return {
        "status_counts": dict(status_counts),
        "spatial_status_counts": dict(spatial_counts),
        "zone_status_counts": {zone: dict(counts) for zone, counts in sorted(by_zone.items())},
        "eligible_review_queue_count": len(review_queue),
        "eligible_high_signal_review_count": sum(bool(row["risk_signals"]) for row in review_queue),
        "eligible_low_signal_review_count": sum(not row["risk_signals"] for row in review_queue),
        "eligible_review_queue_by_zone": {zone: dict(counts) for zone, counts in sorted(queue_by_zone.items())},
        "review_queue": review_queue,
        **source_audit,
    }
