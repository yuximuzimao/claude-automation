import Foundation

enum ContentRegionError: Error, CustomStringConvertible {
    case toolbarNotFound
    case invalidRegion

    var description: String {
        switch self {
        case .toolbarNotFound:
            return "Could not locate the QQ history toolbar from OCR blocks."
        case .invalidRegion:
            return "Derived QQ history content region is invalid."
        }
    }
}

struct ContentRegionLocator {
    private static let toolbarTokens = ["全部", "图片/视频", "表情", "文件", "链接", "筛选"]
    private static let topMargin = 0.012
    private static let rightMargin = 0.018
    private static let fallbackRightEdge = 0.92
    private static let bottomEdge = 0.02

    static func locate(from blocks: [CaptureOCRBlock]) throws -> CaptureBBox {
        let toolbar = blocks.filter { isToolbarText($0.text) }
        guard toolbar.count >= 2 else {
            throw ContentRegionError.toolbarNotFound
        }

        // Vision coordinates use a bottom-left origin. The message stream sits
        // below the filter toolbar, so the toolbar's lowest observed edge is a
        // dynamic upper bound for content.
        let toolbarBottom = toolbar.map(\.bbox.y).min() ?? 1.0
        let top = toolbarBottom - topMargin

        let rightControl = toolbar
            .filter { compact($0.text).contains("筛选") }
            .map(\.bbox.x)
            .min()
        let right = min(0.98, (rightControl ?? fallbackRightEdge) - (rightControl == nil ? 0.0 : rightMargin))

        guard top > bottomEdge + 0.10, right > 0.50 else {
            throw ContentRegionError.invalidRegion
        }

        return CaptureBBox(
            x: 0.0,
            y: bottomEdge,
            width: right,
            height: top - bottomEdge
        )
    }

    static func isToolbarText(_ text: String) -> Bool {
        let value = compact(text)
        if value.contains("搜索") || (value.contains("搜") && value.count <= 5) {
            return true
        }
        return toolbarTokens.contains { value.contains($0) }
    }

    static func isTimeOnly(_ text: String) -> Bool {
        text.range(
            of: #"^\s*[•.]?\s*\d{1,2}:\d{2}\s*$"#,
            options: .regularExpression
        ) != nil
    }

    static func isDateSeparator(_ text: String) -> Bool {
        text.range(
            of: #"^\s*\d{4}[/-]\d{1,2}[/-]\d{1,2}\s*$"#,
            options: .regularExpression
        ) != nil
    }

    private static func compact(_ text: String) -> String {
        text.replacingOccurrences(of: " ", with: "")
            .replacingOccurrences(of: "\n", with: "")
    }
}
