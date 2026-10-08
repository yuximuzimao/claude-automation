import CoreGraphics
import Foundation

enum PixelDiffError: Error, CustomStringConvertible {
    case sizeMismatch
    case bitmapContextFailed
    case invalidRegion

    var description: String {
        switch self {
        case .sizeMismatch:
            return "Capture frames have different pixel dimensions."
        case .bitmapContextFailed:
            return "Could not render capture frame for MAD comparison."
        case .invalidRegion:
            return "MAD content region did not contain sampleable pixels."
        }
    }
}

enum ScrollStabilityResult {
    case changedAndStable(CGImage, baselineMAD: Double, adjacentMAD: Double)
    case noChange(maxBaselineMAD: Double)
    case uncertain(lastBaselineMAD: Double, lastAdjacentMAD: Double?)
}

struct SparseRGBMAD {
    static func measure(
        _ lhs: CGImage,
        _ rhs: CGImage,
        region: CaptureBBox,
        step: Int = 8
    ) throws -> Double {
        let widthDrift = abs(lhs.width - rhs.width)
        let heightDrift = abs(lhs.height - rhs.height)
        guard widthDrift <= 3, heightDrift <= 3 else {
            throw PixelDiffError.sizeMismatch
        }
        let width = min(lhs.width, rhs.width)
        let height = min(lhs.height, rhs.height)
        let left = try rgbaBytes(lhs, width: width, height: height)
        let right = try rgbaBytes(rhs, width: width, height: height)

        let minX = max(0, Int((region.x * Double(width)).rounded(.down)))
        let maxX = min(width, Int((region.maxX * Double(width)).rounded(.up)))
        let minY = max(0, Int((region.y * Double(height)).rounded(.down)))
        let maxY = min(height, Int((region.maxY * Double(height)).rounded(.up)))
        guard minX < maxX, minY < maxY else {
            throw PixelDiffError.invalidRegion
        }

        var total = 0.0
        var channels = 0
        for y in stride(from: minY, to: maxY, by: max(1, step)) {
            for x in stride(from: minX, to: maxX, by: max(1, step)) {
                let offset = (y * width + x) * 4
                total += Double(abs(Int(left[offset]) - Int(right[offset])))
                total += Double(abs(Int(left[offset + 1]) - Int(right[offset + 1])))
                total += Double(abs(Int(left[offset + 2]) - Int(right[offset + 2])))
                channels += 3
            }
        }
        guard channels > 0 else {
            throw PixelDiffError.invalidRegion
        }
        return total / Double(channels)
    }

    private static func rgbaBytes(
        _ image: CGImage,
        width: Int,
        height: Int
    ) throws -> [UInt8] {
        let bytesPerRow = width * 4
        var bytes = [UInt8](repeating: 0, count: bytesPerRow * height)
        let colorSpace = CGColorSpaceCreateDeviceRGB()
        let bitmapInfo = CGBitmapInfo.byteOrder32Big.rawValue |
            CGImageAlphaInfo.premultipliedLast.rawValue

        let created = bytes.withUnsafeMutableBytes { buffer -> Bool in
            guard let context = CGContext(
                data: buffer.baseAddress,
                width: width,
                height: height,
                bitsPerComponent: 8,
                bytesPerRow: bytesPerRow,
                space: colorSpace,
                bitmapInfo: bitmapInfo
            ) else {
                return false
            }
            context.interpolationQuality = .none
            context.draw(
                image,
                in: CGRect(x: 0, y: 0, width: image.width, height: image.height)
            )
            return true
        }
        guard created else {
            throw PixelDiffError.bitmapContextFailed
        }
        return bytes
    }
}

struct ScrollChangeDetector {
    static let quietThreshold = 0.80
    static let dynamicNoiseThreshold = 2.00
    static let changedThreshold = 3.00
    static let checkpointsMilliseconds = [100, 250, 500, 1000, 1500, 2000]

    static func waitForStableChange(
        baseline: CGImage,
        region: CaptureBBox,
        capture: @escaping () async throws -> CGImage
    ) async throws -> ScrollStabilityResult {
        var previous = baseline
        var previousFingerprint = try VisualFingerprint.make(baseline)
        let baselineFingerprint = previousFingerprint
        var previousCheckpoint = 0
        var everChanged = false
        var allBaselineWithinDynamicNoise = true
        var allBaselineSameViewport = true
        var maxBaselineMAD = 0.0
        var lastBaselineMAD = 0.0
        var lastAdjacentMAD: Double?

        for checkpoint in checkpointsMilliseconds {
            let delta = checkpoint - previousCheckpoint
            try await Task.sleep(nanoseconds: UInt64(delta) * 1_000_000)
            previousCheckpoint = checkpoint

            let current = try await capture()
            let currentFingerprint = try VisualFingerprint.make(current)
            let baselineMAD = try SparseRGBMAD.measure(
                baseline,
                current,
                region: region
            )
            let adjacentMAD = try SparseRGBMAD.measure(
                previous,
                current,
                region: region
            )
            let baselineSameViewport = try VisualFingerprint.sameViewport(
                baselineFingerprint,
                currentFingerprint
            )
            let adjacentSameViewport = try VisualFingerprint.sameViewport(
                previousFingerprint,
                currentFingerprint
            )
            lastBaselineMAD = baselineMAD
            lastAdjacentMAD = adjacentMAD
            maxBaselineMAD = max(maxBaselineMAD, baselineMAD)

            if baselineMAD > dynamicNoiseThreshold {
                allBaselineWithinDynamicNoise = false
            }
            if !baselineSameViewport {
                allBaselineSameViewport = false
            }
            if baselineMAD >= changedThreshold {
                everChanged = true
            }
            let stableNow = adjacentMAD <= quietThreshold ||
                (adjacentMAD <= dynamicNoiseThreshold && adjacentSameViewport)
            if everChanged && baselineMAD >= changedThreshold && stableNow {
                return .changedAndStable(
                    current,
                    baselineMAD: baselineMAD,
                    adjacentMAD: adjacentMAD
                )
            }
            if checkpoint >= 500 &&
                allBaselineWithinDynamicNoise &&
                allBaselineSameViewport {
                return .noChange(maxBaselineMAD: maxBaselineMAD)
            }
            previous = current
            previousFingerprint = currentFingerprint
        }

        return .uncertain(
            lastBaselineMAD: lastBaselineMAD,
            lastAdjacentMAD: lastAdjacentMAD
        )
    }
}
