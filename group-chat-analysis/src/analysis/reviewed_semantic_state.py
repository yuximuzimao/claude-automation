"""Formal reviewed semantic state for first-read dedupe.

This registry is the durable truth for user review decisions.  It is intentionally
separate from filtering/quarantine: only explicit user decisions are represented.

Matching contract:
1. exact knowledge_id alias;
2. exact semantic fingerprint;
3. reviewed semantic comparison upstream.

Fuzzy similarity alone must never auto-hide a new unit.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from .quality import WORK, sha256_file
from .semantic_fingerprint import semantic_fingerprint, semantic_identity

DEFAULT_SILVER = WORK / "silver-knowledge-v1.json"
DEFAULT_DECISIONS = WORK / "reviewed-semantic-decisions-v1.json"
DEFAULT_OUT = WORK / "reviewed-semantic-state-v1.json"


def _state_id(fingerprint: str) -> str:
    _, digest = fingerprint.split(":", 1)
    return "rs1:" + digest


def _merge_aliases(target: dict, aliases: dict | None) -> None:
    aliases = aliases or {}
    for key in ("knowledge_ids", "card_ids"):
        current = set(target.setdefault("aliases", {}).setdefault(key, []))
        current.update(str(x) for x in aliases.get(key, []) if x)
        target["aliases"][key] = sorted(current)


def _add_record(records: dict[str, dict], record: dict) -> None:
    fp = record["semantic_fingerprint"]
    existing = records.get(fp)
    if existing is None:
        records[fp] = record
        return
    if existing["decision"] != record["decision"]:
        raise ValueError(
            f"conflicting user decisions for semantic fingerprint {fp}: "
            f"{existing['decision']} / {record['decision']}"
        )
    _merge_aliases(existing, record.get("aliases"))
    existing_sources = {
        json.dumps(x, ensure_ascii=False, sort_keys=True)
        for x in existing.get("source_refs", [])
    }
    for source in record.get("source_refs", []):
        key = json.dumps(source, ensure_ascii=False, sort_keys=True)
        if key not in existing_sources:
            existing.setdefault("source_refs", []).append(copy.deepcopy(source))
            existing_sources.add(key)
    bases = set(existing.setdefault("decision_basis", []))
    bases.update(record.get("decision_basis", []))
    existing["decision_basis"] = sorted(bases)


def build_reviewed_semantic_state(
    silver: dict,
    reviewed_decisions: dict | None = None,
) -> dict:
    records: dict[str, dict] = {}
    known_units: dict[str, dict] = {}

    for unit in silver.get("units", []):
        kid = str(unit.get("knowledge_id") or "")
        if not kid:
            raise ValueError("Silver unit missing knowledge_id")
        if kid in known_units:
            raise ValueError(f"duplicate Silver knowledge_id: {kid}")
        known_units[kid] = unit

        # A formal knowledge state means the user has already chosen to retain this
        # semantic conclusion.  Queue units are not reviewed merely by existing.
        if unit.get("initial_state") != "knowledge":
            continue
        fp = semantic_fingerprint(unit)
        legacy = unit.get("legacy_aliases") or {}
        record = {
            "state_id": _state_id(fp),
            "decision": "knowledge",
            "semantic_fingerprint": fp,
            "semantic_identity": semantic_identity(unit),
            "aliases": {
                "knowledge_ids": [kid],
                "card_ids": sorted({
                    str(x)
                    for x in legacy.get("card_ids", [])
                    if x
                }),
            },
            "source_refs": copy.deepcopy(unit.get("evidence_refs", [])),
            "decision_source": "user",
            "decision_basis": ["formal_silver_knowledge_state"],
        }
        _add_record(records, record)

    reviewed_decisions = reviewed_decisions or {
        "status": "reviewed_user_semantic_decisions",
        "items": [],
    }
    if reviewed_decisions.get("status") != "reviewed_user_semantic_decisions":
        raise ValueError("unexpected reviewed semantic decisions status")

    for item in reviewed_decisions.get("items", []):
        decision = str(item.get("decision") or "")
        if decision not in {"discard", "knowledge"}:
            raise ValueError(f"invalid user semantic decision: {decision}")
        if item.get("decision_source") != "user":
            raise ValueError("semantic state may only ingest explicit user decisions")

        knowledge_id = str(item.get("knowledge_id") or "")
        if knowledge_id:
            unit = known_units.get(knowledge_id)
            if unit is None:
                raise ValueError(f"decision references unknown knowledge_id: {knowledge_id}")
            identity = semantic_identity(unit)
            fp = semantic_fingerprint(unit)
            source_refs = copy.deepcopy(unit.get("evidence_refs", []))
            aliases = {
                "knowledge_ids": [knowledge_id],
                "card_ids": list((item.get("aliases") or {}).get("card_ids", [])),
            }
        else:
            raw_identity = item.get("semantic_identity")
            if not isinstance(raw_identity, dict):
                raise ValueError("card-only semantic decision requires semantic_identity")
            identity = semantic_identity(raw_identity)
            fp = semantic_fingerprint(raw_identity)
            source_refs = copy.deepcopy(item.get("source_refs", []))
            aliases = copy.deepcopy(item.get("aliases") or {})
            aliases.setdefault("knowledge_ids", [])
            aliases.setdefault("card_ids", [])
            if not aliases["card_ids"]:
                raise ValueError("card-only semantic decision requires card alias")

        record = {
            "state_id": _state_id(fp),
            "decision": decision,
            "semantic_fingerprint": fp,
            "semantic_identity": identity,
            "aliases": aliases,
            "source_refs": source_refs,
            "decision_source": "user",
            "decision_basis": [str(item.get("reason") or "explicit_user_review")],
        }
        _add_record(records, record)

    rows = sorted(records.values(), key=lambda row: row["state_id"])
    knowledge_ids = {
        kid
        for row in rows
        if row["decision"] == "knowledge"
        for kid in row.get("aliases", {}).get("knowledge_ids", [])
    }
    card_aliases = {
        card
        for row in rows
        for card in row.get("aliases", {}).get("card_ids", [])
    }
    return {
        "schema_version": 1,
        "status": "reviewed_semantic_state",
        "fingerprint_version": 1,
        "contract": {
            "user_decisions_only": True,
            "system_filters_are_user_read": False,
            "knowledge_is_also_read": True,
            "discard_is_not_knowledge": True,
            "evidence_only_changes_reopen": False,
            "material_boundary_or_correction_can_reopen": True,
            "matching_order": [
                "exact_knowledge_id",
                "exact_semantic_fingerprint",
                "reviewed_semantic_match",
            ],
            "fuzzy_similarity_can_auto_hide": False,
        },
        "counts": {
            "states": len(rows),
            "knowledge_states": sum(row["decision"] == "knowledge" for row in rows),
            "discard_states": sum(row["decision"] == "discard" for row in rows),
            "knowledge_id_aliases": len(knowledge_ids),
            "card_aliases": len(card_aliases),
        },
        "states": rows,
    }


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--silver", type=Path, default=DEFAULT_SILVER)
    parser.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    decisions = _load(args.decisions) if args.decisions.exists() else None
    result = build_reviewed_semantic_state(_load(args.silver), decisions)
    result["inputs"] = {
        "silver_sha256": sha256_file(args.silver),
        "decisions_sha256": sha256_file(args.decisions)
        if args.decisions.exists()
        else None,
    }
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
