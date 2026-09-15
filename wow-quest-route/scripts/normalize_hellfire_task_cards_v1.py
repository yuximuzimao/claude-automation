from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TASK_CARDS_DIR = ROOT / "data/task-cards"


def _coverage(card: dict[str, Any]) -> dict[str, str]:
    mechanics = card.get("mechanics", {})
    stages = card.get("fivebox", {}).get("stages", [])
    open_questions = card.get("verification", {}).get("open_questions", [])

    if mechanics:
        mechanic_confidences = {item.get("confidence") for item in mechanics.values() if isinstance(item, dict)}
        mechanics_status = "verified" if mechanic_confidences == {"verified"} else "partial"
    else:
        mechanics_status = "unknown"

    if stages:
        fivebox_status = (
            "verified"
            if all(stage.get("confidence") == "verified" and stage.get("mode") != "unknown" for stage in stages)
            else "partial"
        )
    else:
        fivebox_status = "unknown"

    if open_questions and fivebox_status == "verified":
        fivebox_status = "partial"

    return {
        "availability": "partial",
        "objectives": "partial" if card.get("objectives") else "unknown",
        "locations": "partial" if card.get("locations") else "unknown",
        "rewards": "partial" if card.get("rewards") else "unknown",
        "mechanics": mechanics_status,
        "fivebox": fivebox_status,
        "guide": "partial" if card.get("guide") else "unknown",
    }


def _fivebox_player_status(card: dict[str, Any]) -> str:
    existing = card.get("fivebox", {}).get("status")
    if existing in {"shared", "not_shared", "sequential_loot", "pending"}:
        return existing

    if card.get("coverage", {}).get("fivebox") != "verified":
        return "pending"

    modes = {
        stage.get("mode")
        for stage in card.get("fivebox", {}).get("stages", [])
        if isinstance(stage, dict)
    }
    modes.discard(None)
    if not modes or "unknown" in modes:
        return "pending"

    shared_modes = {
        "shared_kill",
        "shared_progress",
        "shared_interaction",
        "shared_event",
        "escort_party_shared",
    }
    personal_modes = {
        "personal_progress",
        "personal_drop",
        "per_character_interaction",
        "per_character_item_use",
    }
    if modes <= shared_modes:
        return "shared"
    if modes == {"same_corpse_multi_character_loot"}:
        return "sequential_loot"
    if modes <= personal_modes:
        return "not_shared"
    return "pending"


def normalize(card: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(card, ensure_ascii=False))

    result["identity"].pop("knowledge_status", None)
    result["identity"]["game_variant_id"] = "timewalking-wotlk-cn"
    result["availability"].pop("direct_followups", None)
    result["coverage"] = _coverage(result)

    for evidence in result.get("evidence", []):
        supports = evidence.get("supports_fields", [])
        evidence["supports_fields"] = [
            field for field in supports if field != "availability.direct_followups"
        ]

    for question in result.get("verification", {}).get("open_questions", []):
        question.pop("impact", None)
        question.pop("player_visible", None)

    old_presentation = result.get("presentation", {})
    new_presentation: dict[str, Any] = {}

    # Idempotent path: preserve already-normalized v1 presentation fields exactly.
    if isinstance(old_presentation.get("note_override"), dict):
        new_presentation["note_override"] = old_presentation["note_override"]
    # One-time compatibility path from the pre-v1 draft fields.
    old_note_override = old_presentation.get("override")
    if "note_override" not in new_presentation and isinstance(old_note_override, dict):
        scope = old_note_override.get("scope") or "all"
        if scope != "all" and not str(scope).startswith("route_profile:"):
            scope = f"route_profile:{scope}"
        new_presentation["note_override"] = {
            "text": str(old_note_override.get("text", "")),
            "scope": str(scope),
            "source_ref": str(old_note_override.get("source_ref", "legacy-migration")),
            "reason": str(old_note_override.get("reason", "迁移现有用户固定展示语句。")),
        }

    legacy_badge = old_presentation.get("badge_override")
    badge_value = None
    if isinstance(legacy_badge, dict):
        badge_value = legacy_badge.get("value")
    if badge_value is None:
        badge_value = old_presentation.get("share_badge_override")
    if "status" not in result.get("fivebox", {}) and badge_value in {"shared", "not_shared"}:
        result.setdefault("fivebox", {})["status"] = badge_value

    result.setdefault("fivebox", {})["status"] = _fivebox_player_status(result)
    result["presentation"] = new_presentation

    # Keep coverage near identity for human readability.
    ordered: dict[str, Any] = {}
    for key in ("schema_version", "task_id", "identity", "coverage"):
        ordered[key] = result[key]
    for key, value in result.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize current Hellfire Task Cards to the frozen v1 contract.")
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
