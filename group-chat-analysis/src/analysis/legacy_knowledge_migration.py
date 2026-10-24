"""Migrate historical user-confirmed card knowledge into formal Silver units."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from .quality import WORK, sha256_file
from .semantic_fingerprint import build_fingerprint_registry

DEFAULT_SILVER = WORK / "silver-knowledge-v1.json"
DEFAULT_REVIEW = WORK / "legacy-knowledge-silver-migration-reviewed-v1.json"
DEFAULT_ANCHORS = WORK / "verified-source-anchors-v1.json"
DEFAULT_AUDIT = WORK / "legacy-knowledge-silver-migration-apply-v1.json"


def apply_legacy_knowledge_migration(
    silver: dict,
    review: dict,
    verified_anchors: dict,
) -> tuple[dict, dict]:
    if review.get("status") != "reviewed_legacy_knowledge_silver_migration":
        raise ValueError("unexpected legacy knowledge migration review status")

    result = copy.deepcopy(silver)
    units = result.setdefault("units", [])
    existing_ids = {
        str(unit.get("knowledge_id") or "")
        for unit in units
        if unit.get("knowledge_id")
    }
    existing_card_owners: dict[str, str] = {}
    for unit in units:
        kid = str(unit.get("knowledge_id") or "")
        for ref in unit.get("evidence_refs", []):
            card = ref.get("card_id")
            if card:
                existing_card_owners[str(card)] = kid

    anchor_ids = set((verified_anchors.get("anchors") or {}).keys())
    reviewed_units = review.get("units", [])
    if not reviewed_units:
        raise ValueError("legacy knowledge migration has no reviewed units")

    added_ids: set[str] = set()
    migrated_cards: set[str] = set()
    for unit in reviewed_units:
        kid = str(unit.get("knowledge_id") or "")
        if not kid:
            raise ValueError("reviewed migration unit missing knowledge_id")
        if kid in existing_ids or kid in added_ids:
            raise ValueError(f"migration knowledge_id already exists: {kid}")
        if unit.get("initial_state") != "knowledge":
            raise ValueError(f"legacy user-confirmed migration must be knowledge: {kid}")
        if not unit.get("subject") or not unit.get("question") or not unit.get("canonical_facts"):
            raise ValueError(f"migration unit missing semantic fields: {kid}")
        if not isinstance(unit.get("structured"), dict):
            raise ValueError(f"migration unit missing structured object: {kid}")

        aliases = unit.get("legacy_aliases") or {}
        legacy_cards = [str(x) for x in aliases.get("card_ids", []) if x]
        if not legacy_cards:
            raise ValueError(f"migration unit missing legacy card alias: {kid}")

        refs = unit.get("evidence_refs") or []
        ref_cards = [str(ref.get("card_id")) for ref in refs if ref.get("card_id")]
        if not ref_cards:
            raise ValueError(f"migration unit has no card evidence: {kid}")
        missing_anchor = sorted(set(ref_cards) - anchor_ids)
        if missing_anchor:
            raise ValueError(
                f"migration evidence lacks verified source anchor: {kid}: {missing_anchor}"
            )
        occupied = {
            card: existing_card_owners[card]
            for card in ref_cards
            if card in existing_card_owners
        }
        if occupied:
            raise ValueError(
                f"migration evidence already owned by formal Silver: {kid}: {occupied}"
            )
        if not set(legacy_cards).issubset(set(ref_cards)):
            raise ValueError(
                f"legacy aliases must be represented in evidence refs: {kid}"
            )
        duplicate_cards = migrated_cards & set(ref_cards)
        if duplicate_cards:
            raise ValueError(
                f"legacy card assigned to multiple migration units: {sorted(duplicate_cards)}"
            )

        units.append(copy.deepcopy(unit))
        added_ids.add(kid)
        migrated_cards.update(ref_cards)

    # This also validates duplicate knowledge IDs and exact semantic identity collisions.
    registry = build_fingerprint_registry(result)

    audit = {
        "schema_version": 1,
        "status": "legacy_knowledge_silver_migration_applied",
        "counts": {
            "silver_before": len(silver.get("units", [])),
            "migrated_units": len(reviewed_units),
            "migrated_legacy_cards": len(migrated_cards),
            "silver_after": len(result.get("units", [])),
            "queue_after": sum(
                unit.get("initial_state") == "queue"
                for unit in result.get("units", [])
            ),
            "knowledge_after": sum(
                unit.get("initial_state") == "knowledge"
                for unit in result.get("units", [])
            ),
            "semantic_fingerprints_after": registry["counts"]["fingerprints"],
        },
        "migrated_knowledge_ids": sorted(added_ids),
        "migrated_card_ids": sorted(migrated_cards),
    }
    return result, audit


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--silver", type=Path, default=DEFAULT_SILVER)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--anchors", type=Path, default=DEFAULT_ANCHORS)
    parser.add_argument("--out", type=Path, default=DEFAULT_SILVER)
    parser.add_argument("--audit-out", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()

    result, audit = apply_legacy_knowledge_migration(
        _load(args.silver),
        _load(args.review),
        _load(args.anchors),
    )
    audit["inputs"] = {
        "silver_before_sha256": sha256_file(args.silver),
        "review_sha256": sha256_file(args.review),
        "anchors_sha256": sha256_file(args.anchors),
    }
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    audit["output_sha256"] = sha256_file(args.out)
    args.audit_out.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    main()
