"""One-shot per-group anchor checkpoints for the next incremental capture.

A checkpoint bridges a newer independently completed capture (for example a
history-day backfill) into the next incremental run without rewriting the
previous main batch.  It is intentionally scoped to one base batch id: after a
new incremental batch is created, the old checkpoint is stale and ignored.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Iterable

from .batch_state import ANCHOR_KEYS, MIN_ANCHOR_COUNT, BatchStateStore
from .message_store import MessageStore


CHECKPOINT_SCHEMA_VERSION = "1"
CHECKPOINT_STATUS = "ready"


class IncrementalCheckpointError(ValueError):
    """Raised when an anchor checkpoint cannot be proven safe."""


def _sha256_file(path: Path) -> str:
    if not path.is_file():
        raise IncrementalCheckpointError(f"required checkpoint source file is missing: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _valid_datetime(value: object) -> bool:
    if not isinstance(value, str) or "T" not in value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _anchor_identity(anchor: dict[str, object]) -> tuple[object, object, object]:
    return (
        anchor.get("content_text"),
        anchor.get("sender_display"),
        anchor.get("timestamp_text"),
    )


def _validate_anchor(anchor: object) -> None:
    if not isinstance(anchor, dict) or set(anchor) != ANCHOR_KEYS:
        raise IncrementalCheckpointError("checkpoint anchor fields are invalid")
    sequence = anchor.get("sequence")
    if (
        not isinstance(sequence, int)
        or isinstance(sequence, bool)
        or sequence < 0
        or not isinstance(anchor.get("content_text"), str)
        or not anchor["content_text"]
    ):
        raise IncrementalCheckpointError("checkpoint anchor is invalid")
    for field in ("sender_display", "timestamp_text"):
        value = anchor.get(field)
        if value is not None and not isinstance(value, str):
            raise IncrementalCheckpointError("checkpoint anchor identity field is invalid")


def _validate_anchor_list(anchors: object) -> list[dict[str, object]]:
    if not isinstance(anchors, list) or len(anchors) < MIN_ANCHOR_COUNT:
        raise IncrementalCheckpointError(
            f"checkpoint requires at least {MIN_ANCHOR_COUNT} continuous anchors"
        )
    copied = [dict(anchor) for anchor in anchors]
    for anchor in copied:
        _validate_anchor(anchor)
    sequences = [int(anchor["sequence"]) for anchor in copied]
    if sequences != list(range(sequences[0], sequences[0] + len(sequences))):
        raise IncrementalCheckpointError("checkpoint anchor sequence must be adjacent and ordered")
    return copied


def _validate_checkpoint(document: object) -> dict:
    if not isinstance(document, dict):
        raise IncrementalCheckpointError("incremental checkpoint must be an object")
    if set(document) != {
        "schema_version",
        "status",
        "base_batch_id",
        "created_at",
        "groups",
    }:
        raise IncrementalCheckpointError("incremental checkpoint fields do not match contract")
    if document.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
        raise IncrementalCheckpointError("unsupported incremental checkpoint schema")
    if document.get("status") != CHECKPOINT_STATUS:
        raise IncrementalCheckpointError("incremental checkpoint is not ready")
    if not isinstance(document.get("base_batch_id"), str) or not document["base_batch_id"]:
        raise IncrementalCheckpointError("incremental checkpoint base_batch_id is required")
    if not _valid_datetime(document.get("created_at")):
        raise IncrementalCheckpointError("incremental checkpoint created_at is invalid")
    groups = document.get("groups")
    if not isinstance(groups, dict) or not groups:
        raise IncrementalCheckpointError("incremental checkpoint needs at least one group")

    expected_group_fields = {
        "source_runtime",
        "source_batch_id",
        "source_state_sha256",
        "source_messages_sha256",
        "anchor",
    }
    for group_key, row in groups.items():
        if not isinstance(group_key, str) or not group_key:
            raise IncrementalCheckpointError("checkpoint group key is invalid")
        if not isinstance(row, dict) or set(row) != expected_group_fields:
            raise IncrementalCheckpointError(
                f"checkpoint group fields do not match contract: {group_key}"
            )
        for field in (
            "source_runtime",
            "source_batch_id",
            "source_state_sha256",
            "source_messages_sha256",
        ):
            if not isinstance(row.get(field), str) or not row[field]:
                raise IncrementalCheckpointError(
                    f"checkpoint group field is invalid: {group_key}.{field}"
                )
        for field in ("source_state_sha256", "source_messages_sha256"):
            value = row[field]
            if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
                raise IncrementalCheckpointError(
                    f"checkpoint hash is invalid: {group_key}.{field}"
                )
        _validate_anchor_list(row["anchor"])
    return document


def _atomic_write_json(path: Path, value: dict) -> None:
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
        try:
            dir_fd = os.open(path.parent, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except Exception:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


class IncrementalCheckpointStore:
    def __init__(
        self,
        project_root: Path,
        runtime_root: Path,
        *,
        current_path: Path | None = None,
        snapshots_dir: Path | None = None,
    ) -> None:
        self.project_root = project_root.resolve()
        self.runtime_root = (
            runtime_root.resolve()
            if runtime_root.is_absolute()
            else (self.project_root / runtime_root).resolve()
        )
        self.current_path = current_path or (
            self.runtime_root / "state" / "incremental-checkpoint-v1.json"
        )
        self.snapshots_dir = snapshots_dir or (
            self.runtime_root / "state" / "incremental-checkpoints"
        )
        self.main_state = BatchStateStore(
            self.runtime_root / "state" / "batch-state.json"
        )

    def _resolve_runtime(self, path: Path) -> Path:
        resolved = path.resolve() if path.is_absolute() else (self.project_root / path).resolve()
        try:
            resolved.relative_to(self.project_root)
        except ValueError as exc:
            raise IncrementalCheckpointError(
                f"checkpoint source runtime escapes project root: {path}"
            ) from exc
        return resolved

    def _relative_runtime(self, path: Path) -> str:
        resolved = self._resolve_runtime(path)
        return resolved.relative_to(self.project_root).as_posix()

    def load(self) -> dict | None:
        if not self.current_path.exists():
            return None
        try:
            document = json.loads(self.current_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IncrementalCheckpointError(
                "incremental checkpoint is not valid JSON"
            ) from exc
        return _validate_checkpoint(document)

    @staticmethod
    def _records_anchor(
        records: Iterable[dict[str, object]],
        *,
        group_key: str,
        count: int,
    ) -> list[tuple[object, object, object]]:
        selected = sorted(
            (
                row
                for row in records
                if str(row.get("group_key") or "") == group_key
            ),
            key=lambda row: int(row["sequence"]),
        )[-count:]
        if len(selected) < count:
            raise IncrementalCheckpointError(
                f"source batch does not contain enough records for anchor: {group_key}"
            )
        return [_anchor_identity(row) for row in selected]

    def _validate_source_row(
        self,
        group_key: str,
        row: dict,
    ) -> list[dict[str, object]]:
        source_runtime = self._resolve_runtime(Path(row["source_runtime"]))
        state_path = source_runtime / "state" / "batch-state.json"
        messages_path = source_runtime / "messages" / "messages.jsonl"
        if _sha256_file(state_path) != row["source_state_sha256"]:
            raise IncrementalCheckpointError(
                f"checkpoint source state changed after review: {group_key}"
            )
        if _sha256_file(messages_path) != row["source_messages_sha256"]:
            raise IncrementalCheckpointError(
                f"checkpoint source messages changed after review: {group_key}"
            )

        state = BatchStateStore(state_path).load()
        if state is None or state["batch_id"] != row["source_batch_id"]:
            raise IncrementalCheckpointError(
                f"checkpoint source batch no longer matches: {group_key}"
            )
        if state["status"] not in {"completed", "analyzed"}:
            raise IncrementalCheckpointError(
                f"checkpoint source batch is not completed: {group_key}"
            )
        progress = state["groups"].get(group_key)
        if progress is None or not progress["capture_complete"]:
            raise IncrementalCheckpointError(
                f"checkpoint source group is not completed: {group_key}"
            )

        anchor = _validate_anchor_list(row["anchor"])
        if progress["last_completed_anchor"] != anchor:
            raise IncrementalCheckpointError(
                f"checkpoint source completed anchor changed: {group_key}"
            )

        records = MessageStore(messages_path).records_for_batch(state["batch_id"])
        expected_identities = self._records_anchor(
            records,
            group_key=group_key,
            count=len(anchor),
        )
        if [_anchor_identity(item) for item in anchor] != expected_identities:
            raise IncrementalCheckpointError(
                f"checkpoint source anchor does not match canonical tail: {group_key}"
            )
        return anchor

    def create_from_completed_runtime(
        self,
        *,
        source_runtime: Path,
        group_key: str,
        created_at: str,
    ) -> dict:
        if not group_key or not _valid_datetime(created_at):
            raise IncrementalCheckpointError("valid group_key and created_at are required")

        base = self.main_state.load()
        if base is None or base["status"] not in {"completed", "analyzed"}:
            raise IncrementalCheckpointError(
                "main runtime needs a completed/analyzed base batch"
            )
        if group_key not in base["groups"]:
            raise IncrementalCheckpointError(
                f"checkpoint group is not part of main runtime: {group_key}"
            )

        source_root = self._resolve_runtime(source_runtime)
        state_path = source_root / "state" / "batch-state.json"
        messages_path = source_root / "messages" / "messages.jsonl"
        source_state = BatchStateStore(state_path).load()
        if source_state is None or source_state["status"] not in {"completed", "analyzed"}:
            raise IncrementalCheckpointError("source runtime is not completed")
        progress = source_state["groups"].get(group_key)
        if progress is None or not progress["capture_complete"]:
            raise IncrementalCheckpointError(
                f"source runtime does not contain a completed group: {group_key}"
            )
        anchor = _validate_anchor_list(progress["last_completed_anchor"])

        source_records = MessageStore(messages_path).records_for_batch(
            source_state["batch_id"]
        )
        expected_identities = self._records_anchor(
            source_records,
            group_key=group_key,
            count=len(anchor),
        )
        if [_anchor_identity(item) for item in anchor] != expected_identities:
            raise IncrementalCheckpointError(
                "source completed anchor does not match canonical message tail"
            )

        existing = self.load()
        groups: dict[str, dict] = {}
        if existing is not None and existing["base_batch_id"] == base["batch_id"]:
            groups = {
                key: json.loads(json.dumps(value, ensure_ascii=False))
                for key, value in existing["groups"].items()
            }

        groups[group_key] = {
            "source_runtime": self._relative_runtime(source_root),
            "source_batch_id": source_state["batch_id"],
            "source_state_sha256": _sha256_file(state_path),
            "source_messages_sha256": _sha256_file(messages_path),
            "anchor": anchor,
        }
        document = {
            "schema_version": CHECKPOINT_SCHEMA_VERSION,
            "status": CHECKPOINT_STATUS,
            "base_batch_id": base["batch_id"],
            "created_at": created_at,
            "groups": dict(sorted(groups.items())),
        }
        _validate_checkpoint(document)

        payload = json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        snapshot = self.snapshots_dir / f"{digest}.json"
        if not snapshot.exists():
            _atomic_write_json(snapshot, document)
        else:
            persisted = json.loads(snapshot.read_text(encoding="utf-8"))
            if persisted != document:
                raise IncrementalCheckpointError(
                    "hash-addressed checkpoint snapshot has conflicting content"
                )
        _atomic_write_json(self.current_path, document)
        return {
            "status": "ready",
            "base_batch_id": base["batch_id"],
            "group_key": group_key,
            "source_batch_id": source_state["batch_id"],
            "checkpoint_sha256": digest,
            "snapshot": str(snapshot),
        }

    def resolve_for_next_batch(
        self,
        *,
        previous_state: dict,
        group_keys: Iterable[str],
    ) -> dict[str, list[dict[str, object]]]:
        document = self.load()
        if document is None:
            return {}
        if previous_state.get("status") not in {"completed", "analyzed"}:
            raise IncrementalCheckpointError(
                "checkpoint can only be applied after a completed/analyzed batch"
            )
        if document["base_batch_id"] != previous_state.get("batch_id"):
            # Expected after the checkpoint has already been consumed by a newer
            # completed batch.  A stale one-shot checkpoint must never override it.
            return {}

        requested = {str(key) for key in group_keys}
        unknown = sorted(set(document["groups"]) - requested)
        if unknown:
            raise IncrementalCheckpointError(
                f"checkpoint contains groups outside the requested incremental batch: {unknown}"
            )

        overrides: dict[str, list[dict[str, object]]] = {}
        for group_key, row in document["groups"].items():
            overrides[group_key] = self._validate_source_row(group_key, row)
        return overrides
