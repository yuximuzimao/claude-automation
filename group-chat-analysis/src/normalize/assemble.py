"""Assemble capture pages into conservative schema-shaped message records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.store import MESSAGE_SCHEMA_VERSION, MESSAGE_SOURCE, validate_message_record

from .overlap import Message, merge_capture_order_pages
from .page_reconstruct import (
    BBox,
    PageFragment,
    PageMessageCandidate,
    PageReconstruction,
    reconstruct_page,
    validate_capture_page,
)


class BatchAssemblyError(ValueError):
    """Raised when capture pages cannot form one safe ordered batch."""


@dataclass(frozen=True)
class AssembledBatch:
    batch_id: str
    group_key: str
    group_display: str | None
    records: tuple[dict[str, object], ...]
    page_reconstructions: tuple[PageReconstruction, ...]
    overlap_count: int


def _fragment_content(fragment: PageFragment) -> str | None:
    lines = [line for line in fragment.text.splitlines() if line.strip()]
    if not lines:
        return None
    if fragment.sender_display is not None or fragment.timestamp_text is not None:
        if len(lines) < 2:
            return None
        return "\n".join(lines[1:]).strip() or None
    return "\n".join(lines).strip() or None


def _fragment_candidate(fragment: PageFragment) -> PageMessageCandidate | None:
    if fragment.kind == "header_only":
        return None
    content = _fragment_content(fragment)
    if not content:
        return None
    return PageMessageCandidate(
        sender_display=fragment.sender_display,
        timestamp_text=fragment.timestamp_text,
        message_type="text",
        content_text=content,
        ocr_confidence=None,
        observed_at=fragment.observed_at,
        page_index=fragment.page_index,
        bbox=fragment.bbox,
    )


def _page_candidates(reconstruction: PageReconstruction) -> list[PageMessageCandidate]:
    candidates = list(reconstruction.messages)
    candidates.extend(
        candidate
        for fragment in reconstruction.fragments
        if (candidate := _fragment_candidate(fragment)) is not None
    )
    # Raw QQ visual y increases upward; lower items are older. Sorting by mid-y
    # therefore produces the chronological old-to-new order required by overlap.
    candidates.sort(key=lambda item: item.bbox.mid_y)
    return candidates


def _message_from_candidate(candidate: PageMessageCandidate) -> Message:
    return Message(
        content_text=candidate.content_text,
        sender_display=candidate.sender_display,
        timestamp_text=candidate.timestamp_text,
        message_type=candidate.message_type,
        ocr_confidence=candidate.ocr_confidence,
    )


def _bbox_dict(bbox: BBox) -> dict[str, float]:
    return {
        "x": bbox.x,
        "y": bbox.y,
        "width": bbox.width,
        "height": bbox.height,
    }


def assemble_capture_pages(pages: Iterable[object]) -> AssembledBatch:
    validated = [validate_capture_page(page) for page in pages]
    if not validated:
        raise BatchAssemblyError("at least one capture page is required")

    validated.sort(key=lambda page: page["page_index"])
    actual_indices = [page["page_index"] for page in validated]
    first_index = actual_indices[0]
    expected_indices = list(range(first_index, first_index + len(validated)))
    if actual_indices != expected_indices:
        raise BatchAssemblyError("capture page_index values for one group must be contiguous")

    batch_ids = {page["batch_id"] for page in validated}
    group_keys = {page["group_key"] for page in validated}
    group_displays = {page["group_display"] for page in validated}
    if len(batch_ids) != 1 or len(group_keys) != 1 or len(group_displays) != 1:
        raise BatchAssemblyError("all capture pages must belong to the same batch/group/display")

    batch_id = next(iter(batch_ids))
    group_key = next(iter(group_keys))
    group_display = next(iter(group_displays))
    if not isinstance(batch_id, str) or not batch_id:
        raise BatchAssemblyError("batch_id is required")
    if not isinstance(group_key, str) or not group_key:
        raise BatchAssemblyError("group_key is required")
    if group_display is not None and not isinstance(group_display, str):
        raise BatchAssemblyError("group_display must be a string or null")

    reconstructions = tuple(reconstruct_page(page) for page in validated)
    message_pages: list[list[Message]] = []
    candidate_by_message_id: dict[int, PageMessageCandidate] = {}
    for reconstruction in reconstructions:
        message_page: list[Message] = []
        for candidate in _page_candidates(reconstruction):
            message = _message_from_candidate(candidate)
            message_page.append(message)
            candidate_by_message_id[id(message)] = candidate
        message_pages.append(message_page)

    merged, overlaps = merge_capture_order_pages(message_pages)
    records: list[dict[str, object]] = []
    for sequence, message in enumerate(merged):
        candidate = candidate_by_message_id[id(message)]
        record: dict[str, object] = {
            "schema_version": MESSAGE_SCHEMA_VERSION,
            "record_id": f"{batch_id}:{group_key}:{sequence}",
            "batch_id": batch_id,
            "group_key": group_key,
            "group_display": group_display,
            "sequence": sequence,
            "sender_display": candidate.sender_display,
            "timestamp": None,
            "timestamp_text": candidate.timestamp_text,
            "message_type": candidate.message_type,
            "content_text": candidate.content_text,
            "ocr_confidence": candidate.ocr_confidence,
            "observed_at": candidate.observed_at,
            "source": MESSAGE_SOURCE,
            "capture_refs": [
                {
                    "page_index": candidate.page_index,
                    "bbox": _bbox_dict(candidate.bbox),
                }
            ],
        }
        validate_message_record(record)
        records.append(record)

    return AssembledBatch(
        batch_id=batch_id,
        group_key=group_key,
        group_display=group_display,
        records=tuple(records),
        page_reconstructions=reconstructions,
        overlap_count=sum(match.count for match in overlaps if match is not None),
    )
