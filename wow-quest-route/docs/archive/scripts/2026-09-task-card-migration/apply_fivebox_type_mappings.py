from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.task_cards import load_task_card, task_card_path, validate_task_card

REVIEW_QUEUE = ROOT / "tasks/task-card-migration/review-queue.json"
MAPPING_OUT = ROOT / "tasks/task-card-migration/fivebox-type-mapping.json"

PENDING_TYPES = {
    "special_capture_mechanic_group_share_pending",
    "mixed_ground_pickup_or_mob_drop_pickup_preferred",
    "object_collect_manual_local_loop",
    "post_prerequisite_item_trigger_fixed_route_task",
    "named_elite_with_single_use_protection_consumable_failure_mode",
}

SPECIAL_TYPES = {
    "single_fight_multi_character_interaction_confirmed",
    "event_group_shared_plus_named_corpse_multi_person_loot_confirmed",
    "item_trigger_same_corpse_fivebox_loot_followup_samples_shared_confirmed",
    "shared_completion_with_personal_script_gate_confirmed",
    "ship_burning_shared_same_corpse_fivebox_personal_loot_confirmed",
    "vehicle_kill_group_shared_same_corpse_fivebox_personal_loot_confirmed",
}

SEQUENTIAL_EXACT_TYPES = {
    "named_single_kill_multi_person_item_start_confirmed",
}

SEQUENTIAL_MARKERS = (
    "same_corpse_sequential_loot",
    "single_kill_multi_person_loot",
    "same_drop_sequential_pickup",
    "same_kill_sequential_pickup",
    "single_drop_multi_person_loot",
    "same_corpse_fivebox_loot",
    "same_corpse_fivebox_personal_loot",
    "same_corpse_multi_person",
    "same_source_fivebox_personal_loot",
    "three_named_single_kill_multi_person_loot",
    "shared_corpse_single_drop_multi_person_loot",
    "single_corpse_multi_character_item_start",
)


def classify_type(type_name: str) -> tuple[str, str]:
    if type_name in PENDING_TYPES:
        return "pending", "旧记录没有形成足够五开共享结论；保留待实测，不猜。"
    if type_name in SPECIAL_TYPES or type_name.startswith("mixed_") or "_mixed_" in type_name:
        return "special", "同一任务同时包含共享阶段与个人阶段/条件阶段，按粗粒度五类归special。"
    if type_name in SEQUENTIAL_EXACT_TYPES or any(marker in type_name for marker in SEQUENTIAL_MARKERS):
        return "sequential_loot", "任务物由各号取得，但同一有效掉落/尸体可供五号依次拾取。"
    if "group_shared" in type_name or "shared_confirmed" in type_name or type_name == "group_shared_completion_confirmed":
        return "shared", "旧type明确记录整项任务/任务进度共享。"
    if "personal" in type_name or "per_character" in type_name:
        return "not_shared", "旧type明确记录逐角色完成或个人进度。"
    raise ValueError(f"unclassified legacy fivebox type: {type_name}")


def build_mapping(review_queue: dict[str, Any], existing_mapping: dict[str, Any] | None = None) -> dict[str, Any]:
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for task in review_queue.get("tasks", []):
        for reason in task.get("reasons", []):
            if reason.get("kind") != "legacy_fivebox_needs_mapping":
                continue
            detail = reason.get("detail") or {}
            type_name = detail.get("type")
            if not isinstance(type_name, str) or not type_name:
                raise ValueError(f"task {task.get('task_id')} has legacy fivebox detail without type")
            by_type[type_name].append(
                {
                    "task_id": int(task["task_id"]),
                    "name": task.get("name"),
                    "legacy_status": detail.get("status"),
                    "note": detail.get("note"),
                    "confirmed_at": detail.get("confirmed_at") or detail.get("observed_at"),
                }
            )

    merged: dict[str, dict[str, Any]] = {}
    if isinstance(existing_mapping, dict):
        for row in existing_mapping.get("mappings", []):
            if isinstance(row, dict) and isinstance(row.get("legacy_type"), str):
                merged[row["legacy_type"]] = dict(row)

    for type_name, rows in by_type.items():
        status, basis = classify_type(type_name)
        existing = merged.get(type_name)
        if existing is not None and existing.get("fivebox_status") != status:
            raise ValueError(
                f"legacy type {type_name} mapping conflict: {existing.get('fivebox_status')} != {status}"
            )
        task_ids = set(existing.get("task_ids", [])) if existing else set()
        task_ids.update(row["task_id"] for row in rows)
        merged[type_name] = {
            "legacy_type": type_name,
            "fivebox_status": status,
            "basis": existing.get("basis") if existing and existing.get("basis") else basis,
            "task_count": len(task_ids),
            "task_ids": sorted(task_ids),
        }

    mappings = [merged[type_name] for type_name in sorted(merged)]
    type_status_counts: Counter[str] = Counter(row["fivebox_status"] for row in mappings)
    task_status_counts: Counter[str] = Counter()
    for row in mappings:
        task_status_counts[row["fivebox_status"]] += row["task_count"]

    return {
        "schema_version": 1,
        "status": "migration_workflow_mapping_not_task_truth",
        "source": "tasks/task-card-migration/review-queue.json + previous mapping ledger",
        "legacy_type_count": len(mappings),
        "task_count": sum(row["task_count"] for row in mappings),
        "type_status_counts": dict(sorted(type_status_counts.items())),
        "task_status_counts": dict(sorted(task_status_counts.items())),
        "mappings": mappings,
    }


def _merge_evidence(card: dict[str, Any], entry: dict[str, Any]) -> None:
    evidence = list(card.get("evidence") or [])
    replaced = False
    for index, row in enumerate(evidence):
        if isinstance(row, dict) and row.get("evidence_id") == entry["evidence_id"]:
            evidence[index] = entry
            replaced = True
            break
    if not replaced:
        evidence.append(entry)
    card["evidence"] = evidence


def apply_mapping(mapping: dict[str, Any], review_queue: dict[str, Any], *, write: bool) -> dict[str, Any]:
    status_by_type = {row["legacy_type"]: row["fivebox_status"] for row in mapping["mappings"]}
    detail_by_task: dict[int, dict[str, Any]] = {}
    for task in review_queue.get("tasks", []):
        for reason in task.get("reasons", []):
            if reason.get("kind") == "legacy_fivebox_needs_mapping":
                detail_by_task[int(task["task_id"])] = reason.get("detail") or {}

    changed = 0
    unchanged = 0
    resulting_statuses: Counter[str] = Counter()
    for task_id, detail in sorted(detail_by_task.items()):
        type_name = detail.get("type")
        if type_name not in status_by_type:
            raise ValueError(f"task {task_id}: missing mapping for type {type_name}")
        target_status = status_by_type[type_name]
        card = load_task_card(task_id)
        before = json.loads(json.dumps(card, ensure_ascii=False))
        current = (card.get("fivebox") or {}).get("status")
        if current not in {"pending", target_status}:
            raise ValueError(f"task {task_id}: existing fivebox.status={current} conflicts with mapping {target_status}")
        card["fivebox"] = {"status": target_status}

        observed_at = detail.get("confirmed_at") or detail.get("observed_at")
        confidence = "partial" if target_status == "pending" else "verified"
        _merge_evidence(
            card,
            {
                "evidence_id": "evidence-fivebox-type-mapping",
                "source_type": "user_live",
                "source_ref": f"data/observations/fivebox-task-types.json#tasks.{task_id}; legacy_type={type_name}",
                "observed_at": observed_at,
                "version_scope": "TitanReforged-Wotlk-ChinaRegion 3.80.2 / 时光服",
                "confidence": confidence,
                "supports_fields": ["fivebox.status"],
            },
        )
        validate_task_card(card, expected_task_id=task_id)
        resulting_statuses[target_status] += 1
        if card == before:
            unchanged += 1
        else:
            changed += 1
            if write:
                task_card_path(task_id).write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "write": write,
        "mapped_task_count": len(detail_by_task),
        "changed_card_count": changed,
        "unchanged_card_count": unchanged,
        "resulting_status_counts": dict(sorted(resulting_statuses.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve reviewed legacy fivebox types into the five-class Task Card status contract.")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    review_queue = json.loads(REVIEW_QUEUE.read_text(encoding="utf-8"))
    existing_mapping = json.loads(MAPPING_OUT.read_text(encoding="utf-8")) if MAPPING_OUT.exists() else None
    mapping = build_mapping(review_queue, existing_mapping)

    result = apply_mapping(mapping, review_queue, write=args.write)
    if args.write:
        MAPPING_OUT.write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"mapping": {k: v for k, v in mapping.items() if k != "mappings"}, "apply": result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
