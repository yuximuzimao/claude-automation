import Foundation

struct SelectHistoryDateArguments {
    let targetDate: String
    let target: QQConversationTarget
    let expectedTitle: String
    let geometry: WindowTargetGeometry

    static func parse(_ args: [String]) throws -> SelectHistoryDateArguments {
        var values: [String: String] = [:]
        var index = 1
        while index < args.count {
            let key = args[index]
            guard key.hasPrefix("--"), index + 1 < args.count else {
                throw SelectHistoryDateCLIError.invalidArguments
            }
            values[key] = args[index + 1]
            index += 2
        }
        guard
            let targetDate = values["--date"], !targetDate.isEmpty,
            let groupKey = values["--group-key"], !groupKey.isEmpty,
            let conversationPrefix = values["--conversation-prefix"], !conversationPrefix.isEmpty,
            let headerContains = values["--header-contains"], !headerContains.isEmpty,
            let expectedTitle = values["--expected-title"], !expectedTitle.isEmpty,
            let x = values["--window-x"].flatMap(Double.init),
            let y = values["--window-y"].flatMap(Double.init),
            let width = values["--window-width"].flatMap(Double.init), width > 100,
            let height = values["--window-height"].flatMap(Double.init), height > 100
        else {
            throw SelectHistoryDateCLIError.invalidArguments
        }
        return SelectHistoryDateArguments(
            targetDate: targetDate,
            target: QQConversationTarget(
                groupKey: groupKey,
                conversationPrefix: conversationPrefix,
                headerContains: headerContains,
                expectedHistoryTitle: expectedTitle
            ),
            expectedTitle: expectedTitle,
            geometry: WindowTargetGeometry(x: x, y: y, width: width, height: height)
        )
    }
}

enum SelectHistoryDateCLIError: Error, CustomStringConvertible {
    case invalidArguments

    var description: String {
        "Usage: select-history-date --date YYYY-MM-DD --group-key <key> --conversation-prefix <text> --header-contains <text> --expected-title <exact title> --window-x <x> --window-y <y> --window-width <w> --window-height <h>"
    }
}

@main
struct SelectHistoryDateMain {
    @MainActor
    private static func select(_ args: SelectHistoryDateArguments) async throws -> HistoryDateSelectionResult {
        try await HistoryDateSelector.select(
            targetText: args.targetDate,
            expectedTitle: args.expectedTitle,
            geometry: args.geometry
        )
    }

    static func main() async {
        do {
            let args = try SelectHistoryDateArguments.parse(CommandLine.arguments)
            let result: HistoryDateSelectionResult
            do {
                result = try await select(args)
            } catch let error as WindowPreparationError {
                switch error {
                case .exactWindowNotFound, .sckWindowNotFound:
                    try await QQConversationSwitcher.openHistory(args.target)
                    result = try await select(args)
                default:
                    throw error
                }
            }
            print(
                "DATE_SELECTED target=\(result.target) row=\(result.row) column=\(result.column) month_steps=\(result.monthSteps)"
            )
        } catch {
            fputs("ERROR \(error)\n", stderr)
            exit(1)
        }
    }
}
