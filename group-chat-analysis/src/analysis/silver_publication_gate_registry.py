"""Aggregate reviewed Silver publication-gate decisions and emit remaining queue.

This stage records human publication intent only. It does not mutate the formal
Silver registry.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .quality import WORK, sha256_file

DEFAULT_PROPOSALS = WORK / "silver-publication-gate-proposals-v1.json"
DEFAULT_AUTHORED = WORK / "silver-draft-authored-registry-v1.json"
DEFAULT_FORMAL = WORK / "silver-knowledge-v1.json"
DEFAULT_MANIFEST = WORK / "silver-publication-gate-reviewed-manifest-v1.json"

ALLOWED_DECISIONS = {"append_new", "update_existing", "hold"}


def inputs_from_manifest(path: Path) -> list[tuple[str, Path]]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows = doc.get("datasets", [])
    if not isinstance(rows, list):
        raise ValueError("publication manifest datasets must be a list")
    result = []
    seen_roles: set[str] = set()
    seen_files: set[str] = set()
    for row in rows:
        role = str(row.get("role") or "").strip()
        filename = str(row.get("file") or "").strip()
        if not role or not filename:
            raise ValueError("publication manifest rows require role and file")
        if role in seen_roles or filename in seen_files:
            raise ValueError(f"duplicate publication manifest entry: {role} / {filename}")
        seen_roles.add(role)
        seen_files.add(filename)
        p = WORK / filename
        if not p.exists():
            raise ValueError(f"publication decision dataset missing: {p}")
        result.append((role, p))
    return result


def build_registry(
    proposals: dict,
    authored: dict,
    formal: dict,
    inputs: list[tuple[str, Path]],
) -> tuple[dict, dict]:
    proposal_map = {
        str(row.get("group_id") or ""): row
        for row in proposals.get("items", [])
        if row.get("group_id")
    }
    authored_map = {
        str((row.get("lineage") or {}).get("group_id") or row.get("group_id") or ""): row
        for row in authored.get("items", [])
        if (row.get("lineage") or {}).get("group_id") or row.get("group_id")
    }
    formal_ids = {
        str(unit.get("knowledge_id") or "")
        for unit in formal.get("units", [])
        if unit.get("knowledge_id")
    }
    if len(proposal_map) != len(proposals.get("items", [])):
        raise ValueError("proposal items contain missing or duplicate group ids")
    if len(authored_map) != len(authored.get("items", [])):
        raise ValueError("authored items contain missing or duplicate group ids")
    if set(proposal_map) != set(authored_map):
        missing_p = sorted(set(authored_map) - set(proposal_map))
        missing_a = sorted(set(proposal_map) - set(authored_map))
        raise ValueError(f"proposal/authored group mismatch: missing_proposals={missing_p} missing_authored={missing_a}")

    reviewed: dict[str, dict] = {}
    datasets = []
    counts = {
        "authored_drafts": len(authored_map),
        "reviewed_groups": 0,
        "append_new": 0,
        "update_existing": 0,
        "hold": 0,
        "active_work_items": 0,
        "input_datasets": 0,
    }

    for role, path in inputs:
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("status") != "reviewed_silver_publication_gate":
            raise ValueError(f"unexpected publication decision status: {path}: {doc.get('status')}")
        datasets.append({"role": role, "file": path.name, "sha256": sha256_file(path)})
        for row in doc.get("decisions", []):
            gid = str(row.get("group_id") or "").strip()
            decision = str(row.get("decision") or "").strip()
            reason = str(row.get("reason") or "").strip()
            target = str(row.get("target_knowledge_id") or "").strip() or None
            if gid not in proposal_map:
                raise ValueError(f"unknown publication group: {gid}")
            if gid in reviewed:
                raise ValueError(f"duplicate publication decision: {gid}")
            if decision not in ALLOWED_DECISIONS:
                raise ValueError(f"invalid publication decision for {gid}: {decision}")
            if not reason:
                raise ValueError(f"publication decision requires reason: {gid}")
            if decision == "update_existing":
                if not target or target not in formal_ids:
                    raise ValueError(f"update_existing requires valid formal target: {gid}: {target}")
            elif target:
                raise ValueError(f"{decision} must not set target_knowledge_id: {gid}")

            reviewed[gid] = {
                "group_id": gid,
                "draft_knowledge_id": proposal_map[gid].get("knowledge_id"),
                "decision": decision,
                "target_knowledge_id": target,
                "reason": reason,
                "review_origin": role,
            }
            counts[decision] += 1

    remaining = [
        row for gid, row in proposal_map.items()
        if gid not in reviewed
    ]
    remaining.sort(key=lambda row: (
        -float(row.get("review_priority_score") or 0.0),
        -float(row.get("top_formal_score") or 0.0),
        -float(row.get("top_authored_score") or 0.0),
        row.get("knowledge_id") or "",
    ))
    counts["reviewed_groups"] = len(reviewed)
    counts["active_work_items"] = len(remaining)
    counts["input_datasets"] = len(datasets)

    registry = {
        "schema_version": 1,
        "status": "reviewed_silver_publication_gate_not_applied",
        "contract": {
            "formal_silver_is_not_mutated": True,
            "decisions_are_human_reviewed": True,
            "allowed_decisions": sorted(ALLOWED_DECISIONS),
        },
        "counts": counts,
        "datasets": datasets,
        "items": [reviewed[gid] for gid in sorted(reviewed)],
    }
    queue = {
        "schema_version": 1,
        "status": "silver_publication_gate_work_queue",
        "counts": {
            "authored_drafts": len(authored_map),
            "reviewed_groups": len(reviewed),
            "active_work_items": len(remaining),
        },
        "items": remaining,
    }
    return registry, queue


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--proposals", type=Path, default=DEFAULT_PROPOSALS)
    p.add_argument("--authored", type=Path, default=DEFAULT_AUTHORED)
    p.add_argument("--formal", type=Path, default=DEFAULT_FORMAL)
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    p.add_argument(
        "--out",
        type=Path,
        default=WORK / "silver-publication-gate-reviewed-v1.json",
    )
    p.add_argument(
        "--queue-out",
        type=Path,
        default=WORK / "silver-publication-gate-work-queue-v1.json",
    )
    args = p.parse_args()

    proposals = json.loads(args.proposals.read_text(encoding="utf-8"))
    authored = json.loads(args.authored.read_text(encoding="utf-8"))
    formal = json.loads(args.formal.read_text(encoding="utf-8"))
    registry, queue = build_registry(
        proposals,
        authored,
        formal,
        inputs_from_manifest(args.manifest),
    )
    registry["inputs"] = {
        "proposals_sha256": sha256_file(args.proposals),
        "authored_sha256": sha256_file(args.authored),
        "formal_sha256": sha256_file(args.formal),
        "manifest_sha256": sha256_file(args.manifest),
    }
    args.out.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    queue["inputs"] = {
        "proposals_sha256": sha256_file(args.proposals),
        "registry_sha256": sha256_file(args.out),
    }
    args.queue_out.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(registry["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
