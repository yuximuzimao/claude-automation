"""Aggregate authored Silver draft batches and keep a remaining review queue.

Authored drafts are still not published Silver. This registry only tracks which
materialized provisional groups have completed semantic writing.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .quality import WORK, sha256_file

DEFAULT_MATERIALIZED = WORK / "silver-draft-materialized-work-queue-v1.json"
DEFAULT_MANIFEST = WORK / "silver-draft-authored-manifest-v1.json"
DEFAULT_SILVER = WORK / "silver-knowledge-v1.json"


def inputs_from_manifest(path: Path) -> list[tuple[str, Path]]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows = doc.get("datasets", [])
    if not isinstance(rows, list):
        raise ValueError("authored manifest datasets must be a list")
    result = []
    seen_roles: set[str] = set()
    seen_files: set[str] = set()
    for row in rows:
        role = str(row.get("role") or "").strip()
        filename = str(row.get("file") or "").strip()
        if not role or not filename:
            raise ValueError("authored manifest row requires role and file")
        if role in seen_roles or filename in seen_files:
            raise ValueError(f"duplicate authored manifest entry: {role} / {filename}")
        seen_roles.add(role)
        seen_files.add(filename)
        p = WORK / filename
        if not p.exists():
            raise ValueError(f"authored dataset missing: {p}")
        result.append((role, p))
    return result


def build_registry(
    materialized: dict,
    inputs: list[tuple[str, Path]],
    formal_silver: dict | None = None,
) -> tuple[dict, dict]:
    source = {}
    for row in materialized.get("items", []):
        gid = str(row.get("group_id") or "").strip()
        if not gid:
            raise ValueError("materialized item missing group_id")
        if gid in source:
            raise ValueError(f"duplicate materialized group_id: {gid}")
        source[gid] = row

    authored_by_group: dict[str, dict] = {}
    knowledge_ids: set[str] = set()
    formal_knowledge_ids = {
        str(unit.get("knowledge_id") or "").strip()
        for unit in (formal_silver or {}).get("units", [])
        if str(unit.get("knowledge_id") or "").strip()
    }
    datasets = []

    for role, path in inputs:
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("status") != "authored_silver_drafts_not_published":
            raise ValueError(f"unexpected authored draft status: {path}: {doc.get('status')}")
        datasets.append({"role": role, "file": path.name, "sha256": sha256_file(path)})
        for entry in doc.get("items", []):
            unit = entry.get("unit") or {}
            lineage = entry.get("lineage") or {}
            gid = str(lineage.get("group_id") or "").strip()
            kid = str(unit.get("knowledge_id") or "").strip()
            if gid not in source:
                raise ValueError(f"authored draft references unknown group: {gid}")
            if gid in authored_by_group:
                raise ValueError(f"group authored more than once: {gid}")
            if not kid or kid in knowledge_ids:
                raise ValueError(f"missing or duplicate authored knowledge_id: {kid}")
            if kid in formal_knowledge_ids:
                raise ValueError(f"authored knowledge_id collides with formal Silver: {kid}")
            authored_by_group[gid] = {
                "group_id": gid,
                "knowledge_id": kid,
                "unit": unit,
                "lineage": lineage,
                "review_origin": role,
            }
            knowledge_ids.add(kid)

    remaining = [
        row for gid, row in source.items()
        if gid not in authored_by_group
    ]
    remaining.sort(key=lambda row: (
        -int(row.get("claim_count") or 0),
        -len(row.get("evidence_refs_proposed", [])),
        row["group_id"],
    ))

    authored = [authored_by_group[gid] for gid in sorted(authored_by_group)]
    registry = {
        "schema_version": 1,
        "status": "authored_silver_draft_registry_not_published",
        "contract": {
            "formal_silver_is_not_mutated": True,
            "authored_draft_is_not_published": True,
            "one_materialized_group_at_most_one_authored_unit": True,
        },
        "counts": {
            "materialized_groups": len(source),
            "authored_groups": len(authored),
            "active_work_items": len(remaining),
            "input_datasets": len(datasets),
        },
        "datasets": datasets,
        "items": authored,
    }
    queue = {
        "schema_version": 1,
        "status": "silver_draft_authoring_work_queue",
        "counts": {
            "materialized_groups": len(source),
            "authored_groups": len(authored),
            "active_work_items": len(remaining),
        },
        "items": remaining,
    }
    return registry, queue


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--materialized", type=Path, default=DEFAULT_MATERIALIZED)
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    p.add_argument("--silver", type=Path, default=DEFAULT_SILVER)
    p.add_argument(
        "--out",
        type=Path,
        default=WORK / "silver-draft-authored-registry-v1.json",
    )
    p.add_argument(
        "--queue-out",
        type=Path,
        default=WORK / "silver-draft-authoring-work-queue-v1.json",
    )
    args = p.parse_args()

    materialized = json.loads(args.materialized.read_text(encoding="utf-8"))
    registry, queue = build_registry(
        materialized,
        inputs_from_manifest(args.manifest),
        json.loads(args.silver.read_text(encoding="utf-8")),
    )
    registry["inputs"] = {
        "materialized_sha256": sha256_file(args.materialized),
        "manifest_sha256": sha256_file(args.manifest),
    }
    args.out.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    queue["inputs"] = {
        "materialized_sha256": sha256_file(args.materialized),
        "registry_sha256": sha256_file(args.out),
    }
    args.queue_out.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(registry["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
