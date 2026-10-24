"""Stable publication store for the reviewed Question Cluster Registry.

Versioned registry files produced during historical cleanup are snapshots, not durable
API names. This store publishes one content-validated current registry and retains
immutable hash-addressed snapshots for rollback/audit.

Existing reviewed questions/claims are monotonic:
- a published question cannot disappear;
- an existing claim cannot disappear or move to another question;
- reviewed scope fields cannot silently shrink;
- a canonical question may change only with explicit revision history.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from .analysis_release import sha256_json, write_json_atomic
from .quality import WORK
from .question_cluster_assignment_apply import _recount


REGISTRY_STATUS = "reviewed_question_cluster_registry_not_silver"
DEFAULT_CURRENT = WORK / "question-cluster-registry-current.json"
DEFAULT_META = WORK / "question-cluster-registry-current.meta.json"
DEFAULT_SNAPSHOTS = WORK.parent / "analysis" / "question-registries"


class QuestionRegistryError(ValueError):
    pass


def _cluster_map(registry: dict) -> dict[str, dict]:
    clusters = registry.get("clusters")
    if not isinstance(clusters, list):
        raise QuestionRegistryError("question registry clusters must be a list")
    result: dict[str, dict] = {}
    claim_owner: dict[str, str] = {}
    for cluster in clusters:
        if not isinstance(cluster, dict):
            raise QuestionRegistryError("question registry cluster must be an object")
        qid = str(cluster.get("question_id") or "").strip()
        if not qid:
            raise QuestionRegistryError("question registry cluster missing question_id")
        if qid in result:
            raise QuestionRegistryError(f"duplicate question_id: {qid}")
        if cluster.get("status") != "reviewed":
            raise QuestionRegistryError(f"question cluster is not reviewed: {qid}")
        question = str(cluster.get("canonical_question") or "").strip()
        if not question:
            raise QuestionRegistryError(f"question cluster missing canonical_question: {qid}")
        members = [str(x) for x in cluster.get("members", []) if str(x)]
        if not members:
            raise QuestionRegistryError(f"question cluster has no members: {qid}")
        if len(members) != len(set(members)):
            raise QuestionRegistryError(f"duplicate claim inside question cluster: {qid}")
        for cid in members:
            owner = claim_owner.get(cid)
            if owner and owner != qid:
                raise QuestionRegistryError(
                    f"claim belongs to multiple questions: {cid}: {owner}, {qid}"
                )
            claim_owner[cid] = qid
        result[qid] = cluster
    return result


def validate_registry(registry: dict) -> dict[str, dict]:
    if registry.get("schema_version") != 1:
        raise QuestionRegistryError("unsupported question registry schema")
    if registry.get("status") != REGISTRY_STATUS:
        raise QuestionRegistryError("unexpected question registry status")
    clusters = _cluster_map(registry)

    copied = copy.deepcopy(registry)
    _recount(copied)
    if copied.get("counts") != registry.get("counts"):
        raise QuestionRegistryError(
            f"question registry counts are stale: declared={registry.get('counts')} "
            f"actual={copied.get('counts')}"
        )
    return clusters


def _revision_authorizes(old: dict, new: dict) -> bool:
    old_question = str(old.get("canonical_question") or "")
    new_question = str(new.get("canonical_question") or "")
    if old_question == new_question:
        return True
    history = new.get("question_revision_history") or []
    if not isinstance(history, list) or not history:
        return False
    for row in reversed(history):
        if not isinstance(row, dict):
            continue
        if (
            str(row.get("from") or "") == old_question
            and str(row.get("to") or "") == new_question
            and str(row.get("reason") or "").strip()
        ):
            return True
    return False


def _require_nonshrinking_set(
    qid: str,
    field: str,
    old: dict,
    new: dict,
) -> None:
    before = {str(x) for x in old.get(field, [])}
    after = {str(x) for x in new.get(field, [])}
    missing = sorted(before - after)
    if missing:
        raise QuestionRegistryError(
            f"published question shrank {field}: {qid}: {missing}"
        )


def _boundary_key(row: dict) -> tuple[str, str, str]:
    return (
        str(row.get("inside_claim") or ""),
        str(row.get("outside_claim") or ""),
        str(row.get("reason") or ""),
    )


def validate_monotonic_update(previous: dict, candidate: dict) -> None:
    old_map = validate_registry(previous)
    new_map = validate_registry(candidate)

    missing_questions = sorted(set(old_map) - set(new_map))
    if missing_questions:
        raise QuestionRegistryError(
            f"published questions cannot disappear: {missing_questions[:10]}"
        )

    old_claim_owner = {
        str(cid): qid
        for qid, cluster in old_map.items()
        for cid in cluster.get("members", [])
    }
    new_claim_owner = {
        str(cid): qid
        for qid, cluster in new_map.items()
        for cid in cluster.get("members", [])
    }
    missing_claims = sorted(set(old_claim_owner) - set(new_claim_owner))
    if missing_claims:
        raise QuestionRegistryError(
            f"published claims cannot disappear: {missing_claims[:10]}"
        )
    moved = sorted(
        cid
        for cid, old_qid in old_claim_owner.items()
        if new_claim_owner.get(cid) != old_qid
    )
    if moved:
        examples = [
            (cid, old_claim_owner[cid], new_claim_owner.get(cid))
            for cid in moved[:10]
        ]
        raise QuestionRegistryError(
            f"published claims cannot move between questions: {examples}"
        )

    for qid, old in old_map.items():
        new = new_map[qid]
        if not _revision_authorizes(old, new):
            raise QuestionRegistryError(
                f"canonical question changed without explicit revision history: {qid}"
            )
        for field in ("members", "source_cards", "entities", "kinds", "certainties"):
            _require_nonshrinking_set(qid, field, old, new)

        old_boundaries = {
            _boundary_key(row)
            for row in old.get("boundary_negatives", [])
            if isinstance(row, dict)
        }
        new_boundaries = {
            _boundary_key(row)
            for row in new.get("boundary_negatives", [])
            if isinstance(row, dict)
        }
        missing_boundaries = sorted(old_boundaries - new_boundaries)
        if missing_boundaries:
            raise QuestionRegistryError(
                f"published question lost boundary negatives: {qid}: "
                f"{missing_boundaries[:5]}"
            )


class QuestionRegistryStore:
    def __init__(
        self,
        *,
        current_path: Path,
        snapshots_dir: Path,
        metadata_path: Path | None = None,
    ) -> None:
        self.current_path = current_path
        self.snapshots_dir = snapshots_dir
        self.metadata_path = metadata_path or current_path.with_suffix(".meta.json")

    @staticmethod
    def _load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def current(self) -> dict | None:
        if not self.current_path.exists():
            return None
        return self._load(self.current_path)

    def publish(
        self,
        candidate: dict,
        *,
        source_label: str,
        expected_previous_sha256: str | None = None,
    ) -> dict:
        validate_registry(candidate)
        previous = self.current()

        previous_sha = sha256_json(previous) if previous is not None else None
        if expected_previous_sha256 is not None and previous_sha != expected_previous_sha256:
            raise QuestionRegistryError(
                "current question registry changed since the reviewed update was prepared"
            )
        if previous is not None:
            validate_monotonic_update(previous, candidate)

        candidate_sha = sha256_json(candidate)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = self.snapshots_dir / f"{candidate_sha}.json"
        if snapshot_path.exists():
            existing = self._load(snapshot_path)
            if existing != candidate:
                raise QuestionRegistryError(
                    "hash-addressed question registry snapshot has conflicting content"
                )
        else:
            write_json_atomic(snapshot_path, candidate)

        if previous == candidate:
            status = "unchanged"
        else:
            write_json_atomic(self.current_path, candidate)
            status = "published"

        meta = {
            "schema_version": 1,
            "status": "question_registry_current",
            "current_sha256": candidate_sha,
            "previous_sha256": previous_sha,
            "source_label": str(source_label),
            "snapshot": str(snapshot_path),
            "counts": copy.deepcopy(candidate.get("counts") or {}),
        }
        write_json_atomic(self.metadata_path, meta)
        return {
            "status": status,
            "current_sha256": candidate_sha,
            "previous_sha256": previous_sha,
            "snapshot": str(snapshot_path),
            "counts": copy.deepcopy(candidate.get("counts") or {}),
        }

    def publish_file(
        self,
        candidate_path: Path,
        *,
        expected_previous_sha256: str | None = None,
    ) -> dict:
        if not candidate_path.is_file():
            raise QuestionRegistryError(
                f"question registry candidate does not exist: {candidate_path}"
            )
        return self.publish(
            self._load(candidate_path),
            source_label=str(candidate_path),
            expected_previous_sha256=expected_previous_sha256,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--current", type=Path, default=DEFAULT_CURRENT)
    parser.add_argument("--meta", type=Path, default=DEFAULT_META)
    parser.add_argument("--snapshots", type=Path, default=DEFAULT_SNAPSHOTS)
    parser.add_argument("--expected-previous-sha256")
    args = parser.parse_args()

    store = QuestionRegistryStore(
        current_path=args.current,
        snapshots_dir=args.snapshots,
        metadata_path=args.meta,
    )
    result = store.publish_file(
        args.candidate,
        expected_previous_sha256=args.expected_previous_sha256,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
