import Foundation

struct CaptureStepArguments {
    let mode: String
    let groupKey: String
    let expectedTitle: String
    let batchID: String
    let pageIndex: Int
    let outputPath: String
    let previousRawPath: String?
    let geometry: WindowTargetGeometry
    let scrollPixels: Int

    static func parse(_ args: [String]) throws -> CaptureStepArguments {
        var values: [String: String] = [:]
        var index = 1
        while index < args.count {
            let key = args[index]
            guard key.hasPrefix("--"), index + 1 < args.count else {
                throw CaptureStepCLIError.invalidArguments
            }
            values[key] = args[index + 1]
            index += 2
        }

        guard
            let mode = values["--mode"], ["current", "scroll"].contains(mode),
            let groupKey = values["--group-key"], !groupKey.isEmpty,
            let expectedTitle = values["--expected-title"], !expectedTitle.isEmpty,
            let batchID = values["--batch-id"], !batchID.isEmpty,
            let pageIndex = values["--page-index"].flatMap(Int.init), pageIndex >= 0,
            let outputPath = values["--output"], !outputPath.isEmpty,
            let x = values["--window-x"].flatMap(Double.init),
            let y = values["--window-y"].flatMap(Double.init),
            let width = values["--window-width"].flatMap(Double.init), width > 100,
            let height = values["--window-height"].flatMap(Double.init), height > 100
        else {
            throw CaptureStepCLIError.invalidArguments
        }

        let previousRawPath = values["--previous-raw"]
        if mode == "scroll" && previousRawPath == nil {
            throw CaptureStepCLIError.previousRawRequired
        }
        let scrollPixels = values["--scroll-pixels"].flatMap(Int.init) ?? 630
        guard scrollPixels > 0 else {
            throw CaptureStepCLIError.invalidArguments
        }

        return CaptureStepArguments(
            mode: mode,
            groupKey: groupKey,
            expectedTitle: expectedTitle,
            batchID: batchID,
            pageIndex: pageIndex,
            outputPath: outputPath,
            previousRawPath: previousRawPath,
            geometry: WindowTargetGeometry(x: x, y: y, width: width, height: height),
            scrollPixels: scrollPixels
        )
    }
}

enum CaptureStepCLIError: Error, CustomStringConvertible {
    case invalidArguments
    case previousRawRequired
    case previousRawMismatch(String)
    case scrollNoChange(Double)
    case scrollUncertain(Double, Double?)

    var description: String {
        switch self {
        case .invalidArguments:
            return "Invalid capture-step arguments."
        case .previousRawRequired:
            return "--previous-raw is required for scroll mode."
        case let .previousRawMismatch(reason):
            return "Previous raw page is not the expected durable predecessor: \(reason)"
        case let .scrollNoChange(mad):
            return "Scroll produced no confirmed change (max baseline MAD=\(String(format: "%.4f", mad)))."
        case let .scrollUncertain(baseline, adjacent):
            return "Scroll stability uncertain (baseline=\(String(format: "%.4f", baseline)), adjacent=\(adjacent.map { String(format: "%.4f", $0) } ?? "n/a"))."
        }
    }
}

private func loadPreviousPage(_ args: CaptureStepArguments) throws -> RawCapturePage {
    guard let path = args.previousRawPath else {
        throw CaptureStepCLIError.previousRawRequired
    }
    let data = try Data(contentsOf: URL(fileURLWithPath: path))
    let page = try JSONDecoder().decode(RawCapturePage.self, from: data)
    guard page.schemaVersion == "2" else {
        throw CaptureStepCLIError.previousRawMismatch("schema_version")
    }
    guard page.batchID == args.batchID else {
        throw CaptureStepCLIError.previousRawMismatch("batch_id")
    }
    guard page.groupKey == args.groupKey else {
        throw CaptureStepCLIError.previousRawMismatch("group_key")
    }
    guard page.pageIndex == args.pageIndex - 1 else {
        throw CaptureStepCLIError.previousRawMismatch("page_index")
    }
    return page
}

@main
struct CaptureStepMain {
    static func main() async {
        do {
            let args = try CaptureStepArguments.parse(CommandLine.arguments)
            try await QQWindowPreparer.prepare(
                expectedTitle: args.expectedTitle,
                geometry: args.geometry
            )

            let page: CapturedPage
            if args.mode == "current" {
                page = try await QQHistoryCapture.capturePage(
                    groupKey: args.groupKey,
                    expectedTitle: args.expectedTitle,
                    batchID: args.batchID,
                    pageIndex: args.pageIndex
                )
            } else {
                let previousRecord = try loadPreviousPage(args)
                let target = try await QQHistoryCapture.validatedHistoryWindow(
                    expectedTitle: args.expectedTitle
                )
                let previous = CapturedPage(
                    record: previousRecord,
                    windowID: target.windowID
                )
                let (next, result) = try await QQHistoryCapture.capturePageAfterStableScroll(
                    groupKey: args.groupKey,
                    expectedTitle: args.expectedTitle,
                    batchID: args.batchID,
                    pageIndex: args.pageIndex,
                    previousPage: previous,
                    scrollPixels: args.scrollPixels
                )
                switch result {
                case .changedAndStable:
                    guard let next else {
                        throw QQHistoryCaptureError.captureFailed
                    }
                    page = next
                case let .noChange(maxBaselineMAD):
                    throw CaptureStepCLIError.scrollNoChange(maxBaselineMAD)
                case let .uncertain(lastBaselineMAD, lastAdjacentMAD):
                    throw CaptureStepCLIError.scrollUncertain(
                        lastBaselineMAD,
                        lastAdjacentMAD
                    )
                }
            }

            try writeRawPageAtomically(page.record, to: args.outputPath)
            print(
                "CAPTURED page=\(page.record.pageIndex) fingerprint=\(page.record.visualFingerprint) blocks=\(page.record.blocks.count)"
            )
        } catch let error as CaptureStepCLIError {
            switch error {
            case let .scrollNoChange(maxBaselineMAD):
                print("NO_CHANGE max_baseline_mad=\(String(format: "%.4f", maxBaselineMAD))")
                exit(10)
            default:
                fputs("ERROR \(error)\n", stderr)
                exit(1)
            }
        } catch {
            fputs("ERROR \(error)\n", stderr)
            exit(1)
        }
    }
}
