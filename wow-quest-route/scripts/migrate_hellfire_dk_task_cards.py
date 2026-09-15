from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.task_cards import TASK_CARDS_DIR, task_card_path, validate_task_card

WORKBENCH = ROOT / "data/route-atlas/workbench-routes.json"
HELLFIRE_CANDIDATE = ROOT / "data/routes/world-candidate-dk/3483-hellfire-peninsula/route.json"
OUTLAND_AUDIT = ROOT / "data/routes/horde/blood-elf/outland-58-68-chain-audit.json"
ZANG_CANDIDATE = ROOT / "data/routes/world-candidate-dk/3521-zangarmarsh/route.json"
FIVEBOX_OBSERVATIONS = ROOT / "data/observations/fivebox-task-types.json"
TASK_RE = re.compile(r"《([^》]+)》")
VERSION_SCOPE = "TitanReforged-Wotlk-ChinaRegion 3.80.2 / 时光服"

# These three identities cannot be selected by Chinese name alone.  Each mapping is closed by
# existing structured project evidence before migration; see the migration matrix/review notes.
IDENTITY_OVERRIDES = {
    "向纳兹格雷尔报到": 10291,
    "刺客": 9400,
    "塞纳里奥远征队": 9912,
}

# One-time explicit migration of already confirmed five-box facts.  This is intentionally keyed by
# stable quest ID; no long-term inference from legacy natural-language notes or legacy type strings.
FIVEBOX_MIGRATIONS: dict[int, dict[str, Any]] = {
    10129: {
        "mode": "shared_progress",
        "kind": "distance_limited_shared_vehicle_progress",
        "summary": "队伍距离足够近时轰炸进度共享，不需要五号各完整飞一轮。",
        "guide": ["保持队伍在可共享距离内完成轰炸；离开前核对五号均已完成。"],
    },
    10162: {
        "mode": "shared_progress",
        "kind": "shared_objective_progress",
        "summary": "任务目标进度共享。",
        "guide": [],
    },
    10220: {
        "mode": "shared_kill",
        "kind": "shared_kill_progress",
        "summary": "三类阴魂击杀进度共享，主控击杀即可同步推进五号。",
        "guide": [],
    },
    10809: {
        "mode": "shared_kill",
        "kind": "shared_named_kill",
        "summary": "座狼主宰卡鲁什的击杀进度共享，只需击杀一次。",
        "guide": [],
    },
    10229: {
        "mode": "personal_drop",
        "kind": "guaranteed_personal_single_loot",
        "summary": "神秘典籍按必掉处理，但单个掉落只能由一个角色拾取；五号各自需要一份。",
        "guide": [],
    },
    10792: {
        "mode": "shared_progress",
        "kind": "shared_objective_progress",
        "summary": "建筑纵火任务进度共享，主控完成纵火即可同步队伍。",
        "guide": [],
    },
    10813: {
        "mode": "unknown",
        "kind": "special_capture_sharing_unresolved",
        "summary": "捕获格里洛克之眼的真实共享性尚未确认；第二组按逐号方式完成不能证明不共享。",
        "guide": ["向塞萨克取得碎片捕获格里洛克之眼，再带到塞萨克的熔锅使其分离。"],
        "open_question": {
            "question_id": "fivebox-sharing",
            "variable": "fivebox.stages[0].mode",
            "status": "expected",
            "reason": "第二组执行方式不能证明真实共享性，第三组需专门验证。",
            "close_condition": "在普通五人小队中由主控单独完成捕获流程并核对其余四号任务进度。",
        },
    },
    10236: {
        "mode": "per_character_interaction",
        "kind": "personal_fixed_object_collection",
        "summary": "伐木机备用零件不共享，五号需要分别拾取。",
        "guide": [],
    },
    10238: {
        "mode": "shared_progress",
        "kind": "shared_rescue_progress",
        "summary": "营救三名地精的任务进度共享，主控执行即可同步队伍。",
        "guide": [],
    },
    10629: {
        "mode": "personal_progress",
        "kind": "personal_rng_script_objective",
        "summary": "任务不共享；五号需要分别召唤地狱犬、喂野猪并从残渣中寻找钥匙，且存在随机长尾。",
        "guide": ["每个角色分别召唤地狱犬，击杀野猪后从地狱犬留下的残渣中寻找钥匙。"],
    },
}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _route_task_names() -> list[str]:
    routes = _load_json(WORKBENCH)
    route = routes.get("hellfire_dk")
    if not isinstance(route, dict):
        raise RuntimeError("workbench route hellfire_dk is missing")
    result: list[str] = []
    for point in route.get("points", []):
        action = str(point[3] if len(point) > 3 else "")
        for name in TASK_RE.findall(action):
            if name not in result:
                result.append(name)
    return result


def _collect_records(paths: list[Path]) -> tuple[dict[int, list[tuple[Path, dict[str, Any]]]], dict[str, set[int]]]:
    by_id: dict[int, list[tuple[Path, dict[str, Any]]]] = defaultdict(list)
    ids_by_name: dict[str, set[int]] = defaultdict(set)

    def walk(value: Any, source: Path) -> None:
        if isinstance(value, dict):
            quest_id = value.get("quest_id")
            name = value.get("name")
            if isinstance(quest_id, int) and isinstance(name, str):
                by_id[quest_id].append((source, value))
                ids_by_name[name].add(quest_id)
            for child in value.values():
                walk(child, source)
        elif isinstance(value, list):
            for child in value:
                walk(child, source)

    for path in paths:
        walk(_load_json(path), path)
    return by_id, ids_by_name


def _record_score(record: dict[str, Any]) -> int:
    useful = ("raw_name", "objective_text", "required_level", "quest_level", "pre_single", "pre_group", "next_quest")
    return sum(1 for key in useful if record.get(key) not in (None, [], ""))


def _best_record(records: list[tuple[Path, dict[str, Any]]]) -> tuple[Path, dict[str, Any]]:
    return max(records, key=lambda item: _record_score(item[1]))


def _resolve_task_ids(names: list[str], ids_by_name: dict[str, set[int]]) -> dict[str, int]:
    result: dict[str, int] = {}
    for name in names:
        if name in IDENTITY_OVERRIDES:
            result[name] = IDENTITY_OVERRIDES[name]
            continue
        candidates = sorted(ids_by_name.get(name, set()))
        if len(candidates) != 1:
            raise RuntimeError(f"cannot resolve stable quest id for {name!r}: {candidates}")
        result[name] = candidates[0]
    return result


def _confidence_from_legacy_status(status: str | None) -> str:
    if status == "user_confirmed":
        return "verified"
    if status in {"third_group_validation_pending", "user_confirmed_partial", "partially_confirmed"}:
        return "partial"
    return "partial"


def _fivebox_status_for_mode(mode: str | None) -> str:
    if mode in {"shared_kill", "shared_progress", "shared_interaction", "shared_event", "escort_party_shared"}:
        return "shared"
    if mode in {"personal_progress", "personal_drop", "per_character_interaction", "per_character_item_use"}:
        return "not_shared"
    if mode == "same_corpse_multi_character_loot":
        return "sequential_loot"
    return "pending"


def _make_card(
    quest_id: int,
    name: str,
    source: Path,
    record: dict[str, Any],
    legacy_fivebox: dict[str, Any] | None,
) -> dict[str, Any]:
    evidence = [
        {
            "evidence_id": "evidence-foundation-migration",
            "source_type": "legacy_migration",
            "source_ref": f"{source.relative_to(ROOT)}#quest_id={quest_id}",
            "observed_at": None,
            "version_scope": "current migrated project data",
            "confidence": "partial",
            "supports_fields": [
                "identity.name_zhcn",
                "identity.name_en",
                "availability.quest_level",
                "availability.min_level",
                "availability.pre_any",
                "availability.pre_all",
            ],
        }
    ]

    mechanics: dict[str, Any] = {}
    fivebox_stages: list[dict[str, Any]] = []
    guide: list[str] = []
    open_questions: list[dict[str, Any]] = []

    migration = FIVEBOX_MIGRATIONS.get(quest_id)
    if migration is not None:
        if legacy_fivebox is None:
            raise RuntimeError(f"quest {quest_id} has explicit fivebox migration but no legacy evidence")
        evidence_id = "evidence-fivebox-migration"
        evidence.append(
            {
                "evidence_id": evidence_id,
                "source_type": "user_live",
                "source_ref": f"data/observations/fivebox-task-types.json#tasks.{quest_id}",
                "observed_at": legacy_fivebox.get("confirmed_at"),
                "version_scope": VERSION_SCOPE,
                "confidence": _confidence_from_legacy_status(legacy_fivebox.get("status")),
                "supports_fields": ["mechanics.fivebox_observation", "fivebox.stages", "fivebox.status"],
            }
        )
        mechanics["fivebox_observation"] = {
            "kind": migration["kind"],
            "summary": migration["summary"],
            "confidence": "verified" if migration["mode"] != "unknown" else "partial",
            "source_refs": [evidence_id],
        }
        fivebox_stages.append(
            {
                "stage_id": "primary",
                "objective_id": None,
                "mode": migration["mode"],
                "summary": migration["summary"],
                "confidence": "verified" if migration["mode"] != "unknown" else "partial",
                "source_refs": [evidence_id],
            }
        )
        guide.extend(migration.get("guide", []))
        if migration.get("open_question"):
            open_questions.append(migration["open_question"])

    mechanics_coverage = "unknown"
    if mechanics:
        mechanics_coverage = (
            "verified"
            if all(item.get("confidence") == "verified" for item in mechanics.values())
            else "partial"
        )
    fivebox_coverage = "unknown"
    if fivebox_stages:
        fivebox_coverage = (
            "verified"
            if all(stage.get("confidence") == "verified" and stage.get("mode") != "unknown" for stage in fivebox_stages)
            else "partial"
        )

    return {
        "schema_version": 1,
        "task_id": quest_id,
        "identity": {
            "name_zhcn": name,
            "name_en": record.get("raw_name"),
            "game_variant_id": "timewalking-wotlk-cn",
            "version_scope": VERSION_SCOPE,
            "faction": "unknown",
            "repeatability": "unknown",
        },
        "coverage": {
            "availability": "partial",
            "objectives": "unknown",
            "locations": "unknown",
            "rewards": "unknown",
            "mechanics": mechanics_coverage,
            "fivebox": fivebox_coverage,
            "guide": "partial" if guide else "unknown",
        },
        "availability": {
            "quest_level": record.get("quest_level"),
            "min_level": record.get("required_level"),
            "pre_any": [int(value) for value in record.get("pre_single", []) if isinstance(value, int)],
            "pre_all": [int(value) for value in record.get("pre_group", []) if isinstance(value, int)],
            "parent_active": [],
            "exclusive_with": [int(value) for value in record.get("exclusive_to", []) if isinstance(value, int)],
            "required_reputation": None,
            "hidden_requirements": [],
        },
        "objectives": [],
        "mechanics": mechanics,
        "fivebox": {
            "status": _fivebox_status_for_mode(migration.get("mode") if migration else None),
            "stages": fivebox_stages,
        },
        "guide": guide,
        "verification": {"open_questions": open_questions},
        "evidence": evidence,
        "presentation": {},
    }


def migrate(*, write: bool) -> dict[str, Any]:
    names = _route_task_names()
    record_sources = [HELLFIRE_CANDIDATE, OUTLAND_AUDIT, ZANG_CANDIDATE]
    by_id, _ = _collect_records(record_sources)
    # Identity resolution is scoped to the current Hellfire candidate universe.  Cross-map/audit
    # sources may enrich an already resolved ID but must not create same-name ambiguity.
    _, hellfire_ids_by_name = _collect_records([HELLFIRE_CANDIDATE])
    ids_by_route_name = _resolve_task_ids(names, hellfire_ids_by_name)
    fivebox = _load_json(FIVEBOX_OBSERVATIONS).get("tasks", {})

    created: list[int] = []
    existing: list[int] = []
    with_fivebox: list[int] = []
    unresolved_fivebox: list[int] = []

    for name in names:
        quest_id = ids_by_route_name[name]
        if quest_id not in by_id:
            raise RuntimeError(f"no structured record found for {quest_id} {name}")
        if task_card_path(quest_id).exists():
            existing.append(quest_id)
            continue

        source, record = _best_record(by_id[quest_id])
        legacy_fivebox = fivebox.get(str(quest_id))
        if legacy_fivebox is not None:
            with_fivebox.append(quest_id)
            if quest_id not in FIVEBOX_MIGRATIONS:
                unresolved_fivebox.append(quest_id)

        card = _make_card(quest_id, name, source, record, legacy_fivebox)
        validate_task_card(card, expected_task_id=quest_id)
        if write:
            TASK_CARDS_DIR.mkdir(parents=True, exist_ok=True)
            task_card_path(quest_id).write_text(
                json.dumps(card, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        created.append(quest_id)

    if unresolved_fivebox:
        raise RuntimeError(
            "legacy fivebox evidence exists without explicit migration mapping: "
            + ", ".join(map(str, unresolved_fivebox))
        )

    return {
        "route_task_count": len(names),
        "resolved_task_count": len(ids_by_route_name),
        "existing_cards": sorted(existing),
        "created_cards": sorted(created),
        "migrated_fivebox_cards": sorted(with_fivebox),
        "write": write,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="One-time migration of current DK Hellfire route tasks into Task Card v1."
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write missing Task Cards. Without this flag the command is a dry-run validator.",
    )
    args = parser.parse_args()
    print(json.dumps(migrate(write=args.write), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
