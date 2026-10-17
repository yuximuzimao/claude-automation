"""Single source manifest for every formal Swift capture target."""

from __future__ import annotations


CAPTURE_LIBRARY_SOURCES: tuple[str, ...] = (
    "src/capture/CaptureModels.swift",
    "src/capture/VisionTextRecognizer.swift",
    "src/capture/VisualFingerprint.swift",
    "src/capture/ContentRegion.swift",
    "src/capture/WindowPreparation.swift",
    "src/capture/ChangeDetector.swift",
    "src/capture/QQHistoryCapture.swift",
    "src/capture/RawPageWriter.swift",
)

CONVERSATION_LIBRARY_SOURCES: tuple[str, ...] = (
    "src/capture/CaptureModels.swift",
    "src/capture/VisionTextRecognizer.swift",
    "src/capture/ConversationSwitcher.swift",
)

HISTORY_DATE_LIBRARY_SOURCES: tuple[str, ...] = (
    "src/capture/CaptureModels.swift",
    "src/capture/VisionTextRecognizer.swift",
    "src/capture/ConversationSwitcher.swift",
    "src/capture/WindowPreparation.swift",
    "src/capture/HistoryDateSelector.swift",
)

CAPTURE_PURE_LIBRARY_SOURCES: tuple[str, ...] = (
    *CAPTURE_LIBRARY_SOURCES,
    "src/capture/ConversationSwitcher.swift",
)

CAPTURE_STEP_SOURCES: tuple[str, ...] = (
    *CAPTURE_LIBRARY_SOURCES,
    "src/app/capture-step.swift",
)

OPEN_HISTORY_SOURCES: tuple[str, ...] = (
    *CONVERSATION_LIBRARY_SOURCES,
    "src/app/open-history.swift",
)

SELECT_HISTORY_DATE_SOURCES: tuple[str, ...] = (
    *HISTORY_DATE_LIBRARY_SOURCES,
    "src/app/select-history-date.swift",
)
