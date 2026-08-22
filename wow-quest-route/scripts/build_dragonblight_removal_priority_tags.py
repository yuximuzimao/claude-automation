from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.questie_lua import seq
from lib.questie_source import load_questie
from scripts.build_route_reward_audit import EQUIPPABLE_ITEM_CLASSES, classify_multi_item_collection
from scripts.estimate_route_atlas_timing import estimate_foundation_task_service_audit

QUESTIE_ZIP = ROOT.parent / ".ai-bridge" / "Questie.zip"
ROUTES = ROOT / "data/route-atlas/workbench-routes.json"
FOUNDATION = ROOT / "data/route-atlas/dragonblight-task-foundation.json"
OBSERVATIONS = ROOT / "data/observations/fivebox-task-types.json"
UNIVERSE_OUT = ROOT / "data/route-atlas/dragonblight-task-card-universe.json"
MONEY_NEEDS_OUT = ROOT / "data/route-atlas/dragonblight-priority-money-needed.json"
TAGS_OUT = ROOT / "data/route-atlas/dragonblight-removal-priority-tags.json"
RETENTION_OUT = ROOT / "data/route-atlas/dragonblight-retention-overrides.json"
ATTRIBUTE_LOCK_OUT = ROOT / "data/route-atlas/dragonblight-task-attribute-locks.json"
DECISION_LOCK_OUT = ROOT / "data/route-atlas/dragonblight-removal-decision-locks.json"
AUDIT_OUT = ROOT / "docs/analysis/2026-08-18-dragonblight-removal-priority-tags.md"

ZONE_ID = 65
ZONE_NAME = "龙骨荒野"

# Current usable pool = effective-foundation primary world tasks on the current Borean->Dragonblight
# axis. These two rows are structurally present but cannot be selected by the current route:
# 11979 conflicts with the chosen inbound breadcrumb 11977; 12033 lost its only prerequisite
# when Borean 11916 was formally removed. 12791 remains usable even though the current route
# intentionally does not select it yet.
CURRENT_UNUSABLE_TASKS: dict[int, str] = {
    11979: "mutually_exclusive_with_current_borean_entry_axis",
    12033: "only_prerequisite_11916_removed_from_current_route",
}

# Questie's item->NPC reverse lookup can misclassify fixed ground objects or scripted
# spawned items as ordinary mob drops. These task-level corrections are optimization-critical
# because P1-P4 distinguishes random drops from predictable pickups.
DRAGON_COLLECTION_SOURCE_OVERRIDES: dict[int, tuple[list[str], str]] = {
    12009: (["pickup"], "underwater crab traps are fixed world pickups"),
    12044: (["pickup"], "Composite Ore is collected from ore carts around the digs"),
    12049: (["pickup"], "one scripted Hulking Jormungar explosion spawns meat slabs on the ground"),
    12200: (["pickup"], "Emerald Dragon Tears are ground objects at the Emerald Dragonshrine"),
    12303: (["pickup"], "Forgotten Treasure is gathered from wreck-area world objects"),
    12230: (["drop", "pickup"], "Siegesmith Bombs can be taken from the ground or looted from siegesmiths"),
    12209: (["pickup"], "Scarlet Onslaught Armor and Weapons are looted from armor stands and weapon racks throughout New Hearthglen"),
}


def apply_collection_source_override(qid: int, collection: dict[str, Any]) -> dict[str, Any]:
    override = DRAGON_COLLECTION_SOURCE_OVERRIDES.get(qid)
    if not override:
        return collection
    modes, reason = override
    result = dict(collection)
    result["source_modes"] = list(modes)
    result["manual_override_source"] = reason
    details = []
    for detail in collection.get("objective_details") or []:
        row = dict(detail)
        row["source_mode"] = modes[0] if len(modes) == 1 else "mixed"
        details.append(row)
    result["objective_details"] = details
    tags = [tag for tag in collection.get("tags") or [] if tag not in {"objective:multi_item_drop", "objective:multi_item_pickup"}]
    if modes == ["pickup"]:
        tags.append("objective:multi_item_pickup")
    elif set(modes) == {"drop", "pickup"}:
        tags.append("objective:multi_item_mixed_drop_pickup")
    result["tags"] = sorted(set(tags))
    return result

# Direct money paid at leveling level. Level-80 XP-to-money conversion does not count.
# Only no-equipment tasks that can change a Dragonblight P1-P4 decision (the eligible
# task itself or one of its in-scope descendants) are required here. Populate these
# two sets from the external WotLK quest-table Money column after the diagnostic pass.
DRAGON_NO_EQUIPMENT_WITH_DIRECT_MONEY: set[int] = {
    11958, 12009, 12016, 12028, 12030, 12031, 12044, 12045, 12046, 12049,
    12056, 12075, 12076, 12077, 12078, 12079, 12112, 12209, 12214, 12230,
    12234, 12239, 12240, 12254, 12260, 12274, 12283, 12458,
}
DRAGON_NO_EQUIPMENT_NO_DIRECT_MONEY: set[int] = {
    11978, 11983, 12008, 12011, 12034, 12036, 12039, 12063, 12069, 12071,
    12100, 12101, 12102, 12104, 12200, 12218, 12496, 12497, 12500, 13242,
}


def route_quest_names(route: dict[str, Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    points = route.get("points", [])
    for step_no, group in enumerate(route.get("stepGroups", []), 1):
        texts = [group.get("title", ""), group.get("summary", ""), group.get("note", ""), group.get("fivebox_check", "")]
        start, end = int(group.get("start", 0)), int(group.get("end", 0))
        for idx in range(max(0, start), min(len(points) - 1, end) + 1):
            point = points[idx]
            if len(point) >= 4:
                texts.append(point[3])
        for text in texts:
            for name in re.findall(r"《([^》]+)》", str(text or "")):
                result.setdefault(name, step_no)
    return result


def is_current_usable_world_task(task: dict[str, Any]) -> bool:
    qid = int(task["quest_id"])
    return bool(
        task.get("is_primary_candidate")
        and str(task.get("scope_status") or "").startswith("include_")
        and not task.get("is_dungeon")
        and not task.get("is_raid_flagged")
        and not task.get("is_repeatable")
        and qid not in CURRENT_UNUSABLE_TASKS
    )


def in_chain_scope(task: dict[str, Any]) -> bool:
    if not is_current_usable_world_task(task):
        return False
    zones = set(task.get("all_route_zones") or []) | set(task.get("start_zones") or []) | set(task.get("turnin_zones") or [])
    # Current confirmed route horizon is Dragonblight only. Cross-map outbound tasks may
    # be carried, but their out-of-zone descendants do not receive speculative value yet.
    return not zones or ZONE_ID in zones


def build_chain(tasks: list[dict[str, Any]]) -> tuple[dict[int, set[int]], dict[int, dict[str, Any]]]:
    universe = {int(task["quest_id"]): task for task in tasks}
    edges: dict[int, set[int]] = {qid: set() for qid in universe}

    def add(source: Any, target: Any) -> None:
        if not isinstance(source, int) or not isinstance(target, int):
            return
        if source == target or source not in universe or target not in universe:
            return
        if not in_chain_scope(universe[target]):
            return
        edges[source].add(target)

    for qid, task in universe.items():
        add(qid, task.get("next_quest"))
        for target in task.get("child_quests") or []:
            add(qid, target)
        add(qid, task.get("breadcrumb_for"))
        for target in task.get("breadcrumbs") or []:
            add(qid, target)

    for target, task in universe.items():
        for source in task.get("pre_all") or []:
            add(source, target)
        for source in task.get("parent_active") or []:
            add(source, target)
        for source in task.get("available_starting_with") or []:
            add(source, target)
        for source in task.get("pre_any") or []:
            add(source, target)
    return edges, universe


def descendants(qid: int, edges: dict[int, set[int]]) -> list[int]:
    seen: set[int] = set()
    stack = list(edges.get(qid, set()))
    while stack:
        target = stack.pop()
        if target in seen:
            continue
        seen.add(target)
        stack.extend(edges.get(target, set()))
    return sorted(seen)


def money_status(qid: int, has_equipment: bool, required_for_priority: bool) -> tuple[bool | None, str, list[str]]:
    if has_equipment:
        return None, "not_required_equipment_already_has_value", []
    if not required_for_priority:
        return None, "not_required_outside_priority_dependency_closure", []
    if qid in DRAGON_NO_EQUIPMENT_WITH_DIRECT_MONEY:
        return True, "verified_present", ["reward:direct_money"]
    if qid in DRAGON_NO_EQUIPMENT_NO_DIRECT_MONEY:
        return False, "verified_absent_at_leveling_level", ["reward:no_direct_money"]
    return None, "pending_priority_dependency", ["reward:money_pending"]


def lock_or_verify(path: Path, payload: dict[str, Any], label: str, *, allow_scope_migration: bool) -> str:
    if path.exists():
        current = json.loads(path.read_text(encoding="utf-8"))
        if current != payload:
            if not allow_scope_migration:
                raise RuntimeError(f"Locked Dragonblight {label} drifted; identify the fact/rule change instead of silently refreshing the lock.")
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return "refreshed_with_user_approved_scope_migration"
        return "verified"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return "created"


def main() -> None:
    allow_scope_migration = "--approved-usable-pool-migration" in sys.argv[1:]
    foundation = json.loads(FOUNDATION.read_text(encoding="utf-8"))
    retention = json.loads(RETENTION_OUT.read_text(encoding="utf-8"))
    priority_excluded_ids = {
        int(qid)
        for package in retention.get("packages") or []
        if package.get("priority_behavior") == "exclude_from_priority_candidates"
        for qid in package.get("protected_quest_ids") or []
    }
    tasks = [task for task in foundation.get("tasks", []) if is_current_usable_world_task(task)]
    tasks.sort(key=lambda task: int(task["quest_id"]))
    live_defer_count = sum(
        1
        for task in foundation.get("tasks", [])
        if task.get("is_primary_candidate")
        and str(task.get("scope_status") or "").startswith("defer_to_80_after_live_failure")
        and not task.get("is_dungeon")
        and not task.get("is_raid_flagged")
        and not task.get("is_repeatable")
    )
    expected_current_usable = 145 - live_defer_count
    if len(tasks) != expected_current_usable:
        raise RuntimeError(
            f"Expected {expected_current_usable} current-usable Dragonblight world tasks "
            f"after {live_defer_count} live defer-to-80 decisions, got {len(tasks)}"
        )
    if len({int(task["quest_id"]) for task in tasks}) != len(tasks):
        raise RuntimeError("Dragonblight task-card universe contains duplicate quest IDs")

    universe_payload = {
        "schema_version": 2,
        "status": "LOCKED_CURRENT_USABLE_WORLD_TASK_POOL",
        "route_key": "dragonblight",
        "source": "effective Dragonblight foundation include_* non-dungeon primary tasks, minus current-axis structural unavailability",
        "excluded_current_unusable": {str(qid): reason for qid, reason in CURRENT_UNUSABLE_TASKS.items()},
        "count": len(tasks),
        "tasks": [
            {
                "quest_id": int(task["quest_id"]),
                "name": task["name"],
                "scope_status": task.get("scope_status"),
            }
            for task in tasks
        ],
    }
    universe_state = lock_or_verify(
        UNIVERSE_OUT,
        universe_payload,
        "current usable task pool",
        allow_scope_migration=allow_scope_migration,
    )

    routes = json.loads(ROUTES.read_text(encoding="utf-8"))
    first_step = route_quest_names(routes["dragonblight"])
    observations = json.loads(OBSERVATIONS.read_text(encoding="utf-8"))
    questie = load_questie(QUESTIE_ZIP)
    edges, by_id = build_chain(tasks)

    reward_items: dict[int, list[dict[str, Any]]] = {int(task["quest_id"]): [] for task in tasks}
    for item_id, item in questie.items.items():
        for qid in seq(item.get(6)):
            if qid not in reward_items:
                continue
            reward_items[qid].append({
                "item_id": int(item_id),
                "name": item.get(1),
                "item_class": item.get(12),
                "item_subclass": item.get(13),
                "item_level": item.get(9),
                "required_level": item.get(10),
            })

    base: dict[int, dict[str, Any]] = {}
    eligible_ids: list[int] = []
    for task in tasks:
        qid = int(task["quest_id"])
        items = reward_items[qid]
        equipment = [item for item in items if item.get("item_class") in EQUIPPABLE_ITEM_CLASSES]
        collection = apply_collection_source_override(qid, classify_multi_item_collection(task))
        pattern = collection.get("collection_pattern")
        source_modes = set(collection.get("source_modes") or [])
        eligible = (
            qid not in priority_excluded_ids
            and in_chain_scope(task)
            and collection.get("is_multi_item_drop_or_pickup")
            and pattern in {"repeated_same_item", "repeated_plus_distinct"}
            and source_modes in ({"drop"}, {"pickup"})
        )
        if eligible:
            eligible_ids.append(qid)
        base[qid] = {
            "task": task,
            "equipment": equipment,
            "has_equipment": bool(equipment),
            "collection": collection,
            "descendants": descendants(qid, edges),
        }

    money_required_ids: set[int] = set()
    money_dependency_root_ids = set(eligible_ids) | priority_excluded_ids
    for qid in money_dependency_root_ids:
        relevant = [qid] + base[qid]["descendants"]
        for target_id in relevant:
            target = base.get(target_id)
            if target and not target["has_equipment"]:
                money_required_ids.add(target_id)

    classified_money_ids = DRAGON_NO_EQUIPMENT_WITH_DIRECT_MONEY | DRAGON_NO_EQUIPMENT_NO_DIRECT_MONEY
    overlap = DRAGON_NO_EQUIPMENT_WITH_DIRECT_MONEY & DRAGON_NO_EQUIPMENT_NO_DIRECT_MONEY
    extra = classified_money_ids - money_required_ids
    missing = money_required_ids - classified_money_ids
    if overlap:
        raise RuntimeError(f"Dragonblight money classification overlap: {sorted(overlap)}")

    money_need_payload = {
        "status": "priority_dependency_direct_money_screen",
        "route_key": "dragonblight",
        "rule": "Only no-equipment tasks in an eligible multi-item task's current-map descendant closure need direct-money lookup for P1-P4 tagging.",
        "required_count": len(money_required_ids),
        "classified_count": len(money_required_ids & classified_money_ids),
        "surplus_previously_verified_count": len(extra),
        "pending_count": len(missing),
        "tasks": [
            {
                "quest_id": qid,
                "name": by_id[qid]["name"],
                "english_name": by_id[qid].get("english_name"),
                "is_priority_candidate": qid in eligible_ids,
                "has_equipment_reward": base[qid]["has_equipment"],
                "classification": (
                    "direct_money" if qid in DRAGON_NO_EQUIPMENT_WITH_DIRECT_MONEY
                    else "no_direct_money" if qid in DRAGON_NO_EQUIPMENT_NO_DIRECT_MONEY
                    else "pending"
                ),
            }
            for qid in sorted(money_required_ids)
        ],
    }
    MONEY_NEEDS_OUT.write_text(json.dumps(money_need_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if missing:
        print(json.dumps({
            "task_card_count": len(tasks),
            "eligible_priority_candidate_count": len(eligible_ids),
            "money_required_count": len(money_required_ids),
            "money_pending_count": len(missing),
            "money_pending": [
                {
                    "quest_id": qid,
                    "name": by_id[qid]["name"],
                    "english_name": by_id[qid].get("english_name"),
                    "candidate": qid in eligible_ids,
                }
                for qid in sorted(missing)
            ],
            "universe_lock": universe_state,
        }, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    rows: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    priority_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    subtier_counts = {"A": 0, "B": 0, "C": 0}

    for task in tasks:
        qid = int(task["quest_id"])
        info = base[qid]
        required_money = qid in money_required_ids
        has_money, money_state, money_tags = money_status(qid, info["has_equipment"], required_money)
        tags = [f"scope:{task.get('scope_status')}"]
        tags.append("reward:equipment" if info["has_equipment"] else "reward:no_equipment")
        tags.extend(money_tags)
        if not required_money and not info["has_equipment"]:
            tags.append("reward:money_not_required_for_priority")
        tags.extend(info["collection"].get("tags") or [])
        timing = estimate_foundation_task_service_audit(task, observations)
        if timing.get("status") == "estimated":
            timing["minutes"] = round(float(timing["minutes"]), 2)
            tags.append("timing:estimated")
        else:
            tags.append("timing:unknown")

        desc = info["descendants"]
        direct_followups = sorted(edges.get(qid, set()))
        if in_chain_scope(task):
            tags.append("chain:has_in_scope_followup" if direct_followups else "chain:terminal_in_scope")
        else:
            tags.append("chain:not_in_priority_scope")

        decision: dict[str, Any]
        if qid in eligible_ids:
            valuable_followups: list[dict[str, Any]] = []
            for target_id in desc:
                target = base[target_id]
                target_money, _, _ = money_status(
                    target_id,
                    target["has_equipment"],
                    target_id in money_required_ids,
                )
                if target["has_equipment"] or target_money is True:
                    valuable_followups.append({
                        "quest_id": target_id,
                        "name": by_id[target_id]["name"],
                        "has_equipment_reward": target["has_equipment"],
                        "has_direct_money": target_money,
                    })
            direct_has_value = info["has_equipment"] or has_money is True
            source_modes = set(info["collection"].get("source_modes") or [])
            priority = 1
            if source_modes == {"pickup"}:
                priority += 1
            if direct_has_value:
                priority += 1
            if valuable_followups:
                priority += 1
            if priority not in priority_counts:
                raise RuntimeError(f"Unexpected priority P{priority} for {qid}")
            count = len(valuable_followups)
            subtier = "A" if count == 0 else "B" if count == 1 else "C"
            label = f"P{priority}{subtier}"
            tags.extend([
                f"removal:priority_{priority}",
                f"removal:subtier_{subtier}",
                f"removal:{label.lower()}",
            ])
            priority_counts[priority] += 1
            subtier_counts[subtier] += 1
            decision = {
                "eligible": True,
                "priority": priority,
                "subtier": subtier,
                "priority_label": label,
                "collection_source": next(iter(source_modes)),
                "collection_pattern": info["collection"].get("collection_pattern"),
                "direct_has_equipment_or_money_value": direct_has_value,
                "valuable_followup_count": count,
                "valuable_followups": valuable_followups,
            }
            decisions.append({"quest_id": qid, "name": task["name"], **decision})
        else:
            pattern = info["collection"].get("collection_pattern")
            if qid in priority_excluded_ids:
                reason = "protected_non_removal_candidate"
            elif not in_chain_scope(task):
                reason = "not_in_current_route_scope"
            elif not info["collection"].get("is_multi_item_drop_or_pickup"): 
                reason = "not_multi_item_drop_or_pickup"
            elif pattern == "multiple_distinct_one_each":
                reason = "multiple_distinct_one_each_excluded_by_rule"
            elif pattern not in {"repeated_same_item", "repeated_plus_distinct"}:
                reason = "collection_pattern_not_eligible"
            else:
                reason = "mixed_or_unknown_collection_source"
            tags.append(f"removal:not_eligible:{reason}")
            decision = {"eligible": False, "reason": reason}

        rows.append({
            "quest_id": qid,
            "name": task["name"],
            "english_name": task.get("english_name"),
            "scope_status": task.get("scope_status"),
            "first_route_step": first_step.get(task["name"]),
            "has_equipment_reward": info["has_equipment"],
            "equipment_rewards": info["equipment"],
            "direct_money_status": money_state,
            "has_direct_money": has_money,
            "max_level_bonus_money": task.get("xp", {}).get("max_level_bonus_money"),
            "collection": info["collection"],
            "chain": {
                "scope_zone_ids": [ZONE_ID],
                "direct_followup_ids": direct_followups,
                "descendant_ids": desc,
            },
            "timing": timing,
            "removal_priority": decision,
            "tags": sorted(set(tags)),
        })

    attribute_lock = {
        "schema_version": 1,
        "status": "LOCKED_TASK_ATTRIBUTES",
        "route_key": "dragonblight",
        "chain_scope": [{"zone_id": ZONE_ID, "name": ZONE_NAME}],
        "tasks": [
            {
                "quest_id": row["quest_id"],
                "name": row["name"],
                "locked_tags": [tag for tag in row["tags"] if tag.startswith(("scope:", "reward:", "objective:", "chain:", "timing:"))],
                "reward": {
                    "has_equipment_reward": row["has_equipment_reward"],
                    "has_direct_money": row["has_direct_money"],
                    "direct_money_status": row["direct_money_status"],
                    "max_level_bonus_money": row["max_level_bonus_money"],
                },
                "collection": {
                    "is_multi_item_drop_or_pickup": row["collection"]["is_multi_item_drop_or_pickup"],
                    "trusted_item_units": row["collection"]["trusted_item_units"],
                    "source_modes": row["collection"]["source_modes"],
                    "collection_pattern": row["collection"]["collection_pattern"],
                },
                "chain": row["chain"],
                "timing": {
                    "status": row["timing"].get("status"),
                    "minutes": row["timing"].get("minutes"),
                    "basis": row["timing"].get("basis"),
                },
            }
            for row in rows
        ],
    }
    decision_lock = {
        "schema_version": 1,
        "status": "LOCKED_OPTIMIZATION_DECISIONS",
        "route_key": "dragonblight",
        "rule": {
            "eligible_collection_patterns": ["repeated_same_item", "repeated_plus_distinct"],
            "excluded_collection_pattern": "multiple_distinct_one_each",
            "base": "multi-item drop + no equipment/direct-money value + no valuable Dragonblight follow-up = P1",
            "downgrade_one_level_each": [
                "pickup instead of drop",
                "current task has equipment or direct-money value",
                "at least one current-map downstream task has equipment or direct-money value",
            ],
            "subtier": {"A": "0 valuable descendants", "B": "1 valuable descendant", "C": "2+ valuable descendants"},
            "chain_scope": "Dragonblight only; future-map descendants are not speculatively valued.",
        },
        "candidates": sorted(decisions, key=lambda row: (row["priority"], row["subtier"], row["quest_id"])),
    }
    attribute_state = lock_or_verify(
        ATTRIBUTE_LOCK_OUT,
        attribute_lock,
        "task attributes",
        allow_scope_migration=allow_scope_migration,
    )
    decision_state = lock_or_verify(
        DECISION_LOCK_OUT,
        decision_lock,
        "removal decisions",
        allow_scope_migration=allow_scope_migration,
    )

    payload = {
        "schema_version": 2,
        "status": "current_usable_dragonblight_world_tasks_tagged_priority_screen_no_route_deletion",
        "route_key": "dragonblight",
        "rule_source": "docs/rules/leveling-and-selection.md",
        "pool_definition": {
            "effective_world_candidates_before_current_axis_filter": 147,
            "excluded_current_unusable": {str(qid): reason for qid, reason in CURRENT_UNUSABLE_TASKS.items()},
            "usable_task_count": len(rows),
        },
        "chain_scope": [{"zone_id": ZONE_ID, "name": ZONE_NAME}],
        "summary": {
            "task_card_count": len(rows),
            "priority_candidate_count": len(decisions),
            "priority_counts": {f"P{k}": v for k, v in priority_counts.items()},
            "subtier_counts": subtier_counts,
            "money_dependency_count": len(money_required_ids),
            "money_pending_count": 0,
            "formal_route_mutated_by_tagging": False,
        },
        "priority_candidates": sorted(decisions, key=lambda row: (row["priority"], row["subtier"], first_step.get(row["name"], 999), row["quest_id"])),
        "tasks": rows,
    }
    TAGS_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 龙骨荒野任务剔除优先级逐任务打标",
        "",
        "- 本轮只打标，不自动删除龙骨荒野正式路线任务。",
        f"- 当前可用任务池固定为{len(rows)}个：effective foundation中147个include_*非副本世界候选，扣除当前入口互斥的11979《牦牛人和牛头人》和因北风前置11916已删除而不可解锁的12033《萨鲁法尔的信》。",
        "- 12791《魔法王国达拉然》仍属于可用任务池，只是当前路线尚未证明值得选择。",
        "- 链价值范围只计算当前145个可用任务中的龙骨荒野内后续；尚未规划的下一地图不提前算价值。",
        f"- 进入P1–P4判定的任务：{len(decisions)}；P分布：{ {f'P{k}': v for k, v in priority_counts.items()} }；A/B/C：{subtier_counts}。",
        "",
        "## P1–P4候选",
        "",
    ]
    for row in sorted(decisions, key=lambda item: (item["priority"], item["subtier"], first_step.get(item["name"], 999), item["quest_id"])):
        source = "拾取" if row["collection_source"] == "pickup" else "掉落"
        step = first_step.get(row["name"])
        step_text = f"第{step}步" if step else "当前正式路线未出现"
        lines.append(
            f"- **{row['priority_label']}** 《{row['name']}》（{row['quest_id']}）：{source}；"
            f"当前任务有价值={'是' if row['direct_has_equipment_or_money_value'] else '否'}；"
            f"有价值后续={row['valuable_followup_count']}；{step_text}。"
        )
    lines.extend(["", f"## 全部{len(rows)}张任务卡", ""])
    for row in sorted(rows, key=lambda item: (item["first_route_step"] or 999, item["quest_id"])):
        decision = row["removal_priority"]
        p = decision.get("priority_label") if decision.get("eligible") else "非P候选"
        step = f"第{row['first_route_step']}步" if row["first_route_step"] else "未进当前路线"
        lines.append(f"- {step}｜{p}｜《{row['name']}》（{row['quest_id']}）｜`{row['scope_status']}`")
    AUDIT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "task_card_count": len(rows),
        "priority_candidate_count": len(decisions),
        "priority_counts": {f"P{k}": v for k, v in priority_counts.items()},
        "subtier_counts": subtier_counts,
        "attribute_lock": attribute_state,
        "decision_lock": decision_state,
        "outputs": [
            str(TAGS_OUT.relative_to(ROOT)),
            str(ATTRIBUTE_LOCK_OUT.relative_to(ROOT)),
            str(DECISION_LOCK_OUT.relative_to(ROOT)),
            str(AUDIT_OUT.relative_to(ROOT)),
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
