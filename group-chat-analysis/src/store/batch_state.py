"""Resumable capture batch state with atomic JSON replacement."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import tempfile


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "batch-state.schema.json"
_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
STATE_SCHEMA_VERSION = _SCHEMA["properties"]["schema_version"]["const"]
STATE_STATUSES = frozenset(_SCHEMA["properties"]["status"]["enum"])
STATE_KEYS = frozenset(_SCHEMA["properties"])
GROUP_PROGRESS_KEYS = frozenset(_SCHEMA["$defs"]["groupProgress"]["properties"])
PENDING_CAPTURE_KEYS = frozenset(_SCHEMA["$defs"]["pendingCapture"]["properties"])
ANCHOR_KEYS = frozenset(_SCHEMA["$defs"]["anchorMessage"]["properties"])
MIN_ANCHOR_COUNT = _SCHEMA["allOf"][0]["then"]["properties"]["groups"][
    "additionalProperties"
]["properties"]["last_completed_anchor"]["minItems"]


class StateError(ValueError):
    """Raised when state is invalid or a transition would lose capture data."""


@dataclass(frozen=True)
class Anchor:
    sequence: int
    content_text: str
    sender_display: str | None = None
    timestamp_text: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "content_text": self.content_text,
            "sender_display": self.sender_display,
            "timestamp_text": self.timestamp_text,
        }


class BatchStateStore:
    """Small JSON state store with explicit incomplete/completed transitions."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict | None:
        if not self.path.exists():
            return None
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StateError("batch state is not valid JSON") from exc
        if isinstance(state, dict) and state.get("schema_version") == "2":
            state = self._upgrade_v2_state(state)
            self._write(state)
        self._validate_state(state)
        return state

    @staticmethod
    def _upgrade_v2_state(state: dict) -> dict:
        upgraded = json.loads(json.dumps(state))
        upgraded["schema_version"] = STATE_SCHEMA_VERSION
        capture_complete = upgraded.get("status") in {"completed", "analyzed"}
        groups = upgraded.get("groups")
        if not isinstance(groups, dict):
            raise StateError("legacy batch state groups are invalid")
        for progress in groups.values():
            if not isinstance(progress, dict):
                raise StateError("legacy group progress is invalid")
            progress["capture_complete"] = capture_complete
        return upgraded

    @staticmethod
    def _valid_datetime(value: object) -> bool:
        if not isinstance(value, str) or "T" not in value:
            return False
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return False
        return parsed.tzinfo is not None

    @classmethod
    def _validate_state(cls, state: object) -> None:
        if not isinstance(state, dict):
            raise StateError("batch state must be an object")
        if set(state) != STATE_KEYS:
            raise StateError("batch state fields do not match the state contract")
        if state["schema_version"] != STATE_SCHEMA_VERSION:
            raise StateError("unsupported batch state schema version")
        if not isinstance(state["batch_id"], str) or not state["batch_id"]:
            raise StateError("batch_id is required")
        if state["status"] not in STATE_STATUSES:
            raise StateError("unsupported batch state status")
        if not cls._valid_datetime(state["started_at"]):
            raise StateError("started_at must be a valid date-time")
        if not cls._valid_datetime(state["updated_at"]):
            raise StateError("updated_at must be a valid date-time")

        pending = state["pending_capture"]
        if pending is not None:
            if not isinstance(pending, dict) or set(pending) != PENDING_CAPTURE_KEYS:
                raise StateError("pending_capture fields do not match the state contract")
            if state["status"] != "incomplete":
                raise StateError("only an incomplete batch may have pending_capture")
            if pending["mode"] not in {"current", "scroll"}:
                raise StateError("pending_capture mode is invalid")
            if not isinstance(pending["group_key"], str) or not pending["group_key"]:
                raise StateError("pending_capture group_key is invalid")
            pending_groups = state["groups"]
            if not isinstance(pending_groups, dict) or pending["group_key"] not in pending_groups:
                raise StateError("pending_capture group is not part of the batch")
            if (
                not isinstance(pending["page_index"], int)
                or isinstance(pending["page_index"], bool)
                or pending["page_index"] < 0
            ):
                raise StateError("pending_capture page_index is invalid")
            if not cls._valid_datetime(pending["started_at"]):
                raise StateError("pending_capture started_at must be a valid date-time")

        next_page_index = state["next_page_index"]
        if (
            not isinstance(next_page_index, int)
            or isinstance(next_page_index, bool)
            or next_page_index < 0
        ):
            raise StateError("next_page_index must be non-negative")
        if pending is not None and pending["page_index"] != next_page_index:
            raise StateError("pending_capture must target next_page_index")

        last_completed_batch = state["last_completed_batch"]
        if last_completed_batch is not None and not isinstance(last_completed_batch, str):
            raise StateError("last_completed_batch must be a string or null")

        last_success_at = state["last_success_at"]
        if last_success_at is not None and not cls._valid_datetime(last_success_at):
            raise StateError("last_success_at must be a valid date-time or null")

        groups = state["groups"]
        if not isinstance(groups, dict) or not groups:
            raise StateError("at least one group is required")

        captured_last_pages: list[int] = []
        for group_key, progress in groups.items():
            if not isinstance(group_key, str) or not group_key:
                raise StateError("group keys must be non-empty strings")
            if not isinstance(progress, dict) or set(progress) != GROUP_PROGRESS_KEYS:
                raise StateError("group progress fields do not match the state contract")

            capture_complete = progress["capture_complete"]
            if not isinstance(capture_complete, bool):
                raise StateError("capture_complete must be boolean")

            last_page = progress["last_page_index"]
            if last_page is not None:
                if (
                    not isinstance(last_page, int)
                    or isinstance(last_page, bool)
                    or last_page < 0
                ):
                    raise StateError("last_page_index must be non-negative or null")
                if last_page >= next_page_index:
                    raise StateError("last_page_index must be before next_page_index")
                captured_last_pages.append(last_page)

            if capture_complete and last_page is None:
                raise StateError("capture_complete group needs at least one captured page")
            if state["status"] in {"completed", "analyzed"} and not capture_complete:
                raise StateError("completed state requires capture_complete for every group")
            if pending is not None and pending["group_key"] == group_key and capture_complete:
                raise StateError("capture_complete group cannot have pending_capture")

            anchors = progress["last_completed_anchor"]
            if not isinstance(anchors, list):
                raise StateError("last_completed_anchor must be an array")
            for anchor in anchors:
                if not isinstance(anchor, dict) or set(anchor) != ANCHOR_KEYS:
                    raise StateError("invalid completed anchor fields")
                sequence = anchor["sequence"]
                if (
                    not isinstance(sequence, int)
                    or isinstance(sequence, bool)
                    or sequence < 0
                    or not isinstance(anchor["content_text"], str)
                    or not anchor["content_text"]
                ):
                    raise StateError("invalid completed anchor")
                for field in ("sender_display", "timestamp_text"):
                    if anchor[field] is not None and not isinstance(anchor[field], str):
                        raise StateError("invalid completed anchor")

            if state["status"] in {"completed", "analyzed"} and len(anchors) < MIN_ANCHOR_COUNT:
                raise StateError("completed state requires continuous anchors")

        if captured_last_pages:
            if max(captured_last_pages) != next_page_index - 1:
                raise StateError("next_page_index must follow the latest captured page")
        elif next_page_index != 0:
            raise StateError("next_page_index must be zero before the first captured page")

    def start_batch(
        self,
        batch_id: str,
        *,
        started_at: str,
        group_keys: list[str],
    ) -> dict:
        if (
            not batch_id
            or not group_keys
            or any(not isinstance(group_key, str) or not group_key for group_key in group_keys)
            or len(set(group_keys)) != len(group_keys)
            or not self._valid_datetime(started_at)
        ):
            raise StateError("valid batch_id, started_at, and unique group_keys are required")

        previous = self.load()
        if previous is not None and previous["status"] == "incomplete":
            if previous["batch_id"] != batch_id:
                raise StateError("cannot replace an incomplete batch")
            if set(previous["groups"]) != set(group_keys):
                raise StateError("cannot resume an incomplete batch with different groups")
            return previous

        previous_groups = previous["groups"] if previous is not None else {}
        state = {
            "schema_version": STATE_SCHEMA_VERSION,
            "batch_id": batch_id,
            "status": "incomplete",
            "started_at": started_at,
            "updated_at": started_at,
            "pending_capture": None,
            "next_page_index": 0,
            "last_completed_batch": previous["last_completed_batch"] if previous is not None else None,
            "last_success_at": previous["last_success_at"] if previous is not None else None,
            "groups": {
                group_key: {
                    "capture_complete": False,
                    "last_page_index": None,
                    "last_completed_anchor": previous_groups.get(group_key, {}).get(
                        "last_completed_anchor", []
                    ),
                }
                for group_key in group_keys
            },
        }
        self._write(state)
        return state

    def begin_capture(
        self,
        batch_id: str,
        group_key: str,
        page_index: int,
        *,
        mode: str,
        started_at: str,
    ) -> dict:
        state = self._require_incomplete(batch_id)
        if state["pending_capture"] is not None:
            raise StateError("cannot start a new capture while pending_capture exists")
        if group_key not in state["groups"]:
            raise StateError("group is not part of the active batch")
        if state["groups"][group_key]["capture_complete"]:
            raise StateError("cannot capture more pages for a capture_complete group")
        if page_index != state["next_page_index"]:
            raise StateError("capture page_index must equal next_page_index")
        if mode not in {"current", "scroll"}:
            raise StateError("capture mode must be current or scroll")
        if not self._valid_datetime(started_at):
            raise StateError("started_at must be a valid date-time")
        if mode == "scroll" and state["groups"][group_key]["last_page_index"] is None:
            raise StateError("scroll capture requires a previous page for the group")

        state["pending_capture"] = {
            "group_key": group_key,
            "page_index": page_index,
            "mode": mode,
            "started_at": started_at,
        }
        state["updated_at"] = started_at
        self._write(state)
        return state

    def record_page(
        self,
        batch_id: str,
        group_key: str,
        page_index: int,
        *,
        updated_at: str,
    ) -> dict:
        state = self._require_incomplete(batch_id)
        if not self._valid_datetime(updated_at):
            raise StateError("updated_at must be a valid date-time")
        group = state["groups"].get(group_key)
        if group is None:
            raise StateError("group is not part of the active batch")
        if (
            not isinstance(page_index, int)
            or isinstance(page_index, bool)
            or page_index != state["next_page_index"]
        ):
            raise StateError("page_index must continue from the recovery point")
        pending = state["pending_capture"]
        if pending is None:
            raise StateError("record_page requires a matching pending_capture")
        if pending["group_key"] != group_key or pending["page_index"] != page_index:
            raise StateError("record_page does not match pending_capture")

        group["last_page_index"] = page_index
        state["pending_capture"] = None
        state["next_page_index"] = page_index + 1
        state["updated_at"] = updated_at
        self._write(state)
        return state

    def record_no_change(
        self,
        batch_id: str,
        group_key: str,
        page_index: int,
        *,
        updated_at: str,
    ) -> dict:
        state = self._require_incomplete(batch_id)
        if not self._valid_datetime(updated_at):
            raise StateError("updated_at must be a valid date-time")
        group = state["groups"].get(group_key)
        if group is None:
            raise StateError("group is not part of the active batch")
        if group["capture_complete"]:
            raise StateError("capture_complete group cannot record no-change")
        pending = state["pending_capture"]
        if pending is None:
            raise StateError("record_no_change requires a pending_capture")
        if (
            pending["group_key"] != group_key
            or pending["page_index"] != page_index
            or pending["mode"] != "scroll"
        ):
            raise StateError("record_no_change requires the matching pending scroll")
        if page_index != state["next_page_index"]:
            raise StateError("no-change page_index must equal next_page_index")

        state["pending_capture"] = None
        state["updated_at"] = updated_at
        self._write(state)
        return state

    def abort_pending_capture(
        self,
        batch_id: str,
        group_key: str,
        page_index: int,
        *,
        updated_at: str,
    ) -> dict:
        state = self._require_incomplete(batch_id)
        if not self._valid_datetime(updated_at):
            raise StateError("updated_at must be a valid date-time")
        pending = state["pending_capture"]
        if pending is None:
            raise StateError("abort_pending_capture requires a pending_capture")
        if pending["group_key"] != group_key or pending["page_index"] != page_index:
            raise StateError("abort_pending_capture does not match pending_capture")
        state["pending_capture"] = None
        state["updated_at"] = updated_at
        self._write(state)
        return state

    def mark_group_capture_complete(
        self,
        batch_id: str,
        group_key: str,
        *,
        completed_at: str,
    ) -> dict:
        state = self._require_incomplete(batch_id)
        if state["pending_capture"] is not None:
            raise StateError("cannot complete group capture while capture is pending")
        if not self._valid_datetime(completed_at):
            raise StateError("completed_at must be a valid date-time")
        group = state["groups"].get(group_key)
        if group is None:
            raise StateError("group is not part of the active batch")
        if group["last_page_index"] is None:
            raise StateError("group capture needs at least one captured page")
        if not group["capture_complete"]:
            group["capture_complete"] = True
            state["updated_at"] = completed_at
            self._write(state)
        return state

    def complete_batch(
        self,
        batch_id: str,
        *,
        anchors: dict[str, list[Anchor]],
        completed_at: str,
    ) -> dict:
        state = self._require_incomplete(batch_id)
        if state["pending_capture"] is not None:
            raise StateError("cannot complete a batch while capture is pending")
        if not self._valid_datetime(completed_at):
            raise StateError("completed_at must be a valid date-time")
        if set(anchors) != set(state["groups"]):
            raise StateError("a completed batch needs an anchor for every group")

        for group_key, group_anchors in anchors.items():
            if not state["groups"][group_key]["capture_complete"]:
                raise StateError("each group capture must be complete before batch completion")
            if state["groups"][group_key]["last_page_index"] is None:
                raise StateError("each group needs at least one captured page")
            if len(group_anchors) < MIN_ANCHOR_COUNT:
                raise StateError("each group needs a continuous anchor sequence")
            if any(not item.content_text for item in group_anchors):
                raise StateError("anchor content_text must be non-empty")
            sequences = [item.sequence for item in group_anchors]
            if any(
                not isinstance(sequence, int)
                or isinstance(sequence, bool)
                or sequence < 0
                for sequence in sequences
            ):
                raise StateError("anchor sequence must be non-negative")
            if sequences != list(range(sequences[0], sequences[0] + len(sequences))):
                raise StateError("anchor sequence must be adjacent and ordered")
            state["groups"][group_key]["last_completed_anchor"] = [
                item.as_dict() for item in group_anchors
            ]

        state["status"] = "completed"
        state["updated_at"] = completed_at
        state["last_completed_batch"] = batch_id
        state["last_success_at"] = completed_at
        self._write(state)
        return state

    def mark_analyzed(self, batch_id: str, *, analyzed_at: str) -> dict:
        state = self.load()
        if state is None or state["batch_id"] != batch_id:
            raise StateError("batch does not exist")
        if state["status"] != "completed":
            raise StateError("only a completed batch can be analyzed")
        if not self._valid_datetime(analyzed_at):
            raise StateError("analyzed_at must be a valid date-time")
        state["status"] = "analyzed"
        state["updated_at"] = analyzed_at
        self._write(state)
        return state

    def can_build_inbox(self, batch_id: str) -> bool:
        state = self.load()
        return bool(
            state is not None
            and state["batch_id"] == batch_id
            and state["status"] in {"completed", "analyzed"}
        )

    def _require_incomplete(self, batch_id: str) -> dict:
        state = self.load()
        if state is None or state["batch_id"] != batch_id:
            raise StateError("batch does not exist")
        if state["status"] != "incomplete":
            raise StateError("batch is no longer incomplete")
        return state

    def _write(self, state: dict) -> None:
        self._validate_state(state)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.tmp-",
            dir=self.path.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
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
