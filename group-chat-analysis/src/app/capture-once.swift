import Foundation

struct CaptureOnceArguments {
    let groupKey: String
    let expectedTitle: String
    let batchID: String
    let pageIndex: Int
    let outputPath: String

    static func parse(_ args: [String]) throws -> CaptureOnceArguments {
        var values: [String: String] = [:]
        var i = 1
        while i < args.count {
            let key = args[i]
            guard key.hasPrefix("--"), i + 1 < args.count else {
                throw CaptureOnceCLIError.invalidArguments
            }
            values[key] = args[i + 1]
            i += 2
        }

        guard
            let groupKey = values["--group-key"], !groupKey.isEmpty,
            let expectedTitle = values["--expected-title"], !expectedTitle.isEmpty,
            let batchID = values["--batch-id"], !batchID.isEmpty,
            let pageRaw = values["--page-index"],
            let pageIndex = Int(pageRaw), pageIndex >= 0
        else {
            throw CaptureOnceCLIError.invalidArguments
        }

        let outputPath = values["--output"]
            ?? "runtime/raw/\(batchID)/page-\(String(format: "%06d", pageIndex)).json"

        return CaptureOnceArguments(
            groupKey: groupKey,
            expectedTitle: expectedTitle,
            batchID: batchID,
            pageIndex: pageIndex,
            outputPath: outputPath
        )
    }
}

enum CaptureOnceCLIError: Error, CustomStringConvertible {
    case invalidArguments

    var description: String {
        "Usage: capture-once --group-key <key> --expected-title <QQ history window title> --batch-id <id> --page-index <n> [--output <path>]"
    }
}

@main
struct CaptureOnceMain {
    static func main() async {
        do {
            let args = try CaptureOnceArguments.parse(CommandLine.arguments)
            try await QQHistoryCapture.activateQQForSession()
            try await QQHistoryCapture.prepareHistoryWindow(expectedTitle: args.expectedTitle)
            let page = try await QQHistoryCapture.capturePage(
                groupKey: args.groupKey,
                expectedTitle: args.expectedTitle,
                batchID: args.batchID,
                pageIndex: args.pageIndex
            )
            try writeRawPageAtomically(page, to: args.outputPath)
            print("OK output=\(args.outputPath) blocks=\(page.blocks.count) window_id=\(page.window.windowID)")
        } catch {
            fputs("ERROR \(error)\n", stderr)
            exit(1)
        }
    }
}
