import CoreGraphics
import Foundation

struct CaptureBBox: Codable, Equatable {
    let x: Double
    let y: Double
    let width: Double
    let height: Double

    var maxX: Double { x + width }
    var maxY: Double { y + height }

    func contains(midX: Double, midY: Double) -> Bool {
        midX >= x && midX <= maxX && midY >= y && midY <= maxY
    }
}

struct CaptureOCRBlock: Codable, Equatable {
    let blockIndex: Int
    let text: String
    let bbox: CaptureBBox
    let confidence: Double

    enum CodingKeys: String, CodingKey {
        case blockIndex = "block_index"
        case text
        case bbox
        case confidence
    }
}

struct CaptureScreenFrame: Codable, Equatable {
    let x: Double
    let y: Double
    let width: Double
    let height: Double
}

struct CapturePixelSize: Codable, Equatable {
    let width: Int
    let height: Int
}

struct CaptureWindowInfo: Codable, Equatable {
    let title: String
    let framePoints: CaptureScreenFrame
    let captureSizePixels: CapturePixelSize

    enum CodingKeys: String, CodingKey {
        case title
        case framePoints = "frame_points"
        case captureSizePixels = "capture_size_pixels"
    }
}

struct RawCapturePage: Codable, Equatable {
    let schemaVersion: String
    let visualFingerprint: String
    let batchID: String
    let groupKey: String
    let groupDisplay: String?
    let pageIndex: Int
    let capturedAt: String
    let source: String
    let window: CaptureWindowInfo
    let contentRegion: CaptureBBox
    let blocks: [CaptureOCRBlock]

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version"
        case visualFingerprint = "visual_fingerprint"
        case batchID = "batch_id"
        case groupKey = "group_key"
        case groupDisplay = "group_display"
        case pageIndex = "page_index"
        case capturedAt = "captured_at"
        case source
        case window
        case contentRegion = "content_region"
        case blocks
    }
}

struct WindowTargetGeometry: Equatable {
    let x: Double
    let y: Double
    let width: Double
    let height: Double
}
