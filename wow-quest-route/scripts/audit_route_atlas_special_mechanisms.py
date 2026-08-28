from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.questie_source import load_questie

QUESTIE_ZIP = ROOT / "data" / "sources" / "questie" / "Questie.zip"
DEFAULT_ATLAS = ROOT / "data" / "route-atlas" / "zangarmarsh-npc-validation.json"
DEFAULT_PROFILES = ROOT / "data" / "route-atlas" / "zangarmarsh-task-profiles.json"
DEFAULT_REGISTRY = ROOT / "data" / "route-atlas" / "special-mechanism-registry.json"
DEFAULT_OUTPUT = ROOT / "data" / "route-atlas" / "zangarmarsh-special-mechanism-audit.json"


def _slot_count(objectives: Any, slot: int) -> int:
    if not isinstance(objectives, dict):
        return 0
    value = objectives.get(slot)
    if not isinstance(value, dict):
        return 0
    return len([k for k in value if isinstance(k, int)])


def detect_risk_signals(raw: dict[Any, Any] | None, profile: dict[str, Any] | None) -> list[str]:
    raw = raw or {}
    profile = profile or {}
    objectives = raw.get(10)
    source_item_id = raw.get(11)
    signals: list[str] = []

    if source_item_id and _slot_count(objectives, 1):
        signals.append("provided_item_plus_creature_objectives")
    if _slot_count(objectives, 5):
        signals.append("credit_objective")
    if _slot_count(objectives, 6):
        signals.append("spell_objective")
    if raw.get(29):
        signals.append("hidden_extra_objectives")

    effective = str((profile.get("classification") or {}).get("effective_primary") or "")
    if any(token in effective for token in ("scripted", "escort")):
        signals.append("known_scripted_or_escort_type")

    return sorted(set(signals))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--atlas", type=Path, default=DEFAULT_ATLAS)
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    atlas = json.loads(args.atlas.read_text(encoding="utf-8"))
    profiles = json.loads(args.profiles.read_text(encoding="utf-8")) if args.profiles.exists() else {"quests": {}}
    registry = json.loads(args.registry.read_text(encoding="utf-8")) if args.registry.exists() else {"quests": {}}
    questie = load_questie(QUESTIE_ZIP)

    rows: dict[str, Any] = {}
    flagged = 0
    unresolved = 0
    for qid_text, atlas_q in atlas.get("quests", {}).items():
        qid = int(qid_text)
        profile = profiles.get("quests", {}).get(qid_text, {})
        raw = questie.quests.get(qid)
        signals = detect_risk_signals(raw, profile)
        registered = registry.get("quests", {}).get(qid_text)
        if not signals and not registered:
            continue
        flagged += 1
        review_required = bool(signals and not registered)
        if review_required:
            unresolved += 1
        rows[qid_text] = {
            "quest_id": qid,
            "name": atlas_q.get("name") or profile.get("name"),
            "risk_signals": signals,
            "review_required": review_required,
            "registry": registered,
            "source_item_id": raw.get(11) if raw else None,
        }

    payload = {
        "meta": {
            "purpose": "Find quests whose Questie objective markers may not represent the real execution entry or mechanic.",
            "rule": "Automatic signals only create a review queue. They never change routing without a per-quest registry decision.",
        },
        "summary": {
            "flagged_or_registered": flagged,
            "unresolved_review_required": unresolved,
        },
        "quests": rows,
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False))
    print(args.output)


if __name__ == "__main__":
    main()
