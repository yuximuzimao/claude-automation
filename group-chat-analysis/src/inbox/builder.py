"""Build the sole GPT input from validated records of a completed batch."""

from __future__ import annotations

from collections import defaultdict
import os
from pathlib import Path

from src.store import BatchStateStore, StateError, validate_message_record


TEXT_MESSAGE_TYPES = {"text", "system"}


def _record_matches_anchor(record: dict[str, object], anchor: dict[str, object]) -> bool:
    return (
        record["sequence"] == anchor["sequence"]
        and record["content_text"] == anchor["content_text"]
        and record.get("sender_display") == anchor["sender_display"]
        and record.get("timestamp_text") == anchor["timestamp_text"]
    )


def build_current_inbox(
    store: BatchStateStore,
    batch_id: str,
    records: list[dict[str, object]],
    destination: Path,
) -> str:
    """Build ``current.md`` only from the complete records of one closed batch.

    Every record is validated before any write.  The completed state's group
    set and saved continuous anchors must also be present in the supplied
    records, preventing an empty or truncated message set from masquerading as
    a completed analysis input.
    """

    state = store.load()
    if (
        state is None
        or state["batch_id"] != batch_id
        or state["status"] not in {"completed", "analyzed"}
    ):
        raise StateError("current.md requires a completed or analyzed batch")

    allowed_groups = set(state["groups"])
    grouped: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    group_display: dict[str, str] = {}

    for record in records:
        validate_message_record(record)
        if record["batch_id"] != batch_id:
            raise StateError("current.md records must belong to the active batch")

        group_key = record["group_key"]
        if group_key not in allowed_groups:
            raise StateError("current.md record group is not part of the active batch")

        display = record.get("group_display")
        if display is not None and not isinstance(display, str):
            raise StateError("group_display must be a string or null")
        resolved_display = display or group_key
        if group_key in group_display and group_display[group_key] != resolved_display:
            raise StateError("group_display must stay consistent within one batch")

        grouped[group_key].append(record)
        group_display[group_key] = resolved_display

    if set(grouped) != allowed_groups:
        raise StateError("completed batch records must cover every active group")

    for group_key, messages in grouped.items():
        messages.sort(key=lambda item: int(item["sequence"]))
        sequences = [int(item["sequence"]) for item in messages]
        if sequences != list(range(len(sequences))):
            raise StateError(f"{group_key} message sequences must be unique and contiguous")

        by_sequence = {int(item["sequence"]): item for item in messages}
        for anchor in state["groups"][group_key]["last_completed_anchor"]:
            record = by_sequence.get(anchor["sequence"])
            if record is None or not _record_matches_anchor(record, anchor):
                raise StateError("completed anchor does not match supplied message records")

    lines = [
        "# 群聊分析输入",
        "",
        f"batch_id: {batch_id}",
        f"message_count: {sum(len(items) for items in grouped.values())}",
        "",
    ]

    for group_key in sorted(grouped):
        lines.extend([f"## {group_display[group_key]}", ""])
        for record in grouped[group_key]:
            if record["message_type"] not in TEXT_MESSAGE_TYPES:
                continue
            timestamp = record.get("timestamp_text") or "未知时间"
            sender = record.get("sender_display") or "未知成员"
            lines.append(f"[{timestamp}] [{sender}] {record['content_text']}")
        lines.append("")

    content = "\n".join(lines).rstrip() + "\n"

    if state["status"] == "analyzed":
        if not destination.exists():
            raise StateError("analyzed batch requires its existing current.md")
        existing = destination.read_text(encoding="utf-8")
        if existing != content:
            raise StateError("analyzed batch cannot replace completed inbox content")
        return existing

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, destination)
    return content
