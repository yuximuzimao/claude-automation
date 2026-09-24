from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.task_cards import TASK_CARDS_DIR, validate_task_card

# Existing enriched Hellfire cards are a small, reviewed set. Keep semantic conversion explicit by
# task_id instead of trying to infer guide facts from arbitrary legacy mechanics/type text.
GUIDE_OVERRIDES: dict[int, list[str]] = {
    10129: ["队伍距离足够近时轰炸进度共享，不需要五号各完整飞一轮；离开前核对五号均已完成。"],
    10134: ["塞纳里奥哨站北侧巨人自然掉落火红水晶碎片后可接取《火红水晶中的线索》。"],
    10208: [
        "恶魔符文石由五个角色分别拾取；五号都达到任务要求后再离开收集区。",
        "炸毁希鲁斯传送门和科卢尔传送门的进度共享；主控完成炸门即可同步推进队伍。",
    ],
    10229: ["神秘典籍按必掉处理，但单个掉落只能由一个角色拾取；五号各自需要一份。"],
    10236: ["伐木机备用零件不共享，五号需要分别拾取。"],
    10393: ["剃刀电锯自然掉落燃烧军团信件后可接取《邪恶的计划》。"],
    10629: ["每个角色分别召唤地狱犬，击杀野猪后从地狱犬留下的残渣中寻找钥匙；存在随机长尾。"],
    10813: ["向塞萨克取得碎片捕获格里洛克之眼，再带到塞萨克的熔锅使其分离。"],
    9373: ["被腐蚀的皮箱自然掉落后可接取《遗失的信件》。"],
}

STATUS_OVERRIDES = {
    10129: "special",
    10208: "special",
}

VALID_STATUSES = {"shared", "not_shared", "sequential_loot", "special", "pending"}


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _coverage(card: dict[str, Any], guide: list[str]) -> dict[str, str]:
    old = card.get("coverage", {})
    availability = old.get("availability", "unknown")
    rewards = old.get("rewards", "partial" if card.get("rewards") else "unknown")
    old_guide = old.get("guide", "unknown")
    guide_status = old_guide if old_guide in {"partial", "verified"} else ("partial" if guide else "unknown")
    return {
        "availability": availability,
        "rewards": rewards,
        "guide": guide_status,
    }


def _rewrite_supports(fields: list[Any], *, has_guide: bool) -> list[str]:
    result: list[str] = []
    for raw in fields:
        if not isinstance(raw, str):
            continue
        field = raw
        if field == "availability.direct_followups":
            continue
        if field == "fivebox.stages" or field.startswith("fivebox.stages["):
            field = "fivebox.status"
        elif field == "objectives" or field.startswith("objectives["):
            field = "guide"
        elif field == "locations" or field.startswith("locations."):
            field = "guide"
        elif field.startswith("mechanics."):
            field = "guide" if has_guide else "fivebox.status"
        elif field.startswith("verification."):
            continue
        if field not in result:
            result.append(field)
    return result


def normalize(card: dict[str, Any]) -> dict[str, Any]:
    task_id = int(card["task_id"])
    identity = json.loads(json.dumps(card["identity"], ensure_ascii=False))
    identity.pop("knowledge_status", None)
    identity["game_variant_id"] = identity.get("game_variant_id") or "timewalking-wotlk-cn"

    availability = json.loads(json.dumps(card["availability"], ensure_ascii=False))
    availability.pop("direct_followups", None)
    availability.setdefault("required_reputation", None)
    availability.setdefault("required_class", [])
    availability.setdefault("required_race", [])
    availability.setdefault("required_skill", [])
    availability.setdefault("hidden_requirements", [])

    guide = list(GUIDE_OVERRIDES.get(task_id, card.get("guide", [])))
    guide = _dedupe([str(item) for item in guide if isinstance(item, str) and item.strip()])

    status = STATUS_OVERRIDES.get(task_id, card.get("fivebox", {}).get("status", "pending"))
    if status not in VALID_STATUSES:
        status = "pending"

    evidence = json.loads(json.dumps(card.get("evidence", []), ensure_ascii=False))
    for item in evidence:
        if not isinstance(item, dict):
            continue
        item["supports_fields"] = _rewrite_supports(
            list(item.get("supports_fields", [])),
            has_guide=bool(guide),
        )

    old_presentation = card.get("presentation", {})
    presentation: dict[str, Any] = {}
    if isinstance(old_presentation.get("note_override"), dict):
        presentation["note_override"] = json.loads(json.dumps(old_presentation["note_override"], ensure_ascii=False))
    elif isinstance(old_presentation.get("override"), dict):
        old_override = old_presentation["override"]
        scope = old_override.get("scope") or "all"
        if scope != "all" and not str(scope).startswith("route_profile:"):
            scope = f"route_profile:{scope}"
        presentation["note_override"] = {
            "text": str(old_override.get("text", "")),
            "scope": str(scope),
            "source_ref": str(old_override.get("source_ref", "legacy-migration")),
            "reason": str(old_override.get("reason", "迁移现有玩家备注。")),
        }

    result = {
        "schema_version": 1,
        "task_id": task_id,
        "identity": identity,
        "coverage": _coverage(card, guide),
        "availability": availability,
        "rewards": json.loads(json.dumps(card.get("rewards", {}), ensure_ascii=False)),
        "guide": guide,
        "fivebox": {"status": status},
        "timing_rule_ref": card.get("timing_rule_ref"),
        "evidence": evidence,
        "presentation": presentation,
    }
    validate_task_card(result, expected_task_id=task_id)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize current Hellfire Task Cards to the simplified v1 contract."
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    changed: list[int] = []
    for path in sorted(TASK_CARDS_DIR.glob("*.json")):
        if path.name == "schema.json":
            continue
        task_id = int(path.stem)
        old = json.loads(path.read_text(encoding="utf-8"))
        new = normalize(old)
        if new != old:
            changed.append(task_id)
            if args.write:
                path.write_text(json.dumps(new, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"changed": changed, "count": len(changed), "write": args.write}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
