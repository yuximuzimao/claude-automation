import Foundation

struct CapturePagesArguments {
    let groupKey: String
    let expectedTitle: String
    let batchID: String
    let pageCount: Int
    let outputDirectory: String
    let geometry: WindowTargetGeometry
    let scrollPixels: Int

    static func parse(_ args: [String]) throws -> CapturePagesArguments {
        var values: [String: String] = [:]
        var index = 1
        while index < args.count {
            let key = args[index]
            guard key.hasPrefix("--"), index + 1 < args.count else {
                throw CapturePagesCLIError.invalidArguments
            }
            values[key] = args[index + 1]
            index += 2
        }

        guard
            let groupKey = values["--group-key"], !groupKey.isEmpty,
            let expectedTitle = values["--expected-title"], !expectedTitle.isEmpty,
            let batchID = values["--batch-id"], !batchID.isEmpty,
            let pageRaw = values["--pages"],
            let pageCount = Int(pageRaw), pageCount >= 1,
            let x = values["--window-x"].flatMap(Double.init),
            let y = values["--window-y"].flatMap(Double.init),
            let width = values["--window-width"].flatMap(Double.init), width > 100,
            let height = values["--window-height"].flatMap(Double.init), height > 100
        else {
            throw CapturePagesCLIError.invalidArguments
        }

        let scrollPixels = values["--scroll-pixels"].flatMap(Int.init) ?? 630
        guard scrollPixels > 0 else {
            throw CapturePagesCLIError.invalidArguments
        }

        return CapturePagesArguments(
            groupKey: groupKey,
            expectedTitle: expectedTitle,
            batchID: batchID,
            pageCount: pageCount,
            outputDirectory: values["--output-dir"] ?? "runtime/raw/\(batchID)",
            geometry: WindowTargetGeometry(
                x: x,
                y: y,
                width: width,
                height: height
            ),
            scrollPixels: scrollPixels
        )
    }
}

enum CapturePagesCLIError: Error, CustomStringConvertible {
    case invalidArguments
    case scrollNoChange(Double)
    case scrollUncertain(Double, Double?)

    var description: String {
        switch self {
        case .invalidArguments:
            return "Usage: capture-pages --group-key <key> --expected-title <exact QQ history title> --batch-id <id> --pages <count> --window-x <x> --window-y <y> --window-width <width> --window-height <height> [--scroll-pixels <pixels>] [--output-dir <path>]"
        case let .scrollNoChange(mad):
            return "Scroll produced no confirmed content change (max baseline MAD=\(format(mad))). Capture stopped incomplete."
        case let .scrollUncertain(baseline, adjacent):
            return "Scroll stability remained uncertain (baseline MAD=\(format(baseline)), adjacent MAD=\(adjacent.map(format) ?? "n/a")). Capture stopped incomplete."
        }
    }

    private func format(_ value: Double) -> String {
        String(format: "%.4f", value)
    }
}

private func pagePath(directory: String, index: Int) -> String {
    URL(fileURLWithPath: directory)
        .appendingPathComponent("page-\(String(format: "%06d", index)).json")
        .path
}

@main
struct CapturePagesMain {
    static func main() async {
        do {
            let args = try CapturePagesArguments.parse(CommandLine.arguments)
            try await QQWindowPreparer.prepare(
                expectedTitle: args.expectedTitle,
                geometry: args.geometry
            )

            var current = try await QQHistoryCapture.capturePage(
                groupKey: args.groupKey,
                expectedTitle: args.expectedTitle,
                batchID: args.batchID,
                pageIndex: 0
            )
            try writeRawPageAtomically(
                current.record,
                to: pagePath(directory: args.outputDirectory, index: 0)
            )
            print(
                "PAGE 0 OK blocks=\(current.record.blocks.count) " +
                "content_region=\(current.record.contentRegion)"
            )

            if args.pageCount > 1 {
                for pageIndex in 1..<args.pageCount {
                    let (next, result) = try await QQHistoryCapture.capturePageAfterStableScroll(
                        groupKey: args.groupKey,
                        expectedTitle: args.expectedTitle,
                        batchID: args.batchID,
                        pageIndex: pageIndex,
                        previousPage: current,
                        scrollPixels: args.scrollPixels
                    )

                    switch result {
                    case let .changedAndStable(baselineMAD, adjacentMAD):
                        guard let next else {
                            throw QQHistoryCaptureError.captureFailed
                        }
                        try writeRawPageAtomically(
                            next.record,
                            to: pagePath(directory: args.outputDirectory, index: pageIndex)
                        )
                        print(
                            "PAGE \(pageIndex) OK blocks=\(next.record.blocks.count) " +
                            "baseline_mad=\(String(format: "%.4f", baselineMAD)) " +
                            "adjacent_mad=\(String(format: "%.4f", adjacentMAD))"
                        )
                        current = next
                    case let .noChange(maxBaselineMAD):
                        throw CapturePagesCLIError.scrollNoChange(maxBaselineMAD)
                    case let .uncertain(lastBaselineMAD, lastAdjacentMAD):
                        throw CapturePagesCLIError.scrollUncertain(
                            lastBaselineMAD,
                            lastAdjacentMAD
                        )
                    }
                }
            }

            print("DONE pages=\(args.pageCount)")
        } catch {
            fputs("ERROR \(error)\n", stderr)
            exit(1)
        }
    }
}
