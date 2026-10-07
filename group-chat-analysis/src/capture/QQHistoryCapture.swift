import AppKit
import CoreGraphics
import Foundation
import ScreenCaptureKit
import Vision

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
        let capturedAt = ISO8601DateFormatter().string(from: Date())
        return try makeCapturedPage(
            image: image,
            capturedAt: capturedAt,
            target: target,
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
        scrollPixels: Int
    ) async throws -> (CapturedPage?, ScrollAdvanceResult) {
        guard scrollPixels > 0 else {
            throw QQHistoryCaptureError.invalidScrollPixels
        }
        let target = try await validatedHistoryWindow(expectedTitle: expectedTitle)
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

        let baseline = try await captureImage(target)
        let delta = min(scrollPixels, max(1, Int(target.frame.height * 0.75)))
        postScrollTowardHistory(pixels: delta)

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
            let page = try makeCapturedPage(
                image: image,
                capturedAt: ISO8601DateFormatter().string(from: Date()),
                target: current,
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
            return (nil, .noChange(maxBaselineMAD: maxBaselineMAD))
        case let .uncertain(lastBaselineMAD, lastAdjacentMAD):
            return (
                nil,
                .uncertain(
                    lastBaselineMAD: lastBaselineMAD,
                    lastAdjacentMAD: lastAdjacentMAD
                )
            )
        }
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

    private static func makeCapturedPage(
        image: CGImage,
        capturedAt: String,
        target: SCWindow,
        groupKey: String,
        expectedTitle: String,
        batchID: String,
        pageIndex: Int
    ) throws -> CapturedPage {
        let blocks = try recognizeText(image)
        guard !blocks.isEmpty else {
            throw QQHistoryCaptureError.noOCRResults
        }
        let region = try ContentRegionLocator.locate(from: blocks)
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

    private static func recognizeText(_ image: CGImage) throws -> [CaptureOCRBlock] {
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.recognitionLanguages = ["zh-Hans", "en-US"]
        request.usesLanguageCorrection = true

        let handler = VNImageRequestHandler(cgImage: image, options: [:])
        try handler.perform([request])

        return (request.results ?? []).enumerated().compactMap { index, observation in
            guard let candidate = observation.topCandidates(1).first else {
                return nil
            }
            let text = candidate.string
            guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
                return nil
            }
            let box = observation.boundingBox
            return CaptureOCRBlock(
                blockIndex: index,
                text: text,
                bbox: CaptureBBox(
                    x: box.origin.x,
                    y: box.origin.y,
                    width: box.size.width,
                    height: box.size.height
                ),
                confidence: Double(candidate.confidence)
            )
        }
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

    private static func postScrollTowardHistory(pixels: Int) {
        CGEvent(
            scrollWheelEvent2Source: CGEventSource(stateID: .hidSystemState),
            units: .pixel,
            wheelCount: 1,
            wheel1: -Int32(pixels),
            wheel2: 0,
            wheel3: 0
        )?.post(tap: .cghidEventTap)
    }
}
