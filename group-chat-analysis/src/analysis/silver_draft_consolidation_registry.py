"""Aggregate reviewed Silver-draft consolidation groups and exclusions.

This layer is still pre-publication. Groups are provisional normalized knowledge
candidates; they do not mutate the existing Silver file.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .quality import WORK, sha256_file

DEFAULT_DRAFTS = WORK / "silver-draft-work-queue-v1.json"
DEFAULT_MANIFEST = WORK / "silver-draft-consolidation-reviewed-manifest-v1.json"


def inputs_from_manifest(path: Path) -> list[tuple[str, Path]]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows = doc.get("datasets", [])
    if not isinstance(rows, list) or not rows:
        raise ValueError("consolidation manifest must contain datasets")
    result = []
    seen_roles: set[str] = set()
    seen_files: set[str] = set()
    for row in rows:
        role = str(row.get("role") or "").strip()
        filename = str(row.get("file") or "").strip()
        if not role or not filename:
            raise ValueError("consolidation manifest rows require role and file")
        if role in seen_roles or filename in seen_files:
            raise ValueError(f"duplicate consolidation manifest entry: {role} / {filename}")
        seen_roles.add(role)
        seen_files.add(filename)
        file_path = WORK / filename
        if not file_path.exists():
            raise ValueError(f"consolidation dataset missing: {file_path}")
        result.append((role, file_path))
    return result


def build_registry(drafts: dict, inputs: list[tuple[str, Path]]) -> tuple[dict, dict]:
    draft_map = {
        str(row.get("question_id") or ""): row
        for row in drafts.get("items", [])
        if row.get("question_id")
    }
    if len(draft_map) != len(drafts.get("items", [])):
        raise ValueError("draft queue contains missing or duplicate question ids")

    groups: dict[str, dict] = {}
    assignment: dict[str, str] = {}
    exclusions: dict[str, dict] = {}
    separations: dict[tuple[str, str], dict] = {}
    datasets = []

    for role, path in inputs:
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("status") != "reviewed_silver_draft_consolidation":
            raise ValueError(f"unexpected consolidation status: {path}: {doc.get('status')}")
        datasets.append({
            "role": role,
            "file": path.name,
            "sha256": sha256_file(path),
        })

        for row in doc.get("groups", []):
            gid = str(row.get("group_id") or "").strip()
            canonical = str(row.get("canonical_question") or "").strip()
            members = [str(x) for x in row.get("members", [])]
            reason = str(row.get("reason") or "").strip()
            if not gid or not canonical or not members or not reason:
                raise ValueError(f"invalid consolidation group in {path}: {gid}")
            if len(members) != len(set(members)):
                raise ValueError(f"duplicate member inside consolidation group: {gid}")
            unknown = sorted(set(members) - set(draft_map))
            if unknown:
                raise ValueError(f"unknown draft members in {gid}: {unknown}")

            if gid not in groups:
                groups[gid] = {
                    "group_id": gid,
                    "canonical_question": canonical,
                    "members": [],
                    "reasons": [],
                    "review_origins": [],
                }
            elif groups[gid]["canonical_question"] != canonical:
                raise ValueError(f"canonical question changed for consolidation group: {gid}")

            for qid in members:
                if qid in exclusions:
                    raise ValueError(f"draft already excluded: {qid}")
                existing = assignment.get(qid)
                if existing and existing != gid:
                    raise ValueError(f"draft assigned to multiple consolidation groups: {qid}")
                if not existing:
                    assignment[qid] = gid
                    groups[gid]["members"].append(qid)
            groups[gid]["reasons"].append(reason)
            groups[gid]["review_origins"].append(role)

        for row in doc.get("exclusions", []):
            qid = str(row.get("question_id") or "").strip()
            reason = str(row.get("reason") or "").strip()
            if qid not in draft_map or not reason:
                raise ValueError(f"invalid exclusion in {path}: {qid}")
            if qid in assignment:
                raise ValueError(f"draft already assigned to group: {qid}")
            if qid in exclusions:
                raise ValueError(f"duplicate exclusion: {qid}")
            exclusions[qid] = {
                "question_id": qid,
                "reason": reason,
                "review_origin": role,
            }

        for row in doc.get("separations", []):
            a = str(row.get("a") or "").strip()
            b = str(row.get("b") or "").strip()
            reason = str(row.get("reason") or "").strip()
            if not a or not b or a == b or a not in draft_map or b not in draft_map or not reason:
                raise ValueError(f"invalid separation in {path}: {a} / {b}")
            key = tuple(sorted((a, b)))
            if key in separations:
                raise ValueError(f"duplicate separation: {key}")
            separations[key] = {
                "a": key[0],
                "b": key[1],
                "reason": reason,
                "review_origin": role,
            }

    group_rows = []
    for gid in sorted(groups):
        group = groups[gid]
        group["members"] = sorted(group["members"])
        group["source_cards"] = sorted({
            card
            for qid in group["members"]
            for card in draft_map[qid].get("source_cards", [])
        })
        group["claim_count"] = sum(
            int(draft_map[qid].get("claim_count") or 0)
            for qid in group["members"]
        )
        group_rows.append(group)

    active = [
        row for qid, row in draft_map.items()
        if qid not in assignment and qid not in exclusions
    ]
    active.sort(key=lambda row: (-int(row.get("claim_count") or 0), row["question_id"]))

    registry = {
        "schema_version": 1,
        "status": "reviewed_silver_draft_consolidation_registry_not_published",
        "contract": {
            "existing_silver_is_not_mutated": True,
            "groups_are_provisional": True,
            "similarity_is_not_merge": True,
        },
        "counts": {
            "draft_questions": len(draft_map),
            "assigned_questions": len(assignment),
            "excluded_questions": len(exclusions),
            "active_work_items": len(active),
            "provisional_groups": len(group_rows),
            "multi_question_groups": sum(len(g["members"]) > 1 for g in group_rows),
            "separation_boundaries": len(separations),
            "input_datasets": len(datasets),
        },
        "datasets": datasets,
        "groups": group_rows,
        "exclusions": [exclusions[qid] for qid in sorted(exclusions)],
        "separations": [separations[key] for key in sorted(separations)],
    }
    queue = {
        "schema_version": 1,
        "status": "silver_draft_consolidation_work_queue",
        "counts": {
            "total_draft_questions": len(draft_map),
            "assigned_questions": len(assignment),
            "excluded_questions": len(exclusions),
            "active_work_items": len(active),
        },
        "items": active,
    }
    return registry, queue


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--drafts", type=Path, default=DEFAULT_DRAFTS)
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    p.add_argument(
        "--out",
        type=Path,
        default=WORK / "silver-draft-consolidation-reviewed-v1.json",
    )
    p.add_argument(
        "--queue-out",
        type=Path,
        default=WORK / "silver-draft-consolidation-work-queue-v1.json",
    )
    args = p.parse_args()

    drafts = json.loads(args.drafts.read_text(encoding="utf-8"))
    registry, queue = build_registry(drafts, inputs_from_manifest(args.manifest))
    registry["inputs"] = {
        "drafts_sha256": sha256_file(args.drafts),
        "manifest_sha256": sha256_file(args.manifest),
    }
    args.out.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    queue["inputs"] = {
        "drafts_sha256": sha256_file(args.drafts),
        "registry_sha256": sha256_file(args.out),
    }
    args.queue_out.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(registry["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
