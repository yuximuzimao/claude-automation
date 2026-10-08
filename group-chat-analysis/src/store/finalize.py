"""Finalize one normalized capture batch without allowing false completion."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Iterable

from src.inbox import build_current_inbox

from .batch_state import Anchor, BatchStateStore, MIN_ANCHOR_COUNT, StateError
from .message_record import validate_message_record
from .message_store import MessageStore


class BatchFinalizeError(ValueError):
    """Raised when durable messages, state, and inbox cannot be reconciled safely."""


def anchors_from_records(
    records: Iterable[dict[str, object]],
    *,
    count: int = MIN_ANCHOR_COUNT,
) -> dict[str, list[Anchor]]:
    if count < MIN_ANCHOR_COUNT:
        raise BatchFinalizeError("anchor count cannot be below the state safety minimum")

    grouped: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    for record in records:
        validate_message_record(record)
        grouped[str(record["group_key"])].append(record)

    anchors: dict[str, list[Anchor]] = {}
    for group_key, group_records in grouped.items():
        ordered = sorted(group_records, key=lambda item: int(item["sequence"]))
        if len(ordered) < count:
            raise BatchFinalizeError(
                f"{group_key} needs at least {count} normalized messages to complete"
            )
        selected = ordered[-count:]
        anchors[group_key] = [
            Anchor(
                sequence=int(record["sequence"]),
                content_text=str(record["content_text"]),
                sender_display=record.get("sender_display"),
                timestamp_text=record.get("timestamp_text"),
            )
            for record in selected
        ]
    return anchors


def incremental_anchors_from_records(
    state: dict,
    records: Iterable[dict[str, object]],
    *,
    count: int = MIN_ANCHOR_COUNT,
) -> dict[str, list[Anchor]]:
    if count < MIN_ANCHOR_COUNT:
        raise BatchFinalizeError("anchor count cannot be below the state safety minimum")
    if state.get("batch_kind") != "incremental":
        raise BatchFinalizeError("incremental anchors require an incremental batch")

    grouped: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    for record in records:
        validate_message_record(record)
        grouped[str(record["group_key"])].append(record)

    anchors: dict[str, list[Anchor]] = {}
    for group_key, progress in state["groups"].items():
        start_anchor = list(progress["start_anchor"])
        if len(start_anchor) < count:
            raise BatchFinalizeError(f"{group_key} is missing its previous completed anchor")
        ordered_new = sorted(grouped.get(group_key, []), key=lambda item: int(item["sequence"]))
        combined: list[dict[str, object]] = [*start_anchor, *ordered_new]
        selected = combined[-count:]
        anchors[group_key] = [
            Anchor(
                sequence=index,
                content_text=str(item["content_text"]),
                sender_display=item.get("sender_display"),
                timestamp_text=item.get("timestamp_text"),
            )
            for index, item in enumerate(selected)
        ]
    return anchors


def finalize_incremental_batch(
    *,
    state_store: BatchStateStore,
    message_store: MessageStore,
    batch_id: str,
    records: Iterable[dict[str, object]],
    completed_at: str,
    current_destination: Path,
) -> str:
    """Finalize only new incremental messages while carrying forward anchors.

    An incremental batch may legitimately contain zero new messages for one or
    every group. In that case no synthetic/duplicate anchor records are written
    to messages.jsonl; durable state + raw pages remain the recovery evidence.
    """

    incoming = [dict(record) for record in records]
    for record in incoming:
        validate_message_record(record)
        if record["batch_id"] != batch_id:
            raise BatchFinalizeError("incremental records must belong to batch_id")

    state = state_store.load()
    if state is None or state["batch_id"] != batch_id:
        raise BatchFinalizeError("active batch state does not match batch_id")
    if state.get("batch_kind") != "incremental":
        raise BatchFinalizeError("incremental finalization requires batch_kind=incremental")

    if state["status"] == "incomplete":
        committed = message_store.commit_batch(batch_id, incoming) if incoming else []
        anchors = incremental_anchors_from_records(state, committed)
        state_store.complete_batch(
            batch_id,
            anchors=anchors,
            completed_at=completed_at,
        )
    elif state["status"] in {"completed", "analyzed"}:
        if incoming:
            committed = message_store.verify_batch(batch_id, incoming)
        else:
            committed = message_store.records_for_batch(batch_id)
            if committed:
                raise BatchFinalizeError("completed empty incremental batch unexpectedly has canonical records")
    else:
        raise StateError("unsupported batch state")

    return build_current_inbox(
        state_store,
        batch_id,
        committed,
        current_destination,
    )


def finalize_batch(
    *,
    state_store: BatchStateStore,
    message_store: MessageStore,
    batch_id: str,
    records: Iterable[dict[str, object]],
    completed_at: str,
    current_destination: Path,
) -> str:
    """Make normalized messages durable, then complete state, then build inbox.

    Recovery semantics:
    - crash after messages replace but before state completion: retry accepts the
      identical durable batch and continues the state transition;
    - crash after state completion but before current.md: retry verifies the
      already-completed batch against canonical messages and rebuilds current.md;
    - completed state with absent/different canonical messages is treated as
      corruption and is never silently repaired.
    """

    incoming = [dict(record) for record in records]
    if not incoming:
        raise BatchFinalizeError("cannot finalize an empty normalized batch")

    state = state_store.load()
    if state is None or state["batch_id"] != batch_id:
        raise BatchFinalizeError("active batch state does not match batch_id")

    if state["status"] == "incomplete":
        committed = message_store.commit_batch(batch_id, incoming)
        anchors = anchors_from_records(committed)
        if set(anchors) != set(state["groups"]):
            raise BatchFinalizeError(
                "normalized records must cover every group in the active batch"
            )
        state_store.complete_batch(
            batch_id,
            anchors=anchors,
            completed_at=completed_at,
        )
    elif state["status"] in {"completed", "analyzed"}:
        committed = message_store.verify_batch(batch_id, incoming)
    else:
        raise StateError("unsupported batch state")

    return build_current_inbox(
        state_store,
        batch_id,
        committed,
        current_destination,
    )
