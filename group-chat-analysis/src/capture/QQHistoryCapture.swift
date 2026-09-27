import AppKit
import CoreGraphics
import Foundation
import ScreenCaptureKit
import Vision

struct CaptureBBox: Codable {
    let x: Double
    let y: Double
    let width: Double
    let height: Double
}

struct CaptureOCRBlock: Codable {
    let blockIndex: Int
    let text: String
    let bbox: CaptureBBox
    let confidence: Double

    enum CodingKeys: String, CodingKey {
        case blockIndex = "block_index"
        case text
        case bbox
        case confidence
    }
}

struct CaptureWindowInfo: Codable {
    let windowID: Int
    let title: String
    let width: Int
    let height: Int

    enum CodingKeys: String, CodingKey {
        case windowID = "window_id"
        case title
        case width
        case height
    }
}

struct RawCapturePage: Codable {
    let schemaVersion: String
    let batchID: String
    let pageIndex: Int
    let groupKey: String
    let groupDisplay: String
    let source: String
    let observedAt: String
    let window: CaptureWindowInfo
    let coordinateSpace: String
    let blocks: [CaptureOCRBlock]

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case batchID = "batch_id"
        case pageIndex = "page_index"
        case groupKey = "group_key"
        case groupDisplay = "group_display"
        case source
        case observedAt = "observed_at"
        case window
        case coordinateSpace = "coordinate_space"
        case blocks
    }
}

enum QQHistoryCaptureError: Error, CustomStringConvertible {
    case qqNotRunning
    case qqNotForeground
    case historyWindowNotFound(expectedTitle: String)
    case historyWindowChanged
    case safeScrollAnchorNotFound
    case captureFailed
    case noOCRResults

    var description: String {
        switch self {
        case .qqNotRunning:
            return "QQ is not running."
        case .qqNotForeground:
            return "QQ is no longer frontmost; capture stopped."
        case let .historyWindowNotFound(expectedTitle):
            return "No visible QQ history window matched expected title: \(expectedTitle)"
        case .historyWindowChanged:
            return "QQ history window changed during capture."
        case .safeScrollAnchorNotFound:
            return "No safe OCR message block was available for scrolling."
        case .captureFailed:
            return "Failed to capture the QQ history window."
        case .noOCRResults:
            return "Apple Vision returned no OCR blocks."
        }
    }
}

struct QQHistoryCapture {
    private static let qqBundleID = "com.tencent.qq"
    private static let minimumWindowWidth: CGFloat = 500
    private static let minimumWindowHeight: CGFloat = 400
    private static let preferredWindowWidth: CGFloat = 1562
    private static let preferredWindowHeight: CGFloat = 978
    private static let resizeRightMargin: CGFloat = 20
    private static let resizeBottomMargin: CGFloat = 80
    private static let preferredRightReserve: CGFloat = 726
    private static let minimumLeftMargin: CGFloat = 40
    private static let historyScrollRatio: CGFloat = 630.0 / 1033.0

    @MainActor
    static func activateQQForSession() async throws {
        guard let qq = NSRunningApplication.runningApplications(
            withBundleIdentifier: qqBundleID
        ).first else {
            throw QQHistoryCaptureError.qqNotRunning
        }

        qq.activate(options: [.activateAllWindows])
        try await Task.sleep(nanoseconds: 900_000_000)

        guard NSWorkspace.shared.frontmostApplication?.bundleIdentifier == qqBundleID else {
            throw QQHistoryCaptureError.qqNotForeground
        }
    }

    @MainActor
    static func prepareHistoryWindow(
        expectedTitle: String
    ) async throws {
        var target = try await validatedHistoryWindow(expectedTitle: expectedTitle)

        if target.frame.width < preferredWindowWidth ||
            target.frame.height < preferredWindowHeight {
            if let displayBounds = displayBounds(containing: CGPoint(
                x: target.frame.midX,
                y: target.frame.midY
            )) {
                let start = CGPoint(
                    x: target.frame.maxX - 2,
                    y: target.frame.maxY - 2
                )
                let destination = CGPoint(
                    x: min(displayBounds.maxX - resizeRightMargin, target.frame.minX + preferredWindowWidth - 2),
                    y: min(displayBounds.maxY - resizeBottomMargin, target.frame.minY + preferredWindowHeight - 2)
                )

                if destination.x > start.x + 40 ||
                    destination.y > start.y + 40 {
                    postMouse(.mouseMoved, at: start)
                    try await Task.sleep(nanoseconds: 200_000_000)
                    postMouse(.leftMouseDown, at: start)
                    try await Task.sleep(nanoseconds: 120_000_000)

                    let steps = 24
                    for step in 1...steps {
                        let t = CGFloat(step) / CGFloat(steps)
                        let point = CGPoint(
                            x: start.x + (destination.x - start.x) * t,
                            y: start.y + (destination.y - start.y) * t
                        )
                        postMouse(.leftMouseDragged, at: point)
                        try await Task.sleep(nanoseconds: 30_000_000)
                    }

                    postMouse(.leftMouseUp, at: destination)
                    try await Task.sleep(nanoseconds: 700_000_000)
                    target = try await validatedHistoryWindow(expectedTitle: expectedTitle)
                }
            }
        }

        try await shiftHistoryWindowLeftIfNeeded(target)
        _ = try await validatedHistoryWindow(expectedTitle: expectedTitle)
    }

    @MainActor
    private static func shiftHistoryWindowLeftIfNeeded(
        _ target: SCWindow
    ) async throws {
        guard let screen = displayBounds(containing: CGPoint(
            x: target.frame.midX,
            y: target.frame.midY
        )) else {
            return
        }

        let currentRightGap = screen.maxX - target.frame.maxX
        guard currentRightGap + 5 < preferredRightReserve else {
            return
        }

        let desiredDX = (screen.maxX - preferredRightReserve) - target.frame.maxX
        let minimumDX = (screen.minX + minimumLeftMargin) - target.frame.minX
        let dx = max(desiredDX, minimumDX)

        guard dx < -5 else {
            return
        }

        let start = CGPoint(
            x: target.frame.midX,
            y: target.frame.minY + 22
        )
        let destination = CGPoint(
            x: start.x + dx,
            y: start.y
        )

        postMouse(.mouseMoved, at: start)
        try await Task.sleep(nanoseconds: 180_000_000)
        postMouse(.leftMouseDown, at: start)
        try await Task.sleep(nanoseconds: 120_000_000)

        let steps = 18
        for step in 1...steps {
            let t = CGFloat(step) / CGFloat(steps)
            let point = CGPoint(
                x: start.x + (destination.x - start.x) * t,
                y: start.y
            )
            postMouse(.leftMouseDragged, at: point)
            try await Task.sleep(nanoseconds: 30_000_000)
        }

        postMouse(.leftMouseUp, at: destination)
        try await Task.sleep(nanoseconds: 700_000_000)
    }

    @MainActor
    static func capturePage(
        groupKey: String,
        expectedTitle: String,
        batchID: String,
        pageIndex: Int
    ) async throws -> RawCapturePage {
        let target = try await validatedHistoryWindow(expectedTitle: expectedTitle)
        let image = try await captureImage(target)
        let blocks = try recognizeText(image)

        guard !blocks.isEmpty else {
            throw QQHistoryCaptureError.noOCRResults
        }

        return RawCapturePage(
            schemaVersion: "1",
            batchID: batchID,
            pageIndex: pageIndex,
            groupKey: groupKey,
            groupDisplay: target.title ?? expectedTitle,
            source: "qq_history_window_ocr",
            observedAt: ISO8601DateFormatter().string(from: Date()),
            window: CaptureWindowInfo(
                windowID: Int(target.windowID),
                title: target.title ?? expectedTitle,
                width: image.width,
                height: image.height
            ),
            coordinateSpace: "vision_normalized_bottom_left",
            blocks: blocks
        )
    }

    @MainActor
    static func scrollTowardHistory(
        expectedTitle: String,
        page: RawCapturePage
    ) async throws -> Int32 {
        let target = try await validatedHistoryWindow(expectedTitle: expectedTitle)

        guard Int(target.windowID) == page.window.windowID else {
            throw QQHistoryCaptureError.historyWindowChanged
        }

        guard let anchor = chooseScrollAnchor(from: page.blocks) else {
            throw QQHistoryCaptureError.safeScrollAnchorNotFound
        }

        let currentWidth = target.frame.width
        let currentHeight = target.frame.height
        let localX = CGFloat(anchor.bbox.x + anchor.bbox.width / 2.0) * currentWidth
        let localY = (1.0 - CGFloat(anchor.bbox.y + anchor.bbox.height / 2.0)) * currentHeight
        let global = CGPoint(
            x: target.frame.minX + localX,
            y: target.frame.minY + localY
        )

        let pixelDelta = Int32((currentHeight * historyScrollRatio).rounded())

        CGEvent(
            mouseEventSource: nil,
            mouseType: .mouseMoved,
            mouseCursorPosition: global,
            mouseButton: .left
        )?.post(tap: .cghidEventTap)

        try await Task.sleep(nanoseconds: 150_000_000)

        guard NSWorkspace.shared.frontmostApplication?.bundleIdentifier == qqBundleID else {
            throw QQHistoryCaptureError.qqNotForeground
        }

        CGEvent(
            scrollWheelEvent2Source: CGEventSource(stateID: .hidSystemState),
            units: .pixel,
            wheelCount: 1,
            wheel1: -pixelDelta,
            wheel2: 0,
            wheel3: 0
        )?.post(tap: .cghidEventTap)

        try await Task.sleep(nanoseconds: 650_000_000)
        return pixelDelta
    }

    @MainActor
    private static func validatedHistoryWindow(expectedTitle: String) async throws -> SCWindow {
        guard NSRunningApplication.runningApplications(
            withBundleIdentifier: qqBundleID
        ).first != nil else {
            throw QQHistoryCaptureError.qqNotRunning
        }

        guard NSWorkspace.shared.frontmostApplication?.bundleIdentifier == qqBundleID else {
            throw QQHistoryCaptureError.qqNotForeground
        }

        let content = try await SCShareableContent.excludingDesktopWindows(
            false,
            onScreenWindowsOnly: true
        )

        let candidates = content.windows.filter { window in
            window.owningApplication?.bundleIdentifier == qqBundleID &&
            window.isOnScreen &&
            window.title == expectedTitle &&
            window.frame.width > minimumWindowWidth &&
            window.frame.height > minimumWindowHeight
        }

        guard let target = candidates.max(by: {
            $0.frame.width * $0.frame.height < $1.frame.width * $1.frame.height
        }) else {
            throw QQHistoryCaptureError.historyWindowNotFound(expectedTitle: expectedTitle)
        }

        return target
    }

    @MainActor
    private static func captureImage(_ window: SCWindow) async throws -> CGImage {
        let filter = SCContentFilter(desktopIndependentWindow: window)
        let config = SCStreamConfiguration()
        config.width = Int(window.frame.width)
        config.height = Int(window.frame.height)
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

    private static func chooseScrollAnchor(
        from blocks: [CaptureOCRBlock]
    ) -> CaptureOCRBlock? {
        let candidates = blocks.filter { block in
            let midX = block.bbox.x + block.bbox.width / 2.0
            let midY = block.bbox.y + block.bbox.height / 2.0

            return block.confidence >= 0.5 &&
                !isToolbarText(block.text) &&
                !isTimeOnly(block.text) &&
                midX > 0.02 && midX < 0.70 &&
                midY > 0.15 && midY < 0.82 &&
                block.bbox.width >= 0.02
        }

        return candidates.min { lhs, rhs in
            let lhsY = lhs.bbox.y + lhs.bbox.height / 2.0
            let rhsY = rhs.bbox.y + rhs.bbox.height / 2.0
            return abs(lhsY - 0.5) < abs(rhsY - 0.5)
        }
    }

    private static func isToolbarText(_ text: String) -> Bool {
        let compact = text.replacingOccurrences(of: " ", with: "")
        let exact: Set<String> = ["全部", "图片/视频", "表情", "文件", "链接", "筛选"]

        if exact.contains(compact) {
            return true
        }

        return compact.contains("搜索") ||
            (compact.contains("搜") && compact.count <= 5)
    }

    private static func postMouse(
        _ type: CGEventType,
        at point: CGPoint
    ) {
        CGEvent(
            mouseEventSource: CGEventSource(stateID: .hidSystemState),
            mouseType: type,
            mouseCursorPosition: point,
            mouseButton: .left
        )?.post(tap: .cghidEventTap)
    }

    private static func displayBounds(
        containing point: CGPoint
    ) -> CGRect? {
        var count: UInt32 = 0
        guard CGGetActiveDisplayList(0, nil, &count) == .success else {
            return nil
        }

        var displays = [CGDirectDisplayID](repeating: 0, count: Int(count))
        guard CGGetActiveDisplayList(count, &displays, &count) == .success else {
            return nil
        }

        return displays
            .map { CGDisplayBounds($0) }
            .first { $0.contains(point) }
    }

    private static func isTimeOnly(_ text: String) -> Bool {
        text.range(
            of: #"^\s*[•.]?\s*\d{1,2}:\d{2}\s*$"#,
            options: .regularExpression
        ) != nil
    }
}
