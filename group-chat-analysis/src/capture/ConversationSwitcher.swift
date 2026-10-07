import AppKit
import ApplicationServices
import Foundation
import ScreenCaptureKit
import Vision

struct QQConversationTarget {
    let groupKey: String
    let conversationPrefix: String
    let headerContains: String
    let expectedHistoryTitle: String
}

enum ConversationSwitchError: Error, CustomStringConvertible {
    case qqNotRunning
    case accessibilityNotTrusted
    case mainAXWindowNotFound
    case mainSCKWindowNotFound
    case conversationCandidateCount(Int)
    case unsafeConversationCandidate
    case targetVerificationFailed
    case historyTooltipNotVerified([String])
    case historyWindowNotReady(String)

    var description: String {
        switch self {
        case .qqNotRunning:
            return "QQ is not running."
        case .accessibilityNotTrusted:
            return "macOS Accessibility permission is not available."
        case .mainAXWindowNotFound:
            return "Could not identify the unique main QQ AXWindow."
        case .mainSCKWindowNotFound:
            return "Could not identify the unique visible main QQ SCK window."
        case let .conversationCandidateCount(count):
            return "Target conversation was not uniquely visible in the left QQ conversation list (count=\(count))."
        case .unsafeConversationCandidate:
            return "Target conversation OCR candidate was outside the verified left-list safety region."
        case .targetVerificationFailed:
            return "QQ main view did not verify the selected target group after switching."
        case let .historyTooltipNotVerified(texts):
            return "Chat-history tooltip verification failed: \(texts)"
        case let .historyWindowNotReady(title):
            return "QQ history window did not become uniquely available with exact title: \(title)"
        }
    }
}

struct QQConversationSwitcher {
    private static let qqBundleID = "com.tencent.qq"
    private static let mainWindowTitle = "QQ"
    private static let historyIconX = 0.818
    private static let historyIconY = 0.19
    private static let historyTooltipROI = CGRect(x: 0.76, y: 0.18, width: 0.12, height: 0.14)

    @MainActor
    static func openHistory(_ target: QQConversationTarget) async throws {
        guard let qq = NSRunningApplication.runningApplications(
            withBundleIdentifier: qqBundleID
        ).first else {
            throw ConversationSwitchError.qqNotRunning
        }
        guard AXIsProcessTrusted() else {
            throw ConversationSwitchError.accessibilityNotTrusted
        }

        let axWindow = try exactMainAXWindow(pid: qq.processIdentifier)
        _ = AXUIElementPerformAction(axWindow, kAXRaiseAction as CFString)
        qq.activate(options: [])
        try await Task.sleep(nanoseconds: 500_000_000)

        let mainWindow = try await exactMainSCKWindow()
        let before = try await capture(mainWindow)
        let blocks = try recognizeText(before)
        let candidate = try conversationCandidate(
            from: blocks,
            prefix: target.conversationPrefix
        )
        let candidatePoint = screenPoint(for: candidate.bbox, in: mainWindow.frame)
        postClick(candidatePoint)
        try await Task.sleep(nanoseconds: 500_000_000)

        let selectedWindow = try await exactMainSCKWindow()
        let selectedBlocks = try recognizeText(try await capture(selectedWindow))
        guard verifiesTarget(selectedBlocks, target: target) else {
            throw ConversationSwitchError.targetVerificationFailed
        }

        let historyPoint = CGPoint(
            x: selectedWindow.frame.origin.x + historyIconX * selectedWindow.frame.width,
            y: selectedWindow.frame.origin.y + (1.0 - historyIconY) * selectedWindow.frame.height
        )
        postMouseMove(historyPoint)
        try await Task.sleep(nanoseconds: 1_000_000_000)
        let tooltipTexts = try recognizeTooltip(try await capture(selectedWindow))
        guard isVerifiedHistoryTooltip(tooltipTexts) else {
            throw ConversationSwitchError.historyTooltipNotVerified(tooltipTexts)
        }
        postClick(historyPoint)

        try await waitForHistoryWindow(exactTitle: target.expectedHistoryTitle)
    }

    static func conversationCandidate(
        from blocks: [CaptureOCRBlock],
        prefix: String
    ) throws -> CaptureOCRBlock {
        var safeMatches: [CaptureOCRBlock] = []
        var textMatches = 0
        for block in blocks {
            guard compact(block.text).contains(compact(prefix)) else { continue }
            textMatches += 1
            let centerX = block.bbox.x + block.bbox.width / 2.0
            let centerY = block.bbox.y + block.bbox.height / 2.0
            if centerX >= 0.05,
               centerX <= 0.30,
               centerY >= 0.05,
               centerY <= 0.90,
               block.bbox.width >= 0.04,
               block.bbox.height >= 0.008 {
                safeMatches.append(block)
            }
        }
        guard safeMatches.count == 1, let match = safeMatches.first else {
            if textMatches > 0 && safeMatches.isEmpty {
                throw ConversationSwitchError.unsafeConversationCandidate
            }
            throw ConversationSwitchError.conversationCandidateCount(safeMatches.count)
        }
        return match
    }

    static func verifiesTarget(
        _ blocks: [CaptureOCRBlock],
        target: QQConversationTarget
    ) -> Bool {
        let texts = blocks.map { compact($0.text) }
        return texts.contains { $0.contains(compact(target.headerContains)) }
    }

    static func isVerifiedHistoryTooltip(_ texts: [String]) -> Bool {
        texts.contains { compact($0) == "聊天记录" }
    }

    @MainActor
    private static func exactMainAXWindow(pid: pid_t) throws -> AXUIElement {
        let app = AXUIElementCreateApplication(pid)
        var raw: CFTypeRef?
        guard AXUIElementCopyAttributeValue(
            app,
            kAXWindowsAttribute as CFString,
            &raw
        ) == .success,
        let windows = raw as? [AXUIElement] else {
            throw ConversationSwitchError.mainAXWindowNotFound
        }

        var matches: [AXUIElement] = []
        for window in windows {
            var titleRaw: CFTypeRef?
            guard AXUIElementCopyAttributeValue(
                window,
                kAXTitleAttribute as CFString,
                &titleRaw
            ) == .success,
            let title = titleRaw as? String,
            title == mainWindowTitle else {
                continue
            }
            matches.append(window)
        }
        guard matches.count == 1, let match = matches.first else {
            throw ConversationSwitchError.mainAXWindowNotFound
        }
        return match
    }

    @MainActor
    private static func exactMainSCKWindow() async throws -> SCWindow {
        let content = try await SCShareableContent.excludingDesktopWindows(
            false,
            onScreenWindowsOnly: true
        )
        var matches: [SCWindow] = []
        for window in content.windows {
            if window.owningApplication?.bundleIdentifier == qqBundleID,
               window.isOnScreen,
               window.title == mainWindowTitle {
                matches.append(window)
            }
        }
        guard matches.count == 1, let match = matches.first else {
            throw ConversationSwitchError.mainSCKWindowNotFound
        }
        return match
    }

    @MainActor
    private static func capture(_ window: SCWindow) async throws -> CGImage {
        let filter = SCContentFilter(desktopIndependentWindow: window)
        let config = SCStreamConfiguration()
        config.width = max(1, Int(window.frame.width.rounded()))
        config.height = max(1, Int(window.frame.height.rounded()))
        config.showsCursor = false
        config.capturesAudio = false
        return try await SCScreenshotManager.captureImage(
            contentFilter: filter,
            configuration: config
        )
    }

    private static func recognizeText(_ image: CGImage) throws -> [CaptureOCRBlock] {
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.recognitionLanguages = ["zh-Hans", "en-US"]
        request.usesLanguageCorrection = true
        try VNImageRequestHandler(cgImage: image, options: [:]).perform([request])

        return (request.results ?? []).enumerated().compactMap { index, observation in
            guard let candidate = observation.topCandidates(1).first else { return nil }
            return CaptureOCRBlock(
                blockIndex: index,
                text: candidate.string,
                bbox: CaptureBBox(
                    x: observation.boundingBox.origin.x,
                    y: observation.boundingBox.origin.y,
                    width: observation.boundingBox.width,
                    height: observation.boundingBox.height
                ),
                confidence: Double(candidate.confidence)
            )
        }
    }

    private static func recognizeTooltip(_ image: CGImage) throws -> [String] {
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.recognitionLanguages = ["zh-Hans", "en-US"]
        request.usesLanguageCorrection = false
        request.regionOfInterest = historyTooltipROI
        request.minimumTextHeight = 0.01
        try VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
        return (request.results ?? []).compactMap {
            $0.topCandidates(1).first?.string
        }
    }

    @MainActor
    private static func waitForHistoryWindow(exactTitle: String) async throws {
        let checkpoints = [150, 350, 700, 1200]
        var previous = 0
        for checkpoint in checkpoints {
            let delta = checkpoint - previous
            try await Task.sleep(nanoseconds: UInt64(delta) * 1_000_000)
            previous = checkpoint
            let content = try await SCShareableContent.excludingDesktopWindows(
                false,
                onScreenWindowsOnly: true
            )
            var count = 0
            for window in content.windows {
                if window.owningApplication?.bundleIdentifier == qqBundleID,
                   window.isOnScreen,
                   window.title == exactTitle {
                    count += 1
                }
            }
            if count == 1 {
                return
            }
        }
        throw ConversationSwitchError.historyWindowNotReady(exactTitle)
    }

    private static func screenPoint(for bbox: CaptureBBox, in frame: CGRect) -> CGPoint {
        let midX = bbox.x + bbox.width / 2.0
        let midY = bbox.y + bbox.height / 2.0
        return CGPoint(
            x: frame.origin.x + midX * frame.width,
            y: frame.origin.y + (1.0 - midY) * frame.height
        )
    }

    private static func postMouseMove(_ point: CGPoint) {
        CGEvent(
            mouseEventSource: nil,
            mouseType: .mouseMoved,
            mouseCursorPosition: point,
            mouseButton: .left
        )?.post(tap: .cghidEventTap)
    }

    private static func postClick(_ point: CGPoint) {
        postMouseMove(point)
        usleep(150_000)
        CGEvent(
            mouseEventSource: nil,
            mouseType: .leftMouseDown,
            mouseCursorPosition: point,
            mouseButton: .left
        )?.post(tap: .cghidEventTap)
        usleep(60_000)
        CGEvent(
            mouseEventSource: nil,
            mouseType: .leftMouseUp,
            mouseCursorPosition: point,
            mouseButton: .left
        )?.post(tap: .cghidEventTap)
    }

    private static func compact(_ text: String) -> String {
        text.replacingOccurrences(of: " ", with: "")
            .replacingOccurrences(of: "\n", with: "")
    }
}
