import CoreGraphics
import Foundation

enum VisualFingerprintError: Error, CustomStringConvertible {
    case renderFailed
    case invalidFingerprint

    var description: String {
        switch self {
        case .renderFailed:
            return "Could not render image for visual fingerprint."
        case .invalidFingerprint:
            return "visual fingerprint must use dhash512:<128 hex chars>."
        }
    }
}

struct VisualFingerprint {
    static let prefix = "dhash512:"
    static let wordCount = 8
    // Kept deliberately conservative; calibrated again whenever QQ rendering or
    // display scaling changes. Same-view noise must stay well below this value,
    // while adjacent real pages must remain comfortably above it.
    static let sameViewportMaximumDistance = 20

    static func make(_ image: CGImage) throws -> String {
        let width = 33
        let height = 16
        var pixels = [UInt8](repeating: 0, count: width * height)
        let colorSpace = CGColorSpaceCreateDeviceGray()
        let rendered = pixels.withUnsafeMutableBytes { buffer -> Bool in
            guard let context = CGContext(
                data: buffer.baseAddress,
                width: width,
                height: height,
                bitsPerComponent: 8,
                bytesPerRow: width,
                space: colorSpace,
                bitmapInfo: CGImageAlphaInfo.none.rawValue
            ) else {
                return false
            }
            context.interpolationQuality = .medium
            context.draw(image, in: CGRect(x: 0, y: 0, width: width, height: height))
            return true
        }
        guard rendered else {
            throw VisualFingerprintError.renderFailed
        }

        var words = [UInt64](repeating: 0, count: wordCount)
        var bitIndex = 0
        for y in 0..<height {
            let row = y * width
            for x in 0..<(width - 1) {
                if pixels[row + x] > pixels[row + x + 1] {
                    let word = bitIndex / 64
                    let shift = 63 - (bitIndex % 64)
                    words[word] |= UInt64(1) << UInt64(shift)
                }
                bitIndex += 1
            }
        }
        return prefix + words.map { String(format: "%016llx", $0) }.joined()
    }

    static func distance(_ left: String, _ right: String) throws -> Int {
        let lhs = try parse(left)
        let rhs = try parse(right)
        return zip(lhs, rhs).reduce(0) { partial, pair in
            partial + (pair.0 ^ pair.1).nonzeroBitCount
        }
    }

    static func sameViewport(_ left: String, _ right: String) throws -> Bool {
        try distance(left, right) <= sameViewportMaximumDistance
    }

    private static func parse(_ value: String) throws -> [UInt64] {
        guard value.hasPrefix(prefix) else {
            throw VisualFingerprintError.invalidFingerprint
        }
        let hex = String(value.dropFirst(prefix.count))
        guard hex.count == wordCount * 16 else {
            throw VisualFingerprintError.invalidFingerprint
        }
        var words: [UInt64] = []
        for index in 0..<wordCount {
            let start = hex.index(hex.startIndex, offsetBy: index * 16)
            let end = hex.index(start, offsetBy: 16)
            guard let word = UInt64(hex[start..<end], radix: 16) else {
                throw VisualFingerprintError.invalidFingerprint
            }
            words.append(word)
        }
        return words
    }
}
