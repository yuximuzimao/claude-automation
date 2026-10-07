"""Validation for persisted normalized message records.

The JSON Schema remains the field/enum authority.  This module loads those
structural values from the schema and implements the small amount of runtime
validation needed without adding a third-party JSON-Schema dependency.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Mapping


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "message-record.schema.json"
_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
MESSAGE_RECORD_KEYS = frozenset(_SCHEMA["properties"])
MESSAGE_RECORD_REQUIRED = frozenset(_SCHEMA["required"])
MESSAGE_TYPES = frozenset(_SCHEMA["properties"]["message_type"]["enum"])
MESSAGE_SOURCE = _SCHEMA["properties"]["source"]["const"]
MESSAGE_SCHEMA_VERSION = _SCHEMA["properties"]["schema_version"]["const"]


class MessageRecordError(ValueError):
    """Raised when a normalized record violates the persisted contract."""


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _require_optional_string(record: Mapping[str, object], field: str) -> None:
    value = record.get(field)
    if value is not None and not isinstance(value, str):
        raise MessageRecordError(f"{field} must be a string or null")


def _require_datetime(value: object, field: str) -> None:
    if not isinstance(value, str) or "T" not in value:
        raise MessageRecordError(f"{field} must be a date-time string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MessageRecordError(f"{field} must be a valid date-time") from exc
    if parsed.tzinfo is None:
        raise MessageRecordError(f"{field} must include a timezone")


def _validate_capture_refs(value: object) -> None:
    if not isinstance(value, list):
        raise MessageRecordError("capture_refs must be an array")
    for ref in value:
        if not isinstance(ref, dict) or set(ref) - {"page_index", "bbox"}:
            raise MessageRecordError("invalid capture_ref")
        page_index = ref.get("page_index")
        if not isinstance(page_index, int) or isinstance(page_index, bool) or page_index < 0:
            raise MessageRecordError("capture_ref.page_index must be non-negative")
        bbox = ref.get("bbox")
        if bbox is None:
            continue
        if not isinstance(bbox, dict) or set(bbox) != {"x", "y", "width", "height"}:
            raise MessageRecordError("invalid capture_ref bbox")
        if not all(_is_number(bbox[field]) for field in ("x", "y", "width", "height")):
            raise MessageRecordError("capture_ref bbox values must be numeric")
        if bbox["width"] < 0 or bbox["height"] < 0:
            raise MessageRecordError("capture_ref bbox size must be non-negative")


def validate_message_record(record: Mapping[str, object]) -> None:
    """Validate one record before it crosses the persistent/inbox boundary."""

    keys = set(record)
    unknown = keys - MESSAGE_RECORD_KEYS
    missing = MESSAGE_RECORD_REQUIRED - keys
    if unknown:
        raise MessageRecordError(f"unknown message record fields: {sorted(unknown)}")
    if missing:
        raise MessageRecordError(f"missing message record fields: {sorted(missing)}")

    if record.get("schema_version") != MESSAGE_SCHEMA_VERSION:
        raise MessageRecordError("unsupported message schema version")
    for field in ("record_id", "batch_id", "group_key"):
        if not isinstance(record.get(field), str) or not record[field]:
            raise MessageRecordError(f"{field} is required")

    _require_optional_string(record, "group_display")
    _require_optional_string(record, "sender_display")
    _require_optional_string(record, "timestamp_text")
    _require_optional_string(record, "timestamp")

    sequence = record.get("sequence")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
        raise MessageRecordError("sequence must be a non-negative integer")

    if record.get("message_type") not in MESSAGE_TYPES:
        raise MessageRecordError("unsupported message_type")
    if not isinstance(record.get("content_text"), str):
        raise MessageRecordError("content_text must be a string")

    confidence = record.get("ocr_confidence")
    if confidence is not None and (
        not _is_number(confidence) or confidence < 0 or confidence > 1
    ):
        raise MessageRecordError("ocr_confidence must be between 0 and 1")

    _require_datetime(record.get("observed_at"), "observed_at")
    timestamp = record.get("timestamp")
    if timestamp is not None:
        _require_datetime(timestamp, "timestamp")

    if record.get("source") != MESSAGE_SOURCE:
        raise MessageRecordError("unsupported message source")

    if "capture_refs" in record:
        _validate_capture_refs(record["capture_refs"])
