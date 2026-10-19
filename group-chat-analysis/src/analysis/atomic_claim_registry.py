"""Aggregate reviewed atomic-claim datasets into one lineage-aware registry.

The registry is a reviewed semantic layer, not Silver/Gold. Original Topic Cards remain
immutable retrieval hints and semantic-error cards stay quarantined at the old-card layer.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .atomic_claim_quality import assess
from .quality import WORK, sha256_file

DEFAULT_MANIFEST = WORK / "atomic-claim-reviewed-manifest-v1.json"


def inputs_from_manifest(path: Path) -> list[tuple[str, Path]]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows = doc.get("datasets", [])
    if not isinstance(rows, list) or not rows:
        raise ValueError("reviewed atomic manifest must contain datasets")
    result: list[tuple[str, Path]] = []
    seen_roles: set[str] = set()
    seen_files: set[str] = set()
    for row in rows:
        role = str(row.get("role") or "").strip()
        filename = str(row.get("file") or "").strip()
        if not role or not filename:
            raise ValueError("reviewed atomic manifest rows require role and file")
        if role in seen_roles or filename in seen_files:
            raise ValueError(f"duplicate reviewed atomic manifest entry: {role} / {filename}")
        seen_roles.add(role)
        seen_files.add(filename)
        path_obj = WORK / filename
        if not path_obj.exists():
            raise ValueError(f"reviewed atomic dataset missing: {path_obj}")
        result.append((role, path_obj))
    return result


def build_registry(inputs: list[tuple[str, Path]]) -> dict:
    cards: dict[str, dict] = {}
    claim_ids: set[str] = set()
    datasets = []
    for role, path in inputs:
        doc = json.loads(path.read_text(encoding="utf-8"))
        report = assess(doc)
        if report["result"] != "PASS":
            raise ValueError(f"atomic dataset failed quality gate: {path}: {report['quality']}")
        datasets.append({
            "role": role,
            "file": path.name,
            "sha256": sha256_file(path),
            "source_cards": report["counts"]["source_cards"],
            "atomic_claims": report["counts"]["atomic_claims"],
        })
        for item in doc["items"]:
            card_id = item["card"]
            if card_id in cards:
                raise ValueError(f"duplicate reviewed source card across atomic datasets: {card_id}")
            copied = json.loads(json.dumps(item, ensure_ascii=False))
            copied["review_origin"] = role
            copied["review_source_file"] = path.name
            for claim in copied["claims"]:
                if claim["id"] in claim_ids:
                    raise ValueError(f"duplicate atomic claim id: {claim['id']}")
                claim_ids.add(claim["id"])
            cards[card_id] = copied

    return {
        "schema_version": 1,
        "status": "reviewed_atomic_claim_registry_not_silver",
        "contract": {
            "source_of_truth": "claim-level canonical source_refs",
            "topic_cards_are_truth": False,
            "semantic_error_topic_cards_remain_quarantined": True,
            "registry_members_are_reviewed_claims": True,
        },
        "counts": {
            "reviewed_source_cards": len(cards),
            "reviewed_atomic_claims": len(claim_ids),
            "input_datasets": len(datasets),
        },
        "datasets": datasets,
        "items": [cards[key] for key in sorted(cards)],
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    p.add_argument("--out", type=Path, default=WORK / "atomic-claims-reviewed-v1.json")
    args = p.parse_args()
    result = build_registry(inputs_from_manifest(args.manifest))
    result["manifest"] = {"file": args.manifest.name, "sha256": sha256_file(args.manifest)}
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
