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

# These identities cannot be selected by Chinese name alone. Each mapping is closed by existing
# structured project evidence before migration.
IDENTITY_OVERRIDES = {
    "向纳兹格雷尔报到": 10291,
    "刺客": 9400,
    "塞纳里奥远征队": 9912,
}

# One-time explicit migration of confirmed/current five-box results. The final Task Card keeps only
# the coarse execution status. Mixed/conditional details stay in guide; legacy type strings are never
# parsed into a status automatically.
FIVEBOX_MIGRATIONS: dict[int, dict[str, Any]] = {
    10129: {
        "status": "special",
        "guide": ["队伍距离足够近时轰炸进度共享，不需要五号各完整飞一轮；离开前核对五号均已完成。"],
    },
    10162: {"status": "shared", "guide": []},
    10208: {
        "status": "special",
        "guide": [
            "恶魔符文石由五个角色分别拾取；五号都达到任务要求后再离开收集区。",
            "炸毁希鲁斯传送门和科卢尔传送门的进度共享；主控完成炸门即可同步推进队伍。",
        ],
    },
    10220: {"status": "shared", "guide": []},
    10229: {
        "status": "not_shared",
        "guide": ["神秘典籍按必掉处理，但单个掉落只能由一个角色拾取；五号各自需要一份。"],
    },
    10236: {
        "status": "not_shared",
        "guide": ["伐木机备用零件不共享，五号需要分别拾取。"],
    },
    10238: {"status": "shared", "guide": []},
    10629: {
        "status": "not_shared",
        "guide": ["每个角色分别召唤地狱犬，击杀野猪后从地狱犬留下的残渣中寻找钥匙；存在随机长尾。"],
    },
    10792: {"status": "shared", "guide": []},
    10809: {"status": "shared", "guide": []},
    10813: {
        "status": "pending",
        "guide": ["向塞萨克取得碎片捕获格里洛克之眼，再带到塞萨克的熔锅使其分离。"],
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


def _make_card(
    quest_id: int,
    name: str,
    source: Path,
    record: dict[str, Any],
    legacy_fivebox: dict[str, Any] | None,
) -> dict[str, Any]:
    migration = FIVEBOX_MIGRATIONS.get(quest_id)
    guide = list(migration.get("guide", [])) if migration else []
    status = str(migration.get("status", "pending")) if migration else "pending"

    evidence: list[dict[str, Any]] = [
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

    if migration is not None:
        if legacy_fivebox is None:
            raise RuntimeError(f"quest {quest_id} has explicit fivebox migration but no legacy evidence")
        supports = ["fivebox.status"]
        if guide:
            supports.append("guide")
        evidence.append(
            {
                "evidence_id": "evidence-fivebox-migration",
                "source_type": "user_live",
                "source_ref": f"data/observations/fivebox-task-types.json#tasks.{quest_id}",
                "observed_at": legacy_fivebox.get("confirmed_at"),
                "version_scope": VERSION_SCOPE,
                "confidence": _confidence_from_legacy_status(legacy_fivebox.get("status")),
                "supports_fields": supports,
            }
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
            "rewards": "unknown",
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
            "required_class": [],
            "required_race": [],
            "required_skill": [],
            "hidden_requirements": [],
        },
        "rewards": {},
        "guide": guide,
        "fivebox": {"status": status},
        "timing_rule_ref": None,
        "evidence": evidence,
        "presentation": {},
    }


def migrate(*, write: bool) -> dict[str, Any]:
    names = _route_task_names()
    record_sources = [HELLFIRE_CANDIDATE, OUTLAND_AUDIT, ZANG_CANDIDATE]
    by_id, _ = _collect_records(record_sources)
    # Identity resolution is scoped to the current Hellfire candidate universe. Cross-map/audit
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
            "legacy fivebox evidence exists without explicit task-id migration mapping: "
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
        description="One-time migration of current DK Hellfire route tasks into simplified Task Card v1."
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
