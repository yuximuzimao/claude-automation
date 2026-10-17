import AppKit
import CoreGraphics
import Foundation
import ScreenCaptureKit

private let qqCaptureBundleID = "com.tencent.qq"

enum QQHistoryCaptureError: Error, CustomStringConvertible {
    case qqNotRunning
    case qqNotForeground
    case historyWindowNotFound(String)
    case ambiguousHistoryWindows(String)
    case historyWindowChanged
    case viewportMismatch(Int)
    case captureFailed
    case noOCRResults
    case safeScrollAnchorNotFound
    case invalidScrollPixels

    var description: String {
        switch self {
        case .qqNotRunning:
            return "QQ is not running."
        case .qqNotForeground:
            return "QQ is no longer frontmost; capture stopped."
        case let .historyWindowNotFound(title):
            return "No visible QQ history window exactly matched title: \(title)"
        case let .ambiguousHistoryWindows(title):
            return "More than one visible QQ window exactly matched title: \(title)"
        case .historyWindowChanged:
            return "QQ history window changed during capture."
        case let .viewportMismatch(distance):
            return "Current QQ viewport no longer matches the last durable raw page (dHash distance=\(distance)); refusing to scroll."
        case .captureFailed:
            return "Failed to capture the QQ history window."
        case .noOCRResults:
            return "Apple Vision returned no OCR blocks."
        case .safeScrollAnchorNotFound:
            return "No safe OCR block inside the content region was available for scrolling."
        case .invalidScrollPixels:
            return "scroll_pixels must be positive."
        }
    }
}

struct CapturedPage {
    let record: RawCapturePage
    let windowID: CGWindowID
}

enum ScrollAdvanceResult {
    case changedAndStable(baselineMAD: Double, adjacentMAD: Double)
    case noChange(maxBaselineMAD: Double)
    case uncertain(lastBaselineMAD: Double, lastAdjacentMAD: Double?)
}

enum HistoryScrollDirection {
    case towardHistory
    case towardNewer
}

struct QQHistoryCapture {
    @MainActor
    static func capturePage(
        groupKey: String,
        expectedTitle: String,
        batchID: String,
        pageIndex: Int
    ) async throws -> CapturedPage {
        let target = try await validatedHistoryWindow(expectedTitle: expectedTitle)
        let image = try await captureImage(target)
        return try await makeCapturedPageWithToolbarRetry(
            initialImage: image,
            initialTarget: target,
            groupKey: groupKey,
            expectedTitle: expectedTitle,
            batchID: batchID,
            pageIndex: pageIndex
        )
    }

    @MainActor
    static func capturePageAfterStableScroll(
        groupKey: String,
        expectedTitle: String,
        batchID: String,
        pageIndex: Int,
        previousPage: CapturedPage,
        scrollPixels: Int,
        direction: HistoryScrollDirection = .towardHistory
    ) async throws -> (CapturedPage?, ScrollAdvanceResult) {
        guard scrollPixels > 0 else {
            throw QQHistoryCaptureError.invalidScrollPixels
        }

        let maxFocusRecoveries = 1
        var focusRecoveries = 0

        while true {
            let target: SCWindow
            do {
                target = try await validatedHistoryWindow(expectedTitle: expectedTitle)
            } catch QQHistoryCaptureError.qqNotForeground {
                guard focusRecoveries < maxFocusRecoveries else {
                    throw QQHistoryCaptureError.qqNotForeground
                }
                try await QQWindowPreparer.focusHistoryWindow(expectedTitle: expectedTitle)
                focusRecoveries += 1
                print("FOCUS_RECOVERED stage=before-viewport-check")
                continue
            }

            guard target.windowID == previousPage.windowID else {
                throw QQHistoryCaptureError.historyWindowChanged
            }
            let currentImage = try await captureImage(target)
            let currentFingerprint = try VisualFingerprint.make(currentImage)
            let fingerprintDistance = try VisualFingerprint.distance(
                currentFingerprint,
                previousPage.record.visualFingerprint
            )
            guard fingerprintDistance <= VisualFingerprint.sameViewportMaximumDistance else {
                throw QQHistoryCaptureError.viewportMismatch(fingerprintDistance)
            }

            let anchor = try safeScrollPoint(
                target: target,
                blocks: previousPage.record.blocks,
                region: previousPage.record.contentRegion
            )
            postMouseMove(anchor)
            try await Task.sleep(nanoseconds: 300_000_000)

            if !QQWindowPreparer.isQQForeground() {
                guard focusRecoveries < maxFocusRecoveries else {
                    throw QQHistoryCaptureError.qqNotForeground
                }
                try await QQWindowPreparer.focusHistoryWindow(expectedTitle: expectedTitle)
                focusRecoveries += 1
                print("FOCUS_RECOVERED stage=before-scroll")
                continue
            }

            let baseline = try await captureImage(target)
            // captureImage is async, so perform one final synchronous foreground
            // check immediately before posting the wheel event.  This closes the
            // focus-steal window between viewport validation and the actual scroll.
            if !QQWindowPreparer.isQQForeground() {
                guard focusRecoveries < maxFocusRecoveries else {
                    throw QQHistoryCaptureError.qqNotForeground
                }
                try await QQWindowPreparer.focusHistoryWindow(expectedTitle: expectedTitle)
                focusRecoveries += 1
                print("FOCUS_RECOVERED stage=immediately-before-scroll")
                continue
            }

            let delta = min(scrollPixels, max(1, Int(target.frame.height * 0.75)))
            postScroll(pixels: delta, direction: direction)

            let stability = try await ScrollChangeDetector.waitForStableChange(
                baseline: baseline,
                region: previousPage.record.contentRegion
            ) {
                let current = try await validatedHistoryWindow(expectedTitle: expectedTitle)
                guard current.windowID == target.windowID else {
                    throw QQHistoryCaptureError.historyWindowChanged
                }
                return try await captureImage(current)
            }

            switch stability {
            case let .changedAndStable(image, baselineMAD, adjacentMAD):
                let current = try await validatedHistoryWindow(expectedTitle: expectedTitle)
                guard current.windowID == target.windowID else {
                    throw QQHistoryCaptureError.historyWindowChanged
                }
                let page = try await makeCapturedPageWithToolbarRetry(
                    initialImage: image,
                    initialTarget: current,
                    groupKey: groupKey,
                    expectedTitle: expectedTitle,
                    batchID: batchID,
                    pageIndex: pageIndex
                )
                return (
                    page,
                    .changedAndStable(
                        baselineMAD: baselineMAD,
                        adjacentMAD: adjacentMAD
                    )
                )
            case let .noChange(maxBaselineMAD):
                // A verified unchanged viewport is safe to retry if focus was
                // stolen: no durable position changed, and this must not count as
                // history-boundary evidence.
                if !QQWindowPreparer.isQQForeground() {
                    guard focusRecoveries < maxFocusRecoveries else {
                        throw QQHistoryCaptureError.qqNotForeground
                    }
                    try await QQWindowPreparer.focusHistoryWindow(expectedTitle: expectedTitle)
                    focusRecoveries += 1
                    print("FOCUS_RECOVERED stage=after-no-change")
                    continue
                }
                return (nil, .noChange(maxBaselineMAD: maxBaselineMAD))
            case let .uncertain(image, lastBaselineMAD, lastAdjacentMAD):
                if lastBaselineMAD > ScrollChangeDetector.dynamicNoiseThreshold,
                   lastBaselineMAD < ScrollChangeDetector.changedThreshold,
                   let lastAdjacentMAD,
                   lastAdjacentMAD <= ScrollChangeDetector.quietThreshold {
                    let current = try await validatedHistoryWindow(expectedTitle: expectedTitle)
                    guard current.windowID == target.windowID else {
                        throw QQHistoryCaptureError.historyWindowChanged
                    }
                    let candidate = try await makeCapturedPageWithToolbarRetry(
                        initialImage: image,
                        initialTarget: current,
                        groupKey: groupKey,
                        expectedTitle: expectedTitle,
                        batchID: batchID,
                        pageIndex: pageIndex
                    )
                    if isClearlyDifferentByOCR(
                        previous: previousPage.record,
                        current: candidate.record
                    ) {
                        return (
                            candidate,
                            .changedAndStable(
                                baselineMAD: lastBaselineMAD,
                                adjacentMAD: lastAdjacentMAD
                            )
                        )
                    }
                }
                return (
                    nil,
                    .uncertain(
                        lastBaselineMAD: lastBaselineMAD,
                        lastAdjacentMAD: lastAdjacentMAD
                    )
                )
            }
        }
    }

    static func isClearlyDifferentByOCR(
        previous: RawCapturePage,
        current: RawCapturePage
    ) -> Bool {
        let previousTexts = normalizedContentTexts(previous)
        let currentTexts = normalizedContentTexts(current)
        guard previousTexts.count >= 8, currentTexts.count >= 8 else {
            return false
        }
        let union = previousTexts.union(currentTexts)
        guard !union.isEmpty else {
            return false
        }
        let common = previousTexts.intersection(currentTexts)
        let jaccard = Double(common.count) / Double(union.count)
        // Low-motion scrolls can advance only part of a viewport.  Preserving
        // that high-overlap page is safer than issuing another scroll and
        // risking skipped messages; adjacent-page dedup can remove duplicates.
        return jaccard <= 0.85
    }

    private static func normalizedContentTexts(_ page: RawCapturePage) -> Set<String> {
        var result = Set<String>()
        for block in page.blocks {
            let midX = block.bbox.x + block.bbox.width / 2.0
            let midY = block.bbox.y + block.bbox.height / 2.0
            guard page.contentRegion.contains(midX: midX, midY: midY) else {
                continue
            }
            let normalized = block.text.replacingOccurrences(
                of: "\\s+",
                with: "",
                options: .regularExpression
            )
            guard normalized.count >= 2 else {
                continue
            }
            result.insert(normalized)
        }
        return result
    }

    @MainActor
    static func validatedHistoryWindow(expectedTitle: String) async throws -> SCWindow {
        guard NSRunningApplication.runningApplications(
            withBundleIdentifier: qqCaptureBundleID
        ).first != nil else {
            throw QQHistoryCaptureError.qqNotRunning
        }
        guard NSWorkspace.shared.frontmostApplication?.bundleIdentifier == qqCaptureBundleID else {
            throw QQHistoryCaptureError.qqNotForeground
        }

        let content = try await SCShareableContent.excludingDesktopWindows(
            false,
            onScreenWindowsOnly: true
        )
        let matches = content.windows.filter { window in
            window.owningApplication?.bundleIdentifier == qqCaptureBundleID &&
                window.isOnScreen &&
                window.title == expectedTitle &&
                window.frame.width > 100 &&
                window.frame.height > 100
        }

        guard !matches.isEmpty else {
            throw QQHistoryCaptureError.historyWindowNotFound(expectedTitle)
        }
        guard matches.count == 1, let target = matches.first else {
            throw QQHistoryCaptureError.ambiguousHistoryWindows(expectedTitle)
        }
        return target
    }

    @MainActor
    static func captureImage(_ window: SCWindow) async throws -> CGImage {
        let filter = SCContentFilter(desktopIndependentWindow: window)
        let config = SCStreamConfiguration()
        config.width = max(1, Int(window.frame.width.rounded()))
        config.height = max(1, Int(window.frame.height.rounded()))
        config.showsCursor = false
        config.capturesAudio = false

        do {
            return try await SCScreenshotManager.captureImage(
                contentFilter: filter,
                configuration: config
            )
        } catch {
            throw QQHistoryCaptureError.captureFailed
        }
    }

    @MainActor
    private static func makeCapturedPageWithToolbarRetry(
        initialImage: CGImage,
        initialTarget: SCWindow,
        groupKey: String,
        expectedTitle: String,
        batchID: String,
        pageIndex: Int
    ) async throws -> CapturedPage {
        var image = initialImage
        var target = initialTarget
        let maximumAttempts = 3

        for attempt in 0..<maximumAttempts {
            do {
                return try makeCapturedPage(
                    image: image,
                    capturedAt: ISO8601DateFormatter().string(from: Date()),
                    target: target,
                    groupKey: groupKey,
                    expectedTitle: expectedTitle,
                    batchID: batchID,
                    pageIndex: pageIndex
                )
            } catch ContentRegionError.toolbarNotFound {
                guard attempt + 1 < maximumAttempts else {
                    throw ContentRegionError.toolbarNotFound
                }
                try await Task.sleep(nanoseconds: 180_000_000)
                let refreshed = try await validatedHistoryWindow(expectedTitle: expectedTitle)
                guard refreshed.windowID == initialTarget.windowID else {
                    throw QQHistoryCaptureError.historyWindowChanged
                }
                target = refreshed
                image = try await captureImage(refreshed)
            }
        }

        throw ContentRegionError.toolbarNotFound
    }

    private static func makeCapturedPage(
        image: CGImage,
        capturedAt: String,
        target: SCWindow,
        groupKey: String,
        expectedTitle: String,
        batchID: String,
        pageIndex: Int
    ) throws -> CapturedPage {
        let uprightBlocks = try VisionTextRecognizer.recognizeBlocks(
            image,
            orientation: .up,
            usesLanguageCorrection: true
        )

        var blocks = uprightBlocks
        let region: CaptureBBox
        if uprightBlocks.isEmpty {
            let rotatedBlocks = try VisionTextRecognizer.recognizeBlocks(
                image,
                orientation: .down,
                usesLanguageCorrection: true
            )
            guard !rotatedBlocks.isEmpty else {
                throw QQHistoryCaptureError.noOCRResults
            }
            blocks = rotatedBlocks
            region = try ContentRegionLocator.locate(from: rotatedBlocks)
        } else {
            do {
                region = try ContentRegionLocator.locate(from: uprightBlocks)
            } catch ContentRegionError.toolbarNotFound {
                let rotatedBlocks = try VisionTextRecognizer.recognizeBlocks(
                    image,
                    orientation: .down,
                    usesLanguageCorrection: true
                )
                guard !rotatedBlocks.isEmpty else {
                    throw QQHistoryCaptureError.noOCRResults
                }
                blocks = rotatedBlocks
                region = try ContentRegionLocator.locate(from: rotatedBlocks)
            }
        }

        let fingerprint = try VisualFingerprint.make(image)
        let title = target.title ?? expectedTitle
        let page = RawCapturePage(
            schemaVersion: "2",
            visualFingerprint: fingerprint,
            batchID: batchID,
            groupKey: groupKey,
            groupDisplay: title,
            pageIndex: pageIndex,
            capturedAt: capturedAt,
            source: "qq_history_window_ocr",
            window: CaptureWindowInfo(
                title: title,
                framePoints: CaptureScreenFrame(
                    x: target.frame.origin.x,
                    y: target.frame.origin.y,
                    width: target.frame.width,
                    height: target.frame.height
                ),
                captureSizePixels: CapturePixelSize(
                    width: image.width,
                    height: image.height
                )
            ),
            contentRegion: region,
            blocks: blocks
        )
        return CapturedPage(record: page, windowID: target.windowID)
    }

    private static func safeScrollPoint(
        target: SCWindow,
        blocks: [CaptureOCRBlock],
        region: CaptureBBox
    ) throws -> CGPoint {
        let candidates = blocks.filter { block in
            let midX = block.bbox.x + block.bbox.width / 2.0
            let midY = block.bbox.y + block.bbox.height / 2.0
            return block.confidence >= 0.5 &&
                region.contains(midX: midX, midY: midY) &&
                !ContentRegionLocator.isToolbarText(block.text) &&
                !ContentRegionLocator.isTimeOnly(block.text) &&
                !ContentRegionLocator.isDateSeparator(block.text)
        }
        guard let anchor = candidates.min(by: { left, right in
            let leftX = left.bbox.x + left.bbox.width / 2.0
            let leftY = left.bbox.y + left.bbox.height / 2.0
            let rightX = right.bbox.x + right.bbox.width / 2.0
            let rightY = right.bbox.y + right.bbox.height / 2.0
            let centerX = region.x + region.width / 2.0
            let centerY = region.y + region.height / 2.0
            let leftDistance = pow(leftX - centerX, 2) + pow(leftY - centerY, 2)
            let rightDistance = pow(rightX - centerX, 2) + pow(rightY - centerY, 2)
            return leftDistance < rightDistance
        }) else {
            throw QQHistoryCaptureError.safeScrollAnchorNotFound
        }

        let localX = CGFloat(anchor.bbox.x + anchor.bbox.width / 2.0) * target.frame.width
        let localY = (1.0 - CGFloat(anchor.bbox.y + anchor.bbox.height / 2.0)) * target.frame.height
        return CGPoint(
            x: target.frame.minX + localX,
            y: target.frame.minY + localY
        )
    }

    private static func postMouseMove(_ point: CGPoint) {
        CGEvent(
            mouseEventSource: CGEventSource(stateID: .hidSystemState),
            mouseType: .mouseMoved,
            mouseCursorPosition: point,
            mouseButton: .left
        )?.post(tap: .cghidEventTap)
    }

    private static func postScroll(pixels: Int, direction: HistoryScrollDirection) {
        let signedPixels: Int32 = direction == .towardHistory
            ? -Int32(pixels)
            : Int32(pixels)
        CGEvent(
            scrollWheelEvent2Source: CGEventSource(stateID: .hidSystemState),
            units: .pixel,
            wheelCount: 1,
            wheel1: signedPixels,
            wheel2: 0,
            wheel3: 0
        )?.post(tap: .cghidEventTap)
    }
}
