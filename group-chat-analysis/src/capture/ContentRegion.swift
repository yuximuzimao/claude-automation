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
        let filterCandidates = blocks.filter { isFilterToolbarText($0.text) }
        let toolbar = bestToolbarRow(from: filterCandidates)
        guard toolbar.count >= 2 else {
            throw ContentRegionError.toolbarNotFound
        }

        // Vision coordinates use a bottom-left origin. Toolbar words may also
        // appear inside chat text (for example a message containing “表情”).
        // Only a co-linear row of at least two filter controls may define the
        // upper content boundary; isolated keyword hits are never sufficient.
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
        return isFilterToolbarText(text)
    }

    private static func isFilterToolbarText(_ text: String) -> Bool {
        let value = compact(text)
        return toolbarTokens.contains { value.contains($0) }
    }

    private static func bestToolbarRow(from candidates: [CaptureOCRBlock]) -> [CaptureOCRBlock] {
        let rowTolerance = 0.035
        var best: [CaptureOCRBlock] = []
        var bestMidY = -Double.infinity

        for anchor in candidates {
            let anchorMidY = anchor.bbox.y + anchor.bbox.height / 2.0
            var row: [CaptureOCRBlock] = []
            var midYTotal = 0.0
            for candidate in candidates {
                let candidateMidY = candidate.bbox.y + candidate.bbox.height / 2.0
                if Swift.abs(candidateMidY - anchorMidY) <= rowTolerance {
                    row.append(candidate)
                    midYTotal += candidateMidY
                }
            }
            let midY = midYTotal / Double(max(1, row.count))
            if row.count > best.count || (row.count == best.count && midY > bestMidY) {
                best = row
                bestMidY = midY
            }
        }
        return best
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
