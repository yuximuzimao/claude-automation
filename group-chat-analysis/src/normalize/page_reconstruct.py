"""Reconstruct conservative message candidates from one capture-page record."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from statistics import median
from typing import Iterable


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "capture-page.schema.json"
_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
CAPTURE_REQUIRED = frozenset(_SCHEMA["required"])
CAPTURE_SCHEMA_VERSION = _SCHEMA["properties"]["schema_version"]["const"]
CAPTURE_SOURCE = _SCHEMA["properties"]["source"]["const"]
CAPTURE_FINGERPRINT_RE = re.compile(r"^dhash512:[0-9a-f]{128}$")

DATE_RE = re.compile(r"^\s*(\d{4})[/-](\d{1,2})[/-](\d{1,2})\s*$")
HEADER_RE = re.compile(r"^\s*(.*?)\s*[•.]?\s*(\d{1,2}:\d{2})\s*$")


class PageReconstructionError(ValueError):
    """Raised when raw capture input is invalid or cannot be reconstructed safely."""


@dataclass(frozen=True)
class BBox:
    x: float
    y: float
    width: float
    height: float

    @property
    def max_x(self) -> float:
        return self.x + self.width

    @property
    def max_y(self) -> float:
        return self.y + self.height

    @property
    def mid_x(self) -> float:
        return self.x + self.width / 2

    @property
    def mid_y(self) -> float:
        return self.y + self.height / 2

    @staticmethod
    def union(items: Iterable["BBox"]) -> "BBox":
        items = list(items)
        if not items:
            raise PageReconstructionError("cannot union an empty bbox list")
        min_x = min(item.x for item in items)
        min_y = min(item.y for item in items)
        max_x = max(item.max_x for item in items)
        max_y = max(item.max_y for item in items)
        return BBox(min_x, min_y, max_x - min_x, max_y - min_y)


@dataclass(frozen=True)
class OCRBlock:
    block_index: int
    text: str
    bbox: BBox
    confidence: float


@dataclass(frozen=True)
class VisualLine:
    text: str
    bbox: BBox
    confidence: float
    block_indices: tuple[int, ...]


@dataclass(frozen=True)
class PageMessageCandidate:
    sender_display: str | None
    timestamp_text: str | None
    message_type: str
    content_text: str
    ocr_confidence: float | None
    observed_at: str
    page_index: int
    bbox: BBox


@dataclass(frozen=True)
class PageFragment:
    kind: str
    text: str
    observed_at: str
    page_index: int
    bbox: BBox
    sender_display: str | None = None
    timestamp_text: str | None = None


@dataclass(frozen=True)
class PageReconstruction:
    messages: tuple[PageMessageCandidate, ...]
    fragments: tuple[PageFragment, ...]
    body_height: float


def _bbox_from_dict(value: object) -> BBox:
    if not isinstance(value, dict) or set(value) != {"x", "y", "width", "height"}:
        raise PageReconstructionError("invalid bbox")
    try:
        bbox = BBox(*(float(value[field]) for field in ("x", "y", "width", "height")))
    except (TypeError, ValueError) as exc:
        raise PageReconstructionError("bbox values must be numeric") from exc
    if bbox.width < 0 or bbox.height < 0:
        raise PageReconstructionError("bbox dimensions must be non-negative")
    return bbox


def validate_capture_page(page: object) -> dict:
    if not isinstance(page, dict):
        raise PageReconstructionError("capture page must be an object")
    if not CAPTURE_REQUIRED.issubset(page):
        raise PageReconstructionError("capture page is missing required fields")
    if set(page) - set(_SCHEMA["properties"]):
        raise PageReconstructionError("capture page has unknown fields")
    if page["schema_version"] != CAPTURE_SCHEMA_VERSION:
        raise PageReconstructionError("unsupported capture schema version")
    fingerprint = page["visual_fingerprint"]
    if not isinstance(fingerprint, str) or CAPTURE_FINGERPRINT_RE.fullmatch(fingerprint) is None:
        raise PageReconstructionError("visual_fingerprint is invalid")
    if page["source"] != CAPTURE_SOURCE:
        raise PageReconstructionError("unsupported capture source")
    if not isinstance(page["page_index"], int) or isinstance(page["page_index"], bool) or page["page_index"] < 0:
        raise PageReconstructionError("page_index must be a non-negative integer")
    if not isinstance(page["captured_at"], str) or not page["captured_at"]:
        raise PageReconstructionError("captured_at is required")
    if not isinstance(page["blocks"], list):
        raise PageReconstructionError("blocks must be an array")
    _bbox_from_dict(page["content_region"])
    return page


def _parse_blocks(page: dict) -> list[OCRBlock]:
    result: list[OCRBlock] = []
    for raw in page["blocks"]:
        if not isinstance(raw, dict):
            raise PageReconstructionError("OCR block must be an object")
        text = raw.get("text")
        index = raw.get("block_index")
        confidence = raw.get("confidence")
        if not isinstance(text, str) or not text.strip():
            raise PageReconstructionError("OCR block text must be non-empty")
        if not isinstance(index, int) or isinstance(index, bool) or index < 0:
            raise PageReconstructionError("OCR block index must be non-negative")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
            raise PageReconstructionError("OCR confidence must be between 0 and 1")
        result.append(OCRBlock(index, text, _bbox_from_dict(raw.get("bbox")), float(confidence)))
    return result


def _inside_region(block: OCRBlock, region: BBox) -> bool:
    return (
        region.x <= block.bbox.mid_x <= region.max_x
        and region.y <= block.bbox.mid_y <= region.max_y
    )


def _same_visual_line(left: OCRBlock, right: OCRBlock) -> bool:
    overlap = min(left.bbox.max_y, right.bbox.max_y) - max(left.bbox.y, right.bbox.y)
    min_height = min(left.bbox.height, right.bbox.height)
    if min_height > 0 and overlap / min_height >= 0.45:
        return True
    return abs(left.bbox.mid_y - right.bbox.mid_y) <= 0.25 * max(
        left.bbox.height,
        right.bbox.height,
    )


def _separator(left: str, right: str, gap: float, height: float) -> str:
    if not left or not right:
        return ""
    if gap <= max(0.002, height * 0.20):
        return ""
    if left[-1:].isascii() and left[-1:].isalnum() and right[:1].isascii() and right[:1].isalnum():
        return " "
    return ""


def build_visual_lines(blocks: list[OCRBlock], region: BBox) -> list[VisualLine]:
    candidates = [block for block in blocks if _inside_region(block, region)]
    candidates.sort(key=lambda item: (-item.bbox.mid_y, item.bbox.x))
    groups: list[list[OCRBlock]] = []
    for block in candidates:
        if groups and any(_same_visual_line(existing, block) for existing in groups[-1]):
            groups[-1].append(block)
        else:
            groups.append([block])

    lines: list[VisualLine] = []
    for group in groups:
        group.sort(key=lambda item: item.bbox.x)
        pieces: list[str] = []
        previous: OCRBlock | None = None
        for item in group:
            if previous is not None:
                gap = item.bbox.x - previous.bbox.max_x
                pieces.append(_separator(previous.text, item.text, gap, max(previous.bbox.height, item.bbox.height)))
            pieces.append(item.text.strip())
            previous = item
        lines.append(
            VisualLine(
                text="".join(pieces).strip(),
                bbox=BBox.union(item.bbox for item in group),
                confidence=sum(item.confidence for item in group) / len(group),
                block_indices=tuple(item.block_index for item in group),
            )
        )
    return lines


def _header_parts(text: str) -> tuple[str | None, str] | None:
    match = HEADER_RE.match(text)
    if not match:
        return None
    sender = match.group(1).strip(" .•") or None
    return sender, match.group(2)


def _estimate_body_height(lines: list[VisualLine]) -> float:
    samples: list[float] = []
    for index, line in enumerate(lines[:-1]):
        if _header_parts(line.text) is None:
            continue
        next_line = lines[index + 1]
        if _header_parts(next_line.text) is not None or DATE_RE.match(next_line.text):
            continue
        gap = max(0.0, line.bbox.y - next_line.bbox.max_y)
        if gap <= 2.0 * max(line.bbox.height, next_line.bbox.height):
            samples.append(next_line.bbox.height)
    if samples:
        return median(samples)

    fallback = [
        line.bbox.height
        for line in lines
        if _header_parts(line.text) is None and DATE_RE.match(line.text) is None
    ]
    if not fallback:
        raise PageReconstructionError("cannot estimate body text height")
    return median(fallback)


def _is_header(line: VisualLine, body_height: float) -> tuple[str | None, str] | None:
    parts = _header_parts(line.text)
    if parts is None:
        return None
    if line.bbox.height > body_height * 0.95:
        return None
    return parts


def _is_system_line(line: VisualLine, region: BBox) -> bool:
    relative_x = (line.bbox.mid_x - region.x) / region.width if region.width else 0
    relative_width = line.bbox.width / region.width if region.width else 1
    return 0.42 <= relative_x <= 0.62 and relative_width <= 0.18


def _looks_like_ocr_inside_media(body: list[VisualLine], body_height: float) -> bool:
    """Conservatively detect dense small OCR likely coming from an embedded image.

    Real QQ evidence showed screenshot OCR as many tightly packed lines whose
    heights are consistently well below the page's normal chat-body height.
    This is intentionally a narrow heuristic: a few quote/reply lines are not
    enough to suppress an otherwise normal text message.
    """

    if len(body) < 3 or body_height <= 0:
        return False
    small = sum(line.bbox.height <= body_height * 0.85 for line in body)
    return small / len(body) >= 0.80


def _message_from_lines(
    header: VisualLine,
    body: list[VisualLine],
    sender: str | None,
    time_text: str,
    observed_at: str,
    page_index: int,
    body_height: float,
) -> PageMessageCandidate:
    all_lines = [header, *body]
    confidence = sum(line.confidence for line in all_lines) / len(all_lines)
    media_like = _looks_like_ocr_inside_media(body, body_height)
    return PageMessageCandidate(
        sender_display=sender,
        timestamp_text=time_text,
        message_type="unknown" if media_like else "text",
        content_text=(
            "非文字内容（图片/表情等，未解析）"
            if media_like
            else "\n".join(line.text for line in body)
        ),
        ocr_confidence=confidence,
        observed_at=observed_at,
        page_index=page_index,
        bbox=BBox.union(line.bbox for line in all_lines),
    )


def reconstruct_page(page: object) -> PageReconstruction:
    page = validate_capture_page(page)
    region = _bbox_from_dict(page["content_region"])
    lines = build_visual_lines(_parse_blocks(page), region)
    if not lines:
        raise PageReconstructionError("capture page has no OCR lines inside content region")

    body_height = _estimate_body_height(lines)
    header_gap_limit = body_height * 1.5
    bottom_edge_limit = body_height * 1.5
    observed_at = page["captured_at"]
    page_index = page["page_index"]

    messages: list[PageMessageCandidate] = []
    fragments: list[PageFragment] = []
    leading_orphan: list[VisualLine] = []
    middle_orphan: list[VisualLine] = []
    current_header: VisualLine | None = None
    current_sender: str | None = None
    current_time: str | None = None
    current_body: list[VisualLine] = []
    seen_valid_header = False

    def add_fragment(kind: str, items: list[VisualLine], sender: str | None = None, time_text: str | None = None) -> None:
        if not items:
            return
        fragments.append(
            PageFragment(
                kind=kind,
                text="\n".join(item.text for item in items),
                observed_at=observed_at,
                page_index=page_index,
                bbox=BBox.union(item.bbox for item in items),
                sender_display=sender,
                timestamp_text=time_text,
            )
        )

    def finish_current(*, at_page_end: bool = False) -> None:
        nonlocal current_header, current_sender, current_time, current_body
        if current_header is None:
            return
        if not current_body:
            add_fragment("header_only", [current_header], current_sender, current_time)
        else:
            near_bottom = min(line.bbox.y for line in current_body) - region.y <= bottom_edge_limit
            if at_page_end and near_bottom:
                add_fragment(
                    "bottom",
                    [current_header, *current_body],
                    current_sender,
                    current_time,
                )
            else:
                messages.append(
                    _message_from_lines(
                        current_header,
                        current_body,
                        current_sender,
                        current_time or "",
                        observed_at,
                        page_index,
                        body_height,
                    )
                )
        current_header = None
        current_sender = None
        current_time = None
        current_body = []

    for line in lines:
        if DATE_RE.match(line.text):
            finish_current()
            if not seen_valid_header:
                add_fragment("top", leading_orphan)
                leading_orphan = []
            if middle_orphan:
                add_fragment("orphan", middle_orphan)
                middle_orphan = []
            continue

        header = _is_header(line, body_height)
        if header is not None:
            if not seen_valid_header:
                add_fragment("top", leading_orphan)
                leading_orphan = []
                seen_valid_header = True
            if middle_orphan:
                add_fragment("orphan", middle_orphan)
                middle_orphan = []
            finish_current()
            current_header = line
            current_sender, current_time = header
            continue

        if _is_system_line(line, region):
            finish_current()
            if not seen_valid_header:
                leading_orphan.append(line)
                continue
            if middle_orphan:
                add_fragment("orphan", middle_orphan)
                middle_orphan = []
            messages.append(
                PageMessageCandidate(
                    sender_display=None,
                    timestamp_text=None,
                    message_type="system",
                    content_text=line.text,
                    ocr_confidence=line.confidence,
                    observed_at=observed_at,
                    page_index=page_index,
                    bbox=line.bbox,
                )
            )
            continue

        if current_header is None:
            if seen_valid_header:
                middle_orphan.append(line)
            else:
                leading_orphan.append(line)
            continue

        previous = current_body[-1] if current_body else current_header
        gap = max(0.0, previous.bbox.y - line.bbox.max_y)
        if current_body and gap > header_gap_limit:
            finish_current()
            middle_orphan.append(line)
            continue
        current_body.append(line)

    finish_current(at_page_end=True)
    if not seen_valid_header:
        add_fragment("top", leading_orphan)
    elif leading_orphan:
        add_fragment("top", leading_orphan)
    if middle_orphan:
        add_fragment("orphan", middle_orphan)

    # QQ's current history window is visually newest-at-top.  The rest of the
    # pipeline uses chronological old-to-new order, so reverse only complete
    # messages here after all visual/edge decisions have been made.
    return PageReconstruction(
        messages=tuple(reversed(messages)),
        fragments=tuple(fragments),
        body_height=body_height,
    )
