import AppKit
import ApplicationServices
import CoreGraphics
import Foundation
import ScreenCaptureKit

private let qqBundleID = "com.tencent.qq"

enum WindowPreparationError: Error, CustomStringConvertible {
    case qqNotRunning
    case accessibilityNotTrusted
    case exactWindowNotFound(String)
    case ambiguousExactWindows(String, Int)
    case attributeNotSettable(String)
    case cannotReadAttribute(String)
    case cannotSetAttribute(String)
    case geometryMismatch(expected: WindowTargetGeometry, actual: WindowTargetGeometry)
    case sckWindowNotFound(String)
    case sckAmbiguousWindows(String, Int)
    case sckGeometryMismatch(expected: WindowTargetGeometry, actual: WindowTargetGeometry)

    var description: String {
        switch self {
        case .qqNotRunning:
            return "QQ is not running."
        case .accessibilityNotTrusted:
            return "macOS Accessibility permission is not available."
        case let .exactWindowNotFound(title):
            return "No QQ AXWindow exactly matched title: \(title)"
        case let .ambiguousExactWindows(title, count):
            return "More than one QQ AXWindow exactly matched title: \(title) (count=\(count))"
        case let .attributeNotSettable(attribute):
            return "QQ history window attribute is not settable: \(attribute)"
        case let .cannotReadAttribute(attribute):
            return "Could not read QQ history window attribute: \(attribute)"
        case let .cannotSetAttribute(attribute):
            return "Could not set QQ history window attribute: \(attribute)"
        case let .geometryMismatch(expected, actual):
            return "QQ history AX geometry mismatch. expected=\(expected) actual=\(actual)"
        case let .sckWindowNotFound(title):
            return "No visible SCK QQ window exactly matched title after AX preparation: \(title)"
        case let .sckAmbiguousWindows(title, count):
            return "More than one visible SCK QQ window exactly matched title: \(title) (count=\(count))"
        case let .sckGeometryMismatch(expected, actual):
            return "QQ history SCK geometry did not settle. expected=\(expected) actual=\(actual)"
        }
    }
}

struct QQWindowPreparer {
    @MainActor
    static func activateQQ() async throws -> pid_t {
        guard let qq = NSRunningApplication.runningApplications(
            withBundleIdentifier: qqBundleID
        ).first else {
            throw WindowPreparationError.qqNotRunning
        }

        qq.activate(options: [.activateAllWindows])
        try await Task.sleep(nanoseconds: 500_000_000)
        return qq.processIdentifier
    }

    @MainActor
    static func prepare(
        expectedTitle: String,
        geometry: WindowTargetGeometry,
        tolerance: Double = 2.0
    ) async throws {
        let pid = try await activateQQ()
        guard AXIsProcessTrusted() else {
            throw WindowPreparationError.accessibilityNotTrusted
        }

        let window = try exactWindow(pid: pid, title: expectedTitle)
        try requireSettable(window, attribute: kAXPositionAttribute as CFString)
        try requireSettable(window, attribute: kAXSizeAttribute as CFString)

        try setPoint(
            window,
            attribute: kAXPositionAttribute as CFString,
            point: CGPoint(x: geometry.x, y: geometry.y)
        )
        try setSize(
            window,
            attribute: kAXSizeAttribute as CFString,
            size: CGSize(width: geometry.width, height: geometry.height)
        )

        try await Task.sleep(nanoseconds: 250_000_000)
        let actual = try readGeometry(window)
        guard approximatelyEqual(actual.x, geometry.x, tolerance: tolerance),
              approximatelyEqual(actual.y, geometry.y, tolerance: tolerance),
              approximatelyEqual(actual.width, geometry.width, tolerance: tolerance),
              approximatelyEqual(actual.height, geometry.height, tolerance: tolerance) else {
            throw WindowPreparationError.geometryMismatch(expected: geometry, actual: actual)
        }

        try await waitForSCKGeometry(
            expectedTitle: expectedTitle,
            expected: geometry,
            tolerance: max(3.0, tolerance)
        )
    }

    private static func exactWindow(pid: pid_t, title: String) throws -> AXUIElement {
        let app = AXUIElementCreateApplication(pid)
        var value: CFTypeRef?
        let result = AXUIElementCopyAttributeValue(
            app,
            kAXWindowsAttribute as CFString,
            &value
        )
        guard result == .success, let windows = value as? [AXUIElement] else {
            throw WindowPreparationError.cannotReadAttribute(kAXWindowsAttribute)
        }

        var matches: [AXUIElement] = []
        for window in windows {
            var titleValue: CFTypeRef?
            guard AXUIElementCopyAttributeValue(
                window,
                kAXTitleAttribute as CFString,
                &titleValue
            ) == .success else {
                continue
            }
            if (titleValue as? String) == title {
                matches.append(window)
            }
        }
        guard !matches.isEmpty else {
            throw WindowPreparationError.exactWindowNotFound(title)
        }
        guard matches.count == 1, let match = matches.first else {
            throw WindowPreparationError.ambiguousExactWindows(title, matches.count)
        }
        return match
    }

    private static func requireSettable(
        _ window: AXUIElement,
        attribute: CFString
    ) throws {
        var settable = DarwinBoolean(false)
        guard AXUIElementIsAttributeSettable(window, attribute, &settable) == .success,
              settable.boolValue else {
            throw WindowPreparationError.attributeNotSettable(attribute as String)
        }
    }

    private static func setPoint(
        _ window: AXUIElement,
        attribute: CFString,
        point: CGPoint
    ) throws {
        var point = point
        guard let value = AXValueCreate(.cgPoint, &point),
              AXUIElementSetAttributeValue(window, attribute, value) == .success else {
            throw WindowPreparationError.cannotSetAttribute(attribute as String)
        }
    }

    private static func setSize(
        _ window: AXUIElement,
        attribute: CFString,
        size: CGSize
    ) throws {
        var size = size
        guard let value = AXValueCreate(.cgSize, &size),
              AXUIElementSetAttributeValue(window, attribute, value) == .success else {
            throw WindowPreparationError.cannotSetAttribute(attribute as String)
        }
    }

    private static func readGeometry(_ window: AXUIElement) throws -> WindowTargetGeometry {
        var pointValue: CFTypeRef?
        var sizeValue: CFTypeRef?
        guard AXUIElementCopyAttributeValue(
            window,
            kAXPositionAttribute as CFString,
            &pointValue
        ) == .success,
        AXUIElementCopyAttributeValue(
            window,
            kAXSizeAttribute as CFString,
            &sizeValue
        ) == .success,
        let pointValue,
        let sizeValue,
        CFGetTypeID(pointValue) == AXValueGetTypeID(),
        CFGetTypeID(sizeValue) == AXValueGetTypeID() else {
            throw WindowPreparationError.cannotReadAttribute("AXPosition/AXSize")
        }

        let pointAX = unsafeBitCast(pointValue, to: AXValue.self)
        let sizeAX = unsafeBitCast(sizeValue, to: AXValue.self)
        var point = CGPoint.zero
        var size = CGSize.zero
        guard AXValueGetValue(pointAX, .cgPoint, &point),
              AXValueGetValue(sizeAX, .cgSize, &size) else {
            throw WindowPreparationError.cannotReadAttribute("AXPosition/AXSize")
        }

        return WindowTargetGeometry(
            x: point.x,
            y: point.y,
            width: size.width,
            height: size.height
        )
    }

    @MainActor
    private static func waitForSCKGeometry(
        expectedTitle: String,
        expected: WindowTargetGeometry,
        tolerance: Double
    ) async throws {
        let checkpoints = [100, 250, 500, 1000]
        var previousCheckpoint = 0
        var lastActual: WindowTargetGeometry?

        for checkpoint in checkpoints {
            let delta = checkpoint - previousCheckpoint
            try await Task.sleep(nanoseconds: UInt64(delta) * 1_000_000)
            previousCheckpoint = checkpoint

            let content = try await SCShareableContent.excludingDesktopWindows(
                false,
                onScreenWindowsOnly: true
            )
            let matches = content.windows.filter { window in
                window.owningApplication?.bundleIdentifier == qqBundleID &&
                    window.isOnScreen &&
                    window.title == expectedTitle
            }
            guard !matches.isEmpty else {
                throw WindowPreparationError.sckWindowNotFound(expectedTitle)
            }
            guard matches.count == 1, let target = matches.first else {
                throw WindowPreparationError.sckAmbiguousWindows(expectedTitle, matches.count)
            }

            let actual = WindowTargetGeometry(
                x: target.frame.origin.x,
                y: target.frame.origin.y,
                width: target.frame.width,
                height: target.frame.height
            )
            lastActual = actual
            if approximatelyEqual(actual.x, expected.x, tolerance: tolerance),
               approximatelyEqual(actual.y, expected.y, tolerance: tolerance),
               approximatelyEqual(actual.width, expected.width, tolerance: tolerance),
               approximatelyEqual(actual.height, expected.height, tolerance: tolerance) {
                return
            }
        }

        throw WindowPreparationError.sckGeometryMismatch(
            expected: expected,
            actual: lastActual ?? WindowTargetGeometry(x: 0, y: 0, width: 0, height: 0)
        )
    }

    private static func approximatelyEqual(
        _ left: Double,
        _ right: Double,
        tolerance: Double
    ) -> Bool {
        abs(left - right) <= tolerance
    }
}
