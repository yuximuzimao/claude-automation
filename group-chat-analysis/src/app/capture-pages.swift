import AppKit
import Foundation

struct CapturePagesArguments {
    let groupKey: String
    let expectedTitle: String
    let batchID: String
    let pageCount: Int
    let outputDirectory: String

    static func parse(_ args: [String]) throws -> CapturePagesArguments {
        var values: [String: String] = [:]
        var i = 1
        while i < args.count {
            let key = args[i]
            guard key.hasPrefix("--"), i + 1 < args.count else {
                throw CapturePagesCLIError.invalidArguments
            }
            values[key] = args[i + 1]
            i += 2
        }

        guard
            let groupKey = values["--group-key"], !groupKey.isEmpty,
            let expectedTitle = values["--expected-title"], !expectedTitle.isEmpty,
            let batchID = values["--batch-id"], !batchID.isEmpty,
            let countRaw = values["--pages"],
            let pageCount = Int(countRaw), pageCount >= 1
        else {
            throw CapturePagesCLIError.invalidArguments
        }

        return CapturePagesArguments(
            groupKey: groupKey,
            expectedTitle: expectedTitle,
            batchID: batchID,
            pageCount: pageCount,
            outputDirectory: values["--output-dir"] ?? "runtime/raw/\(batchID)"
        )
    }
}

enum CapturePagesCLIError: Error, CustomStringConvertible {
    case invalidArguments

    var description: String {
        "Usage: capture-pages --group-key <key> --expected-title <QQ history window title> --batch-id <id> --pages <count> [--output-dir <path>]"
    }
}

func signalUser(title: String, message: String) {
    NSSound.beep()

    let script = "display notification " +
        String(reflecting: message) +
        " with title " +
        String(reflecting: title)

    let process = Process()
    process.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
    process.arguments = ["-e", script]
    try? process.run()
}

@main
struct CapturePagesMain {
    static func main() async {
        let title = "群聊分析"

        do {
            let args = try CapturePagesArguments.parse(CommandLine.arguments)
            try await QQHistoryCapture.activateQQForSession()
            try await QQHistoryCapture.prepareHistoryWindow(expectedTitle: args.expectedTitle)

            signalUser(
                title: title,
                message: "开始采集，请保持 QQ 聊天记录窗口在前台。"
            )

            for pageIndex in 0..<args.pageCount {
                let page = try await QQHistoryCapture.capturePage(
                    groupKey: args.groupKey,
                    expectedTitle: args.expectedTitle,
                    batchID: args.batchID,
                    pageIndex: pageIndex
                )

                let path = URL(fileURLWithPath: args.outputDirectory)
                    .appendingPathComponent(
                        "page-\(String(format: "%06d", pageIndex)).json"
                    )
                    .path

                try writeRawPageAtomically(page, to: path)
                print(
                    "PAGE \(pageIndex) OK blocks=\(page.blocks.count) " +
                    "window=\(page.window.width)x\(page.window.height)"
                )

                if pageIndex + 1 < args.pageCount {
                    let delta = try await QQHistoryCapture.scrollTowardHistory(
                        expectedTitle: args.expectedTitle,
                        page: page
                    )
                    print("SCROLL toward_history delta=\(delta)")
                }
            }

            signalUser(
                title: title,
                message: "采集完成，可以切换到其它应用。"
            )
            print("DONE pages=\(args.pageCount)")
        } catch {
            signalUser(
                title: title,
                message: "采集已停止，可以操作电脑。"
            )
            fputs("ERROR \(error)\n", stderr)
            exit(1)
        }
    }
}
