"""Crash-safe, idempotent persistence for the canonical messages.jsonl store."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Iterable

from .message_record import validate_message_record


class MessageStoreError(ValueError):
    """Raised when canonical message persistence would become ambiguous."""


class MessageStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load_all(self) -> list[dict[str, object]]:
        if not self.path.exists():
            return []
        records: list[dict[str, object]] = []
        seen_ids: set[str] = set()
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    if not isinstance(record, dict):
                        raise MessageStoreError(
                            f"messages.jsonl line {line_number} is not an object"
                        )
                    validate_message_record(record)
                    record_id = str(record["record_id"])
                    if record_id in seen_ids:
                        raise MessageStoreError(f"duplicate record_id in messages.jsonl: {record_id}")
                    seen_ids.add(record_id)
                    records.append(record)
        except json.JSONDecodeError as exc:
            raise MessageStoreError("messages.jsonl contains invalid JSON") from exc
        except OSError as exc:
            raise MessageStoreError("could not read messages.jsonl") from exc
        return records

    def records_for_batch(self, batch_id: str) -> list[dict[str, object]]:
        return [record for record in self.load_all() if record["batch_id"] == batch_id]

    def verify_batch(
        self,
        batch_id: str,
        records: Iterable[dict[str, object]],
    ) -> list[dict[str, object]]:
        incoming = [dict(record) for record in records]
        for record in incoming:
            validate_message_record(record)
            if record["batch_id"] != batch_id:
                raise MessageStoreError("all records must belong to batch_id")
        incoming = self._canonical_batch_order(incoming)
        self._validate_batch_sequences(incoming)
        existing = self._canonical_batch_order(self.records_for_batch(batch_id))
        if not existing:
            raise MessageStoreError(
                "completed batch is missing from canonical messages.jsonl"
            )
        if existing != incoming:
            raise MessageStoreError(
                "completed batch records differ from canonical messages.jsonl"
            )
        return existing

    def commit_batch(
        self,
        batch_id: str,
        records: Iterable[dict[str, object]],
    ) -> list[dict[str, object]]:
        """Durably commit one normalized batch before state becomes completed.

        If the same batch was already atomically installed before a crash, an
        identical retry is accepted. A different retry for the same batch is
        rejected instead of silently rewriting canonical history.
        """

        incoming = [dict(record) for record in records]
        if not batch_id or not incoming:
            raise MessageStoreError("batch_id and at least one message record are required")

        for record in incoming:
            validate_message_record(record)
            if record["batch_id"] != batch_id:
                raise MessageStoreError("all incoming records must belong to batch_id")
        incoming = self._canonical_batch_order(incoming)
        self._validate_batch_sequences(incoming)

        existing = self.load_all()
        existing_batch = self._canonical_batch_order(
            [record for record in existing if record["batch_id"] == batch_id]
        )
        if existing_batch:
            if existing_batch != incoming:
                raise MessageStoreError(
                    "batch already exists in messages.jsonl with different records"
                )
            return existing_batch

        existing_ids = {str(record["record_id"]) for record in existing}
        incoming_ids = [str(record["record_id"]) for record in incoming]
        if len(set(incoming_ids)) != len(incoming_ids):
            raise MessageStoreError("incoming batch contains duplicate record_id values")
        collision = existing_ids.intersection(incoming_ids)
        if collision:
            raise MessageStoreError(
                f"incoming record_id collides with canonical history: {sorted(collision)[0]}"
            )

        self._atomic_replace([*existing, *incoming])
        committed = self.records_for_batch(batch_id)
        if self._canonical_batch_order(committed) != incoming:
            raise MessageStoreError("post-write verification of committed batch failed")
        return self._canonical_batch_order(committed)

    @staticmethod
    def _canonical_batch_order(records: list[dict[str, object]]) -> list[dict[str, object]]:
        return sorted(records, key=lambda record: (str(record["group_key"]), int(record["sequence"])))

    @staticmethod
    def _validate_batch_sequences(records: list[dict[str, object]]) -> None:
        groups: dict[str, list[int]] = {}
        for record in records:
            groups.setdefault(str(record["group_key"]), []).append(int(record["sequence"]))
        for group_key, sequences in groups.items():
            if sequences != list(range(len(sequences))):
                raise MessageStoreError(
                    f"{group_key} message sequences must be contiguous from zero"
                )

    def _atomic_replace(self, records: list[dict[str, object]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.tmp-",
            dir=self.path.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
                for record in records:
                    handle.write(
                        json.dumps(
                            record,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                    )
                    handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            self._fsync_parent()
        except Exception:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    def _fsync_parent(self) -> None:
        try:
            directory_fd = os.open(self.path.parent, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
