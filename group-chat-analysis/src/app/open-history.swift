import Foundation

struct OpenHistoryArguments {
    let target: QQConversationTarget

    static func parse(_ args: [String]) throws -> OpenHistoryArguments {
        var values: [String: String] = [:]
        var index = 1
        while index < args.count {
            let key = args[index]
            guard key.hasPrefix("--"), index + 1 < args.count else {
                throw OpenHistoryCLIError.invalidArguments
            }
            values[key] = args[index + 1]
            index += 2
        }
        guard
            let groupKey = values["--group-key"], !groupKey.isEmpty,
            let conversationPrefix = values["--conversation-prefix"], !conversationPrefix.isEmpty,
            let headerContains = values["--header-contains"], !headerContains.isEmpty,
            let expectedHistoryTitle = values["--expected-history-title"], !expectedHistoryTitle.isEmpty
        else {
            throw OpenHistoryCLIError.invalidArguments
        }
        return OpenHistoryArguments(
            target: QQConversationTarget(
                groupKey: groupKey,
                conversationPrefix: conversationPrefix,
                headerContains: headerContains,
                expectedHistoryTitle: expectedHistoryTitle
            )
        )
    }
}

enum OpenHistoryCLIError: Error, CustomStringConvertible {
    case invalidArguments

    var description: String {
        "Usage: open-history --group-key <key> --conversation-prefix <visible unique prefix> --header-contains <selected-header text> --expected-history-title <exact title>"
    }
}

@main
struct OpenHistoryMain {
    static func main() async {
        do {
            let args = try OpenHistoryArguments.parse(CommandLine.arguments)
            try await QQConversationSwitcher.openHistory(args.target)
            print("HISTORY_READY group=\(args.target.groupKey) title=\(args.target.expectedHistoryTitle)")
        } catch {
            fputs("ERROR \(error)\n", stderr)
            exit(1)
        }
    }
}
