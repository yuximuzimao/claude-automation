"""Durable contracts for reviewed analysis publication and rollback.

This module deliberately contains no semantic judgement.  A model/manual analysis
must first create a reviewed receipt bound to one completed batch.  The deterministic
runner then validates hashes, runs quality/render stages, freezes an immutable
release, atomically switches the current release symlink, and only then may mark the
capture batch analyzed.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Iterable


WORK_PACKAGE_SCHEMA_VERSION = "1"
REVIEW_RECEIPT_SCHEMA_VERSION = "1"
RESULT_SCHEMA_VERSION = "1"
REVIEW_RECEIPT_STATUS = "reviewed_analysis_ready"

WORK_PACKAGE_ARTIFACTS: dict[str, str] = {
    "question_registry": "runtime/analysis-work/question-cluster-registry-current.json",
    "silver_knowledge": "runtime/analysis-work/silver-knowledge-v1.json",
    "reviewed_semantic_decisions": "runtime/analysis-work/reviewed-semantic-decisions-v1.json",
    "reviewed_semantic_state": "runtime/analysis-work/reviewed-semantic-state-v1.json",
    "infinite_dossier": "runtime/analysis-work/infinite-dossier-v1.json",
    "atomic_claims_reviewed": "runtime/analysis-work/atomic-claims-reviewed-v1.json",
    "verified_source_anchors": "runtime/analysis-work/verified-source-anchors-v1.json",
    "silver_candidates": "runtime/analysis-work/silver-candidates-v1.json",
    "blackword_dictionary": "runtime/analysis-work/normalized-v1/blackword-dictionary-v1.md",
}

REQUIRED_ARTIFACTS: dict[str, str] = {
    "silver_candidates": "runtime/analysis-work/silver-candidates-v1.json",
    "silver_knowledge": "runtime/analysis-work/silver-knowledge-v1.json",
    "verified_source_anchors": "runtime/analysis-work/verified-source-anchors-v1.json",
    "reviewed_semantic_decisions": "runtime/analysis-work/reviewed-semantic-decisions-v1.json",
    "infinite_dossier": "runtime/analysis-work/infinite-dossier-v1.json",
    "atomic_claims_reviewed": "runtime/analysis-work/atomic-claims-reviewed-v1.json",
    "no_claim_reviewed": "runtime/analysis-work/atomic-claim-no-claim-reviewed-v1.json",
    "question_registry": "runtime/analysis-work/question-cluster-registry-current.json",
    "silver_routing": "runtime/analysis-work/question-cluster-silver-routing-reviewed-v1.json",
    "silver_consolidation": "runtime/analysis-work/silver-draft-consolidation-reviewed-v1.json",
    "silver_publication": "runtime/analysis-work/silver-publication-gate-reviewed-v1.json",
    "semantic_corrections": "runtime/analysis-work/semantic-correction-queue-v1.json",
    "topic_cards": "runtime/analysis-work/topic-cards-v1",
    "full_history_chunks": "runtime/analysis-work/full-history-chunks",
    "reorg_triage": "runtime/analysis-work/reorg-v2/card-triage.json",
    "normalized_collections": "runtime/analysis-work/normalized-v1/collections",
    "blackword_dictionary": "runtime/analysis-work/normalized-v1/blackword-dictionary-v1.md",
}

DERIVED_RELEASE_FILES: dict[str, str] = {
    "silver_candidates": "runtime/analysis-work/silver-candidates-v1.json",
    "silver_knowledge": "runtime/analysis-work/silver-knowledge-v1.json",
    "infinite_dossier": "runtime/analysis-work/infinite-dossier-v1.json",
    "first_read_projection": "runtime/analysis-work/first-read-projection-v1.json",
    "reviewed_semantic_state": "runtime/analysis-work/reviewed-semantic-state-v1.json",
}

CURRENT_HEADER_RE = re.compile(r"^(batch_id|message_count):\s*(.*)$", re.M)


class AnalysisReleaseError(ValueError):
    """Raised when publication lineage or release state would become ambiguous."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise AnalysisReleaseError(f"expected file does not exist: {path}")
    return sha256_bytes(path.read_bytes())


def sha256_json(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(payload)


def sha256_path(path: Path) -> str:
    """Hash one file or a directory tree deterministically.

    Directory hashes include each relative path plus the file content hash so a
    rename, add, remove, or content change all change the digest.
    """
    if path.is_file():
        return sha256_file(path)
    if not path.is_dir():
        raise AnalysisReleaseError(f"analysis artifact does not exist: {path}")

    entries: list[dict[str, str]] = []
    for child in sorted(p for p in path.rglob("*") if p.is_file()):
        if child.is_symlink():
            raise AnalysisReleaseError(f"analysis artifact tree contains symlink: {child}")
        entries.append({
            "path": child.relative_to(path).as_posix(),
            "sha256": sha256_file(child),
        })
    return sha256_json(entries)


def project_path(project_root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise AnalysisReleaseError("artifact path must be a non-empty project-relative path")
    root = project_root.resolve()
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise AnalysisReleaseError(f"artifact path escapes project root: {relative}") from exc
    return resolved


def parse_current_header(content: str) -> tuple[str, int]:
    values = {key: value.strip() for key, value in CURRENT_HEADER_RE.findall(content)}
    batch_id = values.get("batch_id", "")
    count_text = values.get("message_count", "")
    if not batch_id:
        raise AnalysisReleaseError("current.md is missing batch_id")
    try:
        message_count = int(count_text)
    except ValueError as exc:
        raise AnalysisReleaseError("current.md has invalid message_count") from exc
    if message_count < 0:
        raise AnalysisReleaseError("current.md message_count must be non-negative")
    return batch_id, message_count


def canonical_batch_sha256(records: Iterable[dict[str, object]]) -> str:
    ordered = sorted(
        (dict(record) for record in records),
        key=lambda row: (str(row.get("group_key", "")), int(row.get("sequence", -1))),
    )
    return sha256_json(ordered)


def validate_review_receipt(
    receipt: dict,
    *,
    project_root: Path,
    batch_id: str,
    current_sha256: str,
    message_count: int,
) -> dict[str, dict[str, str]]:
    if receipt.get("schema_version") != REVIEW_RECEIPT_SCHEMA_VERSION:
        raise AnalysisReleaseError("unsupported reviewed analysis receipt schema")
    if receipt.get("status") != REVIEW_RECEIPT_STATUS:
        raise AnalysisReleaseError("analysis receipt is not reviewed and ready")
    if receipt.get("batch_id") != batch_id:
        raise AnalysisReleaseError("analysis receipt batch_id does not match completed batch")

    source = receipt.get("source")
    if not isinstance(source, dict):
        raise AnalysisReleaseError("analysis receipt source must be an object")
    if source.get("current_sha256") != current_sha256:
        raise AnalysisReleaseError("analysis receipt current.md hash is stale")
    if source.get("message_count") != message_count:
        raise AnalysisReleaseError("analysis receipt message_count is stale")

    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, dict):
        raise AnalysisReleaseError("analysis receipt artifacts must be an object")

    normalized: dict[str, dict[str, str]] = {}
    for key, expected_relative in REQUIRED_ARTIFACTS.items():
        row = artifacts.get(key)
        if not isinstance(row, dict):
            raise AnalysisReleaseError(f"analysis receipt missing artifact: {key}")
        relative = row.get("path")
        expected_sha = row.get("sha256")
        if relative != expected_relative:
            raise AnalysisReleaseError(
                f"analysis receipt artifact path mismatch for {key}: {relative!r}"
            )
        if not isinstance(expected_sha, str) or len(expected_sha) != 64:
            raise AnalysisReleaseError(f"analysis receipt artifact hash invalid for {key}")
        path = project_path(project_root, expected_relative)
        actual_sha = sha256_path(path)
        if actual_sha != expected_sha:
            raise AnalysisReleaseError(f"analysis artifact changed after review: {key}")
        normalized[key] = {"path": expected_relative, "sha256": actual_sha}

    reviewed_at = receipt.get("reviewed_at")
    reviewer = receipt.get("reviewer")
    if not isinstance(reviewed_at, str) or "T" not in reviewed_at:
        raise AnalysisReleaseError("analysis receipt reviewed_at is required")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise AnalysisReleaseError("analysis receipt reviewer is required")
    return normalized


def write_json_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.tmp-", dir=path.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        fsync_dir(path.parent)
    except Exception:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_symlink(link: Path, target: str) -> None:
    """Atomically replace a symlink without following the existing target."""
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists() and not link.is_symlink():
        raise AnalysisReleaseError(f"publication pointer is not a symlink: {link}")
    temp = link.with_name(f".{link.name}.tmp-{os.getpid()}")
    temp.unlink(missing_ok=True)
    os.symlink(target, temp)
    os.replace(temp, link)
    fsync_dir(link.parent)


def ensure_static_symlink(link: Path, target: str) -> None:
    """Create a stable convenience symlink once and reject divergent definitions."""
    if link.is_symlink():
        if os.readlink(link) != target:
            raise AnalysisReleaseError(
                f"existing report symlink has unexpected target: {link}"
            )
        return
    if link.exists():
        raise AnalysisReleaseError(f"report publication path already exists: {link}")
    link.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(target, link)
    fsync_dir(link.parent)
