from __future__ import annotations

import argparse
import copy
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.task_cards import task_card_path, validate_task_card
from lib.task_evidence_index import iter_formal_targets, unresolved_workbench_items

DEFAULT_INDEX = ROOT / "_sandbox/task-evidence-index.sqlite"
REVIEW_OUT = ROOT / "tasks/task-card-migration/review-queue.json"
SUMMARY_OUT = ROOT / "tasks/task-card-migration/mechanical-summary.json"
VALIDATION_LEDGER = ROOT / "tasks/task-card-migration/fivebox-validation-todo.json"
VERSION_SCOPE = "TitanReforged-Wotlk-ChinaRegion 3.80.2 / 时光服"
GAME_VARIANT = "timewalking-wotlk-cn"


def _meta(sqlite_path: Path) -> dict[str, Any]:
    with sqlite3.connect(sqlite_path) as conn:
        return {key: json.loads(value) for key, value in conn.execute("SELECT key, value FROM meta")}


def _merge_evidence(card: dict[str, Any], entry: dict[str, Any]) -> None:
    evidence = list(card.get("evidence") or [])
    by_id = {row.get("evidence_id"): row for row in evidence if isinstance(row, dict)}
    by_id[entry["evidence_id"]] = entry
    card["evidence"] = list(by_id.values())


def _hidden_requirements(questie: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in questie.get("hidden_requirements") or []:
        result.append(
            {
                "kind": row["kind"],
                "summary": row["summary"],
                "confidence": "verified",
                "source_refs": ["Questie 11.34.0 effective quest row"],
            }
        )
    raw_skill = questie.get("required_skill_raw")
    if raw_skill not in (None, 0, {}, []):
        result.append(
            {
                "kind": "questie_required_skill_raw",
                "summary": json.dumps(raw_skill, ensure_ascii=False),
                "confidence": "verified",
                "source_refs": ["Questie 11.34.0 effective quest row"],
            }
        )
    return result


def _basic_guide(questie: dict[str, Any]) -> list[str]:
    guide: list[str] = []
    starts = [row.get("name_zhcn") or f"{row.get('kind')}:{row.get('id')}" for row in questie.get("start_entities") or []]
    finishes = [row.get("name_zhcn") or f"{row.get('kind')}:{row.get('id')}" for row in questie.get("finish_entities") or []]
    if starts:
        guide.append("接取：" + "、".join(starts) + "。")
    objective = str(questie.get("objective_zh") or questie.get("objective_en") or "").strip()
    if objective:
        guide.append(objective)
    if finishes:
        guide.append("交付：" + "、".join(finishes) + "。")
    return guide


def _text_segments(text: str) -> list[tuple[list[str], str]]:
    re_mod = __import__("re")
    heading = re_mod.compile(r"(?:《[^》]+》)+[：:]")
    matches = list(heading.finditer(text))
    if not matches:
        return [([], text.strip())] if text.strip() else []
    result: list[tuple[list[str], str]] = []
    if text[: matches[0].start()].strip():
        result.append(([], text[: matches[0].start()].strip()))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        segment = text[match.start() : end].strip()
        names = re_mod.findall(r"《([^》]+)》", match.group(0))
        result.append((list(dict.fromkeys(names)), segment))
    return result


def _owned_texts(task_name: str, occurrences: list[dict[str, Any]], field: str) -> tuple[set[str], list[str]]:
    owned: set[str] = set()
    ambiguous: list[str] = []
    for occurrence in occurrences:
        text = str(occurrence.get(field) or "").strip()
        if not text:
            continue
        point_names = occurrence.get("point_task_names") or []
        for heading_names, segment in _text_segments(text):
            if heading_names:
                if heading_names == [task_name]:
                    owned.add(segment)
                elif task_name in heading_names:
                    ambiguous.append(segment)
                continue
            quoted = list(dict.fromkeys(__import__("re").findall(r"《([^》]+)》", segment)))
            if len(point_names) == 1 and point_names[0] == task_name:
                owned.add(segment)
            elif task_name in quoted:
                ambiguous.append(segment)
    return owned, ambiguous


def _manual_fact_candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for source in payload.get("structured_records") or []:
        record = source.get("record")
        if not isinstance(record, dict):
            continue
        final_review = record.get("final_review")
        if isinstance(final_review, dict) and final_review.get("facts"):
            found.append(
                {
                    "source": source.get("source"),
                    "pointer": source.get("pointer"),
                    "facts": final_review.get("facts"),
                }
            )
    return found


def _fivebox_mapping_evidence(card: dict[str, Any]) -> bool:
    return any(
        isinstance(row, dict) and row.get("evidence_id") == "evidence-fivebox-type-mapping"
        for row in (card.get("evidence") or [])
    )


def _has_evidence(card: dict[str, Any], evidence_id: str) -> bool:
    return any(
        isinstance(row, dict) and row.get("evidence_id") == evidence_id
        for row in (card.get("evidence") or [])
    )


def _fivebox_observation_supports_guide(card: dict[str, Any]) -> bool:
    return any(
        isinstance(row, dict)
        and str(row.get("source_ref") or "").startswith("data/observations/fivebox-task-types.json#tasks.")
        and "guide" in (row.get("supports_fields") or [])
        for row in (card.get("evidence") or [])
    )


def _status_only_fivebox_note(note: Any) -> bool:
    text = str(note or "").strip()
    if not text:
        return True
    tail = text.rsplit("确认：", 1)[-1].strip()
    return tail in {"共享", "共享。", "不共享", "不共享。"}


def _review_reasons(payload: dict[str, Any], card: dict[str, Any], deferred_validation_ids: set[int] | None = None) -> list[dict[str, Any]]:
    questie = payload.get("questie") or {}
    task_name = questie.get("name_zhcn") or (card.get("identity") or {}).get("name_zhcn") or str(payload["task_id"])
    reasons: list[dict[str, Any]] = []

    if payload.get("questie_correction_error"):
        reasons.append({"kind": "questie_correction_parse_error", "detail": payload["questie_correction_error"]})

    workbench_names = sorted(
        {
            str(row.get("task_name"))
            for row in (payload.get("workbench_occurrences") or [])
            if row.get("task_name")
        }
    )
    questie_name = questie.get("name_zhcn")
    alias_names = [name for name in workbench_names if name != questie_name]
    if alias_names and not _has_evidence(card, "evidence-current-server-name-13677"):
        reasons.append(
            {
                "kind": "workbench_name_alias_needs_identity_review",
                "questie_name": questie_name,
                "workbench_names": workbench_names,
            }
        )

    status = (card.get("fivebox") or {}).get("status", "pending")
    legacy_fivebox = payload.get("legacy_fivebox")
    if legacy_fivebox and status == "pending" and not _fivebox_mapping_evidence(card):
        reasons.append({"kind": "legacy_fivebox_needs_mapping", "detail": legacy_fivebox})
    if (
        isinstance(legacy_fivebox, dict)
        and not _status_only_fivebox_note(legacy_fivebox.get("note"))
        and not _fivebox_observation_supports_guide(card)
        and not _has_evidence(card, "evidence-fivebox-note-deferred-to-presentation")
    ):
        reasons.append({"kind": "legacy_fivebox_note_needs_guide_review", "detail": legacy_fivebox})

    note_owned, note_ambiguous = _owned_texts(task_name, payload.get("workbench_occurrences") or [], "note")
    note_override = (card.get("presentation") or {}).get("note_override")
    if note_override is None and (note_owned or note_ambiguous):
        reasons.append(
            {
                "kind": "workbench_note_needs_review",
                "owned_texts": sorted(note_owned),
                "ambiguous_texts": sorted(set(note_ambiguous)),
            }
        )

    fivebox_owned, fivebox_ambiguous = _owned_texts(task_name, payload.get("workbench_occurrences") or [], "fivebox_text")
    deferred_validation_ids = deferred_validation_ids or set()
    if status == "pending" and (fivebox_owned or fivebox_ambiguous) and int(payload["task_id"]) not in deferred_validation_ids:
        reasons.append(
            {
                "kind": "workbench_fivebox_text_needs_review",
                "owned_texts": sorted(fivebox_owned),
                "ambiguous_texts": sorted(set(fivebox_ambiguous)),
            }
        )

    manual = _manual_fact_candidates(payload)
    if manual and not _has_evidence(card, "evidence-dragonblight-special-mechanism-audit"):
        reasons.append({"kind": "legacy_manual_facts_need_guide_review", "candidates": manual})

    if not card.get("guide"):
        reasons.append({"kind": "questie_guide_empty", "detail": "Questie has no localized/English objective or entity guide content."})

    return reasons


def _mechanical_card(payload: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    task_id = int(payload["task_id"])
    questie = payload.get("questie")
    rewards = payload.get("rewards")
    if not isinstance(questie, dict):
        raise ValueError(f"formal task {task_id} is missing Questie data")
    if not isinstance(rewards, dict):
        raise ValueError(f"formal task {task_id} is missing exact reward data")

    existing = payload.get("existing_task_card")
    card = copy.deepcopy(existing) if isinstance(existing, dict) else {
        "schema_version": 1,
        "task_id": task_id,
        "identity": {},
        "coverage": {"availability": "unknown", "rewards": "unknown", "guide": "unknown"},
        "availability": {},
        "rewards": {},
        "guide": [],
        "fivebox": {"status": "pending"},
        "timing_rule_ref": None,
        "evidence": [],
        "presentation": {},
    }

    preserve_live_name = isinstance(existing, dict) and _has_evidence(existing, "evidence-current-server-name-13677")
    live_name = (existing.get("identity") or {}).get("name_zhcn") if preserve_live_name else None
    card["identity"] = {
        "name_zhcn": live_name or questie["name_zhcn"],
        "name_en": questie.get("name_en"),
        "game_variant_id": (card.get("identity") or {}).get("game_variant_id") or GAME_VARIANT,
        "version_scope": (card.get("identity") or {}).get("version_scope") or VERSION_SCOPE,
        "faction": questie["faction"],
        "repeatability": questie["repeatability"],
    }

    card["availability"] = {
        "quest_level": questie.get("quest_level"),
        "min_level": questie.get("min_level"),
        "pre_any": questie.get("pre_any") or [],
        "pre_all": questie.get("pre_all") or [],
        "parent_active": questie.get("parent_active") or [],
        "exclusive_with": questie.get("exclusive_with") or [],
        "required_reputation": questie.get("required_reputation"),
        "required_class": questie.get("required_class") or [],
        "required_race": questie.get("required_race") or [],
        "required_skill": [],
        "hidden_requirements": _hidden_requirements(questie),
    }
    card["rewards"] = rewards
    card.setdefault("coverage", {})["availability"] = "partial" if payload.get("questie_correction_error") else "verified"
    card["coverage"]["rewards"] = "verified"

    if not card.get("guide"):
        card["guide"] = _basic_guide(questie)
        card["coverage"]["guide"] = "partial" if card["guide"] else "unknown"

    card.setdefault("fivebox", {"status": "pending"})
    card.setdefault("timing_rule_ref", None)
    card.setdefault("presentation", {})

    task_name = questie["name_zhcn"]
    note_owned, note_ambiguous = _owned_texts(task_name, payload.get("workbench_occurrences") or [], "note")
    if (card.get("presentation") or {}).get("note_override") is None:
        if len(note_owned) == 1 and not note_ambiguous:
            card["presentation"] = {
                "note_override": {
                    "text": next(iter(note_owned)),
                    "scope": "all",
                    "source_ref": "data/route-atlas/workbench-routes.json",
                    "reason": "机械迁移：当前正式workbench中只有一条可明确归属该任务的备注，按原文无损保存。",
                }
            }
        elif not note_owned and not note_ambiguous:
            card["presentation"] = {
                "note_override": {
                    "text": "",
                    "scope": "all",
                    "source_ref": "data/route-atlas/workbench-routes.json",
                    "reason": "机械迁移确认当前正式workbench没有可归属到该任务的独立备注；显式保持为空。",
                }
            }

    existing_questie_evidence = next(
        (
            row
            for row in (card.get("evidence") or [])
            if isinstance(row, dict) and row.get("evidence_id") == "evidence-questie-11.34.0"
        ),
        None,
    )
    if isinstance(existing_questie_evidence, dict):
        # Existing cards may intentionally narrow Questie support after a live/public correction of one
        # Availability field. Mechanical refreshes must never broaden that evidence scope again.
        questie_supports = list(existing_questie_evidence.get("supports_fields") or [])
    else:
        questie_supports = (
            ["identity.name_en", "identity.faction", "identity.repeatability", "availability"]
            if preserve_live_name
            else ["identity", "availability"]
        )
        if not isinstance(existing, dict) or not (existing.get("guide") or []):
            questie_supports.append("guide")
    _merge_evidence(
        card,
        {
            "evidence_id": "evidence-questie-11.34.0",
            "source_type": "questie",
            "source_ref": f"Questie {meta['questie_version']} sha256={meta['questie_sha256']}; effective quest row task_id={task_id}",
            "observed_at": None,
            "version_scope": f"Questie WotLK {meta['questie_version']}",
            "confidence": "partial" if payload.get("questie_correction_error") else "verified",
            "supports_fields": questie_supports,
        },
    )
    _merge_evidence(
        card,
        {
            "evidence_id": "evidence-rewards-azerothcore",
            "source_type": "local_db",
            "source_ref": f"azerothcore/azerothcore-wotlk quest_template sha256={meta['quest_template_sha256']}; item_template sha256={meta['item_template_sha256']} + Questie {meta['questie_version']} zhCN/xp/reputation",
            "observed_at": None,
            "version_scope": f"WotLK 3.3.5 base DB; Questie {meta['questie_version']}",
            "confidence": "verified",
            "supports_fields": ["rewards"],
        },
    )
    validate_task_card(card, expected_task_id=task_id)
    return card


def migrate(sqlite_path: Path, *, write: bool) -> dict[str, Any]:
    meta = _meta(sqlite_path)
    payloads = list(iter_formal_targets(sqlite_path))
    validation_payload = json.loads(VALIDATION_LEDGER.read_text(encoding="utf-8")) if VALIDATION_LEDGER.exists() else {"tasks": []}
    deferred_validation_ids = {int(row["task_id"]) for row in validation_payload.get("tasks", []) if isinstance(row, dict) and row.get("task_id")}
    review_tasks: list[dict[str, Any]] = []
    cards: dict[int, dict[str, Any]] = {}
    created = 0
    updated = 0
    unchanged = 0

    for payload in payloads:
        card = _mechanical_card(payload, meta)
        task_id = int(payload["task_id"])
        cards[task_id] = card
        existing = payload.get("existing_task_card")
        if not isinstance(existing, dict):
            created += 1
        elif card == existing:
            unchanged += 1
        else:
            updated += 1
        reasons = _review_reasons(payload, card, deferred_validation_ids)
        if reasons:
            review_tasks.append(
                {
                    "task_id": task_id,
                    "name": (card.get("identity") or {}).get("name_zhcn"),
                    "reasons": reasons,
                }
            )

    unresolved = unresolved_workbench_items(sqlite_path)
    review_payload = {
        "schema_version": 1,
        "status": "workflow_review_queue_not_task_truth",
        "source_index": str(sqlite_path),
        "formal_resolved_task_count": len(payloads),
        "task_review_count": len(review_tasks),
        "mechanical_only_task_count": len(payloads) - len(review_tasks),
        "unresolved_workbench_name_count": len(unresolved),
        "tasks": review_tasks,
        "unresolved_workbench_names": unresolved,
    }
    summary = {
        "schema_version": 1,
        "status": "mechanical_task_card_migration_summary",
        "write": write,
        "formal_resolved_task_count": len(payloads),
        "created_card_count": created,
        "updated_card_count": updated,
        "unchanged_card_count": unchanged,
        "mechanical_only_task_count": len(payloads) - len(review_tasks),
        "task_review_count": len(review_tasks),
        "unresolved_workbench_name_count": len(unresolved),
        "review_reason_counts": {},
    }
    for item in review_tasks:
        for reason in item["reasons"]:
            kind = reason["kind"]
            summary["review_reason_counts"][kind] = summary["review_reason_counts"].get(kind, 0) + 1

    if write:
        for task_id, card in cards.items():
            path = task_card_path(task_id)
            path.write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        REVIEW_OUT.parent.mkdir(parents=True, exist_ok=True)
        REVIEW_OUT.write_text(json.dumps(review_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        SUMMARY_OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {**summary, "review_queue_preview": review_tasks[:10], "unresolved_workbench_preview": unresolved[:10]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Mechanically populate deterministic Task Card fields from the task evidence index.")
    parser.add_argument("--index", default=str(DEFAULT_INDEX))
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = migrate(Path(args.index), write=args.write)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
