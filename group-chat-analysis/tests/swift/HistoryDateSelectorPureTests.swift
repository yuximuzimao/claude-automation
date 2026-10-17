import Foundation

private enum TestFailure: Error, CustomStringConvertible {
    case failed(String)
    var description: String { switch self { case let .failed(message): return message } }
}

private func expect(_ condition: @autoclosure () -> Bool, _ message: String) throws {
    if !condition() { throw TestFailure.failed(message) }
}

@main
struct HistoryDateSelectorPureTestsMain {
    static func main() {
        do {
            guard let octoberFirst = HistoryDateSelector.parseTargetDate("2026-10-01") else {
                throw TestFailure.failed("valid date should parse")
            }
            let octoberCell = HistoryDateSelector.calendarCell(octoberFirst)
            try expect(octoberCell.row == 0 && octoberCell.column == 4, "2026-10-01 should be Thursday in row 0")

            guard let september27 = HistoryDateSelector.parseTargetDate("2026-09-27") else {
                throw TestFailure.failed("valid September date should parse")
            }
            let septemberCell = HistoryDateSelector.calendarCell(september27)
            try expect(septemberCell.row == 4 && septemberCell.column == 0, "2026-09-27 should be Sunday in row 4")

            try expect(HistoryDateSelector.parseTargetDate("2026-02-30") == nil, "impossible dates must be rejected")
            try expect(
                HistoryDateSelector.monthsBetween(
                    .init(year: 2026, month: 9),
                    .init(year: 2026, month: 10)
                ) == 1,
                "September to October should be one month"
            )
            try expect(
                HistoryDateSelector.monthsBetween(
                    .init(year: 2026, month: 1),
                    .init(year: 2025, month: 12)
                ) == -1,
                "cross-year previous month should be negative one"
            )
            print("HistoryDateSelectorPureTests OK")
        } catch {
            fputs("HistoryDateSelectorPureTests FAILED: \(error)\n", stderr)
            exit(1)
        }
    }
}
