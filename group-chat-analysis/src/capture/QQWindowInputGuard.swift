import AppKit
import CoreGraphics
import ScreenCaptureKit

enum QQWindowInputError: Error, CustomStringConvertible {
    case notForeground
    case unsafeWindow

    var description: String {
        switch self {
        case .notForeground:
            return "QQ is no longer frontmost; mouse input stopped."
        case .unsafeWindow:
            return "The verified QQ window is not safely exposed at the mouse position; mouse input stopped."
        }
    }
}

enum QQWindowInputGuard {
    @MainActor
    static func requireExposed(_ window: SCWindow, at point: CGPoint) throws {
        guard let owner = window.owningApplication,
              owner.bundleIdentifier == "com.tencent.qq",
              NSWorkspace.shared.frontmostApplication?.processIdentifier == owner.processID else {
            throw QQWindowInputError.notForeground
        }
        guard let windows = CGWindowListCopyWindowInfo(
            [.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID
        ) as? [[String: Any]],
              isExposed(windowID: window.windowID, pid: owner.processID, frame: window.frame,
                        at: point, windows: windows, mainDisplay: CGDisplayBounds(CGMainDisplayID())) else {
            throw QQWindowInputError.unsafeWindow
        }
        guard NSWorkspace.shared.frontmostApplication?.processIdentifier == owner.processID else {
            throw QQWindowInputError.notForeground
        }
    }

    static func isExposed(
        windowID: CGWindowID, pid: pid_t, frame: CGRect, at point: CGPoint,
        windows: [[String: Any]], mainDisplay: CGRect
    ) -> Bool {
        guard frame.contains(point) else { return false }
        // The on-screen list is front to back. Use the first visible surface
        // at this point, even when the covering window is also owned by QQ.
        for window in windows {
            if let alpha = window[kCGWindowAlpha as String] as? Double, alpha == 0 { continue }
            guard let bounds = window[kCGWindowBounds as String] as? [String: Any],
                  let rect = CGRect(dictionaryRepresentation: bounds as CFDictionary) else { return false }
            guard rect.contains(point) else { continue }

            // The verified full-display Dock backing surface passes pointer
            // input through. A visible Dock panel or other overlay still blocks.
            let owner = window[kCGWindowOwnerName as String] as? String
            if (owner == "Dock" || owner == "程序坞"),
               window[kCGWindowLayer as String] as? Int == 20,
               matches(rect, mainDisplay) {
                continue
            }

            return window[kCGWindowNumber as String] as? CGWindowID == windowID
                && window[kCGWindowOwnerPID as String] as? pid_t == pid
                && matches(rect, frame)
        }
        return false
    }

    private static func matches(_ left: CGRect, _ right: CGRect) -> Bool {
        abs(left.minX - right.minX) <= 1 && abs(left.minY - right.minY) <= 1
            && abs(left.width - right.width) <= 1 && abs(left.height - right.height) <= 1
    }
}
