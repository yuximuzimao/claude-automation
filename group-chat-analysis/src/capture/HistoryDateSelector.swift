import AppKit
import CoreGraphics
import Foundation
import ScreenCaptureKit

struct HistoryDateSelectionResult {
    let target: String
    let row: Int
    let column: Int
    let monthSteps: Int
}

enum HistoryDateSelectorError: Error, CustomStringConvertible {
    case qqNotForeground
    case historyWindowNotFound(String)
    case ambiguousHistoryWindows(String, Int)
    case filterPanelDidNotOpen
    case calendarDidNotOpen
    case calendarMonthNotFound
    case calendarMonthAmbiguous([String])
    case calendarMonthDidNotAdvance(expected: String, actual: String?)
    case invalidTargetDate(String)
    case targetDateNotApplied(String)
    case chatDateNotVerified(String)
    case filterPanelDidNotClose

    var description: String {
        switch self {
        case .qqNotForeground:
            return "QQ is no longer frontmost."
        case let .historyWindowNotFound(title):
            return "No visible QQ history window exactly matched title: \(title)"
        case let .ambiguousHistoryWindows(title, count):
            return "More than one visible QQ history window matched title: \(title) (count=\(count))"
        case .filterPanelDidNotOpen:
            return "QQ history filter panel did not open."
        case .calendarDidNotOpen:
            return "QQ history date calendar did not open."
        case .calendarMonthNotFound:
            return "Could not OCR the QQ calendar month label."
        case let .calendarMonthAmbiguous(values):
            return "QQ calendar month label was ambiguous: \(values)"
        case let .calendarMonthDidNotAdvance(expected, actual):
            return "QQ calendar month navigation mismatch. expected=\(expected) actual=\(actual ?? "nil")"
        case let .invalidTargetDate(value):
            return "Invalid target date: \(value)"
        case let .targetDateNotApplied(value):
            return "QQ filter field did not verify target date: \(value)"
        case let .chatDateNotVerified(value):
            return "QQ chat area did not verify target date: \(value)"
        case .filterPanelDidNotClose:
            return "QQ history filter panel did not close after verification."
        }
    }
}

struct HistoryDateSelector {
    private static let qqBundleID = "com.tencent.qq"

    // All fixed points are relative to the prepared history window.  The
    // values are normalized from the locally verified 1562x978 geometry so
    // the selector does not mix screenshot pixels with global screen points.
    private static let filterButton = CGPoint(x: 1489.0 / 1562.0, y: 103.0 / 978.0)
    private static let dateField = CGPoint(x: 1418.0 / 1562.0, y: 239.0 / 978.0)
    private static let closeFilter = CGPoint(x: 1522.0 / 1562.0, y: 152.0 / 978.0)
    // Calendar cells are Sunday-first.  These are cell-center geometry values,
    // not dates: row/column are calculated from the requested date each time.
    private static let firstColumnCenterX = 1316.0 / 1562.0
    private static let columnStepX = 34.0 / 1562.0
    private static let firstRowCenterY = 343.0 / 978.0
    private static let rowStepY = 32.0 / 978.0

    private static var gregorian: Calendar {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(secondsFromGMT: 8 * 3600)!
        return calendar
    }

    @MainActor
    static func select(
        targetText: String,
        expectedTitle: String,
        geometry: WindowTargetGeometry
    ) async throws -> HistoryDateSelectionResult {
        guard let target = parseTargetDate(targetText) else {
            throw HistoryDateSelectorError.invalidTargetDate(targetText)
        }

        try await QQWindowPreparer.prepare(expectedTitle: expectedTitle, geometry: geometry)
        var targetWindow = try await exactHistoryWindow(expectedTitle: expectedTitle)
        var blocks = try await captureBlocks(targetWindow)

        if !isFilterPanelOpen(blocks) {
            postClick(screenPoint(relative: filterButton, frame: targetWindow.frame))
            blocks = try await waitForBlocks(expectedTitle: expectedTitle) { isFilterPanelOpen($0) }
            guard isFilterPanelOpen(blocks) else {
                throw HistoryDateSelectorError.filterPanelDidNotOpen
            }
        }

        if calendarMonth(in: blocks) == nil {
            targetWindow = try await exactHistoryWindow(expectedTitle: expectedTitle)
            postClick(screenPoint(relative: dateField, frame: targetWindow.frame))
            blocks = try await waitForBlocks(expectedTitle: expectedTitle) { calendarMonth(in: $0) != nil }
            guard calendarMonth(in: blocks) != nil else {
                throw HistoryDateSelectorError.calendarDidNotOpen
            }
        }

        var displayed = try requireCalendarMonth(blocks)
        let requested = MonthKey(year: target.year, month: target.month)
        let monthSteps = monthsBetween(displayed, requested)

        if monthSteps != 0 {
            let step = monthSteps < 0 ? -1 : 1
            for _ in 0..<abs(monthSteps) {
                targetWindow = try await exactHistoryWindow(expectedTitle: expectedTitle)
                let observation = try requireCalendarMonthObservation(blocks)
                let navigationPoint = monthNavigationPoint(
                    direction: step,
                    monthBlock: observation.block,
                    frame: targetWindow.frame
                )
                postClick(navigationPoint)
                let expected = displayed.advanced(by: step)
                blocks = try await waitForBlocks(expectedTitle: expectedTitle) {
                    calendarMonth(in: $0) == expected
                }
                let actual = calendarMonth(in: blocks)
                guard actual == expected else {
                    throw HistoryDateSelectorError.calendarMonthDidNotAdvance(
                        expected: expected.description,
                        actual: actual?.description
                    )
                }
                displayed = expected
            }
        }

        let cell = calendarCell(target)
        targetWindow = try await exactHistoryWindow(expectedTitle: expectedTitle)
        let cellPoint = CGPoint(
            x: firstColumnCenterX + Double(cell.column) * columnStepX,
            y: firstRowCenterY + Double(cell.row) * rowStepY
        )
        postClick(screenPoint(relative: cellPoint, frame: targetWindow.frame))

        let slashDate = String(format: "%04d/%02d/%02d", target.year, target.month, target.day)
        blocks = try await waitForBlocks(expectedTitle: expectedTitle) {
            filterFieldContains($0, slashDate) && chatAreaContainsDate($0, slashDate)
        }
        guard filterFieldContains(blocks, slashDate) else {
            throw HistoryDateSelectorError.targetDateNotApplied(slashDate)
        }
        guard chatAreaContainsDate(blocks, slashDate) else {
            throw HistoryDateSelectorError.chatDateNotVerified(slashDate)
        }

        targetWindow = try await exactHistoryWindow(expectedTitle: expectedTitle)
        postClick(screenPoint(relative: closeFilter, frame: targetWindow.frame))
        blocks = try await waitForBlocks(expectedTitle: expectedTitle) { !isFilterPanelOpen($0) }
        guard !isFilterPanelOpen(blocks) else {
            throw HistoryDateSelectorError.filterPanelDidNotClose
        }

        return HistoryDateSelectionResult(
            target: targetText,
            row: cell.row,
            column: cell.column,
            monthSteps: monthSteps
        )
    }

    struct TargetDate: Equatable {
        let year: Int
        let month: Int
        let day: Int
    }

    struct CalendarCell: Equatable {
        let row: Int
        let column: Int
    }

    struct MonthKey: Equatable, CustomStringConvertible {
        let year: Int
        let month: Int

        var description: String {
            String(format: "%04d-%02d", year, month)
        }

        func advanced(by delta: Int) -> MonthKey {
            let absolute = year * 12 + (month - 1) + delta
            return MonthKey(year: absolute / 12, month: absolute % 12 + 1)
        }
    }

    private struct MonthObservation {
        let month: MonthKey
        let block: CaptureOCRBlock
    }

    static func parseTargetDate(_ value: String) -> TargetDate? {
        let parts = value.split(separator: "-")
        guard parts.count == 3,
              let year = Int(parts[0]),
              let month = Int(parts[1]),
              let day = Int(parts[2]),
              (1...12).contains(month) else {
            return nil
        }
        var components = DateComponents()
        components.calendar = gregorian
        components.timeZone = gregorian.timeZone
        components.year = year
        components.month = month
        components.day = day
        guard let date = gregorian.date(from: components) else { return nil }
        let roundTrip = gregorian.dateComponents([.year, .month, .day], from: date)
        guard roundTrip.year == year, roundTrip.month == month, roundTrip.day == day else {
            return nil
        }
        return TargetDate(year: year, month: month, day: day)
    }

    static func calendarCell(_ target: TargetDate) -> CalendarCell {
        let firstComponents = DateComponents(
            calendar: gregorian,
            timeZone: gregorian.timeZone,
            year: target.year,
            month: target.month,
            day: 1
        )
        let firstDate = gregorian.date(from: firstComponents)!
        let firstWeekday = gregorian.component(.weekday, from: firstDate) - 1 // Sunday=0
        let offset = firstWeekday + target.day - 1
        return CalendarCell(row: offset / 7, column: offset % 7)
    }

    static func monthsBetween(_ left: MonthKey, _ right: MonthKey) -> Int {
        (right.year - left.year) * 12 + right.month - left.month
    }

    private static func compact(_ text: String) -> String {
        text.replacingOccurrences(of: " ", with: "")
            .replacingOccurrences(of: "\n", with: "")
    }

    private static func isFilterPanelOpen(_ blocks: [CaptureOCRBlock]) -> Bool {
        blocks.contains { block in
            compact(block.text) == "筛选条件" && block.bbox.x > 0.80
        }
    }

    private static func filterFieldContains(_ blocks: [CaptureOCRBlock], _ slashDate: String) -> Bool {
        blocks.contains { block in
            let centerX = block.bbox.x + block.bbox.width / 2.0
            let centerY = block.bbox.y + block.bbox.height / 2.0
            return centerX > 0.82 && centerY > 0.72 && centerY < 0.79 && compact(block.text).contains(slashDate)
        }
    }

    private static func chatAreaContainsDate(_ blocks: [CaptureOCRBlock], _ slashDate: String) -> Bool {
        blocks.contains { block in
            let centerX = block.bbox.x + block.bbox.width / 2.0
            let centerY = block.bbox.y + block.bbox.height / 2.0
            return centerX < 0.20 && centerY > 0.80 && centerY < 0.88 && compact(block.text) == slashDate
        }
    }

    private static func calendarMonth(in blocks: [CaptureOCRBlock]) -> MonthKey? {
        try? requireCalendarMonthObservation(blocks).month
    }

    private static func requireCalendarMonth(_ blocks: [CaptureOCRBlock]) throws -> MonthKey {
        try requireCalendarMonthObservation(blocks).month
    }

    private static func requireCalendarMonthObservation(
        _ blocks: [CaptureOCRBlock]
    ) throws -> MonthObservation {
        var values: [MonthObservation] = []
        for block in blocks {
            let centerX = block.bbox.x + block.bbox.width / 2.0
            let centerY = block.bbox.y + block.bbox.height / 2.0
            guard centerX > 0.82, centerY > 0.68, centerY < 0.74 else { continue }
            let parts = compact(block.text).split(separator: "-")
            guard parts.count == 2,
                  parts[0].count == 4,
                  let year = Int(parts[0]),
                  let month = Int(parts[1]),
                  (1...12).contains(month) else { continue }
            values.append(
                MonthObservation(month: MonthKey(year: year, month: month), block: block)
            )
        }
        let unique = Array(Set(values.map { $0.month.description }))
        guard !unique.isEmpty else { throw HistoryDateSelectorError.calendarMonthNotFound }
        guard unique.count == 1, let value = values.first else {
            throw HistoryDateSelectorError.calendarMonthAmbiguous(unique.sorted())
        }
        return value
    }

    private static func monthNavigationPoint(
        direction: Int,
        monthBlock: CaptureOCRBlock,
        frame: CGRect
    ) -> CGPoint {
        // Arrow controls are located from the OCR-confirmed month label, rather
        // than from a fixed global coordinate.  This keeps month navigation in
        // the same calendar coordinate system as the detected label.
        let gap = 0.040
        let normalizedX = direction < 0
            ? monthBlock.bbox.x - gap
            : monthBlock.bbox.maxX + gap
        let normalizedTopY = 1.0 - (monthBlock.bbox.y + monthBlock.bbox.height / 2.0)
        return CGPoint(
            x: frame.origin.x + normalizedX * frame.width,
            y: frame.origin.y + normalizedTopY * frame.height
        )
    }

    @MainActor
    private static func waitForBlocks(
        expectedTitle: String,
        predicate: ([CaptureOCRBlock]) -> Bool
    ) async throws -> [CaptureOCRBlock] {
        let checkpoints = [180, 350, 650, 1000, 1500]
        var previous = 0
        var last: [CaptureOCRBlock] = []
        for checkpoint in checkpoints {
            let delta = checkpoint - previous
            try await Task.sleep(nanoseconds: UInt64(delta) * 1_000_000)
            previous = checkpoint
            let window = try await exactHistoryWindow(expectedTitle: expectedTitle)
            last = try await captureBlocks(window)
            if predicate(last) { return last }
        }
        return last
    }

    @MainActor
    private static func exactHistoryWindow(expectedTitle: String) async throws -> SCWindow {
        guard NSWorkspace.shared.frontmostApplication?.bundleIdentifier == qqBundleID else {
            throw HistoryDateSelectorError.qqNotForeground
        }
        let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)
        let matches = content.windows.filter { window in
            window.owningApplication?.bundleIdentifier == qqBundleID &&
                window.isOnScreen &&
                window.title == expectedTitle &&
                window.frame.width > 100 &&
                window.frame.height > 100
        }
        guard !matches.isEmpty else {
            throw HistoryDateSelectorError.historyWindowNotFound(expectedTitle)
        }
        guard matches.count == 1, let match = matches.first else {
            throw HistoryDateSelectorError.ambiguousHistoryWindows(expectedTitle, matches.count)
        }
        return match
    }

    @MainActor
    private static func captureBlocks(_ window: SCWindow) async throws -> [CaptureOCRBlock] {
        let filter = SCContentFilter(desktopIndependentWindow: window)
        let config = SCStreamConfiguration()
        config.width = max(1, Int(window.frame.width.rounded()))
        config.height = max(1, Int(window.frame.height.rounded()))
        config.showsCursor = false
        config.capturesAudio = false
        let image = try await SCScreenshotManager.captureImage(contentFilter: filter, configuration: config)

        let upright = try VisionTextRecognizer.recognizeBlocks(
            image,
            orientation: .up,
            usesLanguageCorrection: false
        )
        if orientationScore(upright) >= 2 {
            return upright
        }
        let upsideDown = try VisionTextRecognizer.recognizeBlocks(
            image,
            orientation: .down,
            usesLanguageCorrection: false
        )
        return orientationScore(upsideDown) > orientationScore(upright) ? upsideDown : upright
    }

    private static func orientationScore(_ blocks: [CaptureOCRBlock]) -> Int {
        let known = ["搜索", "全部", "图片/视频", "表情", "文件", "链接", "筛选条件", "已筛选了"]
        return blocks.reduce(into: 0) { score, block in
            let text = compact(block.text)
            if known.contains(where: { text.contains($0) }) {
                score += 1
            }
        }
    }

    private static func screenPoint(relative: CGPoint, frame: CGRect) -> CGPoint {
        CGPoint(
            x: frame.origin.x + relative.x * frame.width,
            y: frame.origin.y + relative.y * frame.height
        )
    }

    private static func postClick(_ point: CGPoint) {
        let source = CGEventSource(stateID: .hidSystemState)
        CGEvent(
            mouseEventSource: source,
            mouseType: .mouseMoved,
            mouseCursorPosition: point,
            mouseButton: .left
        )?.post(tap: .cghidEventTap)
        usleep(120_000)
        CGEvent(
            mouseEventSource: source,
            mouseType: .leftMouseDown,
            mouseCursorPosition: point,
            mouseButton: .left
        )?.post(tap: .cghidEventTap)
        usleep(60_000)
        CGEvent(
            mouseEventSource: source,
            mouseType: .leftMouseUp,
            mouseCursorPosition: point,
            mouseButton: .left
        )?.post(tap: .cghidEventTap)
    }
}
