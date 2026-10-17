import CoreGraphics
import Foundation
import ImageIO
import Vision

enum VisionTextRecognizer {
    static func recognizeBlocks(
        _ image: CGImage,
        orientation: CGImagePropertyOrientation = .up,
        usesLanguageCorrection: Bool = true,
        regionOfInterest: CGRect? = nil,
        minimumTextHeight: Float? = nil
    ) throws -> [CaptureOCRBlock] {
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.recognitionLanguages = ["zh-Hans", "en-US"]
        request.usesLanguageCorrection = usesLanguageCorrection
        if let regionOfInterest {
            request.regionOfInterest = regionOfInterest
        }
        if let minimumTextHeight {
            request.minimumTextHeight = minimumTextHeight
        }

        let handler = VNImageRequestHandler(
            cgImage: image,
            orientation: orientation,
            options: [:]
        )
        try handler.perform([request])

        return (request.results ?? []).enumerated().compactMap { index, observation in
            guard let candidate = observation.topCandidates(1).first else {
                return nil
            }
            let text = candidate.string
            guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
                return nil
            }
            return CaptureOCRBlock(
                blockIndex: index,
                text: text,
                bbox: displayBBox(for: observation.boundingBox, orientation: orientation),
                confidence: Double(candidate.confidence)
            )
        }
    }

    static func recognizeStrings(
        _ image: CGImage,
        orientation: CGImagePropertyOrientation = .up,
        usesLanguageCorrection: Bool = true,
        regionOfInterest: CGRect? = nil,
        minimumTextHeight: Float? = nil
    ) throws -> [String] {
        try recognizeBlocks(
            image,
            orientation: orientation,
            usesLanguageCorrection: usesLanguageCorrection,
            regionOfInterest: regionOfInterest,
            minimumTextHeight: minimumTextHeight
        ).map(\.text)
    }

    static func displayBBox(
        for box: CGRect,
        orientation: CGImagePropertyOrientation
    ) -> CaptureBBox {
        if orientation == .down {
            return CaptureBBox(
                x: 1.0 - box.origin.x - box.size.width,
                y: 1.0 - box.origin.y - box.size.height,
                width: box.size.width,
                height: box.size.height
            )
        }
        return CaptureBBox(
            x: box.origin.x,
            y: box.origin.y,
            width: box.size.width,
            height: box.size.height
        )
    }
}
