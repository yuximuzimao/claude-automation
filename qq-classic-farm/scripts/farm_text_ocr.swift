// Local-only OCR for small verified UI crops. No app activation or input.
import Foundation
import ImageIO
import Vision

guard CommandLine.arguments.count == 2 else {
    fputs("usage: farm_text_ocr <crop.png>\n", stderr)
    exit(2)
}
let url = URL(fileURLWithPath: CommandLine.arguments[1])
guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
      let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
    fputs("Cannot load crop image\n", stderr)
    exit(2)
}
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false
request.recognitionLanguages = ["en-US"]
request.minimumTextHeight = 0.08
do {
    try VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
    let rows: [[String: Any]] = (request.results ?? []).compactMap { observation in
        guard let candidate = observation.topCandidates(1).first else { return nil }
        return ["text": candidate.string, "confidence": Double(candidate.confidence),
                "x": Double(observation.boundingBox.minX),
                "y": Double(observation.boundingBox.minY)]
    }
    let data = try JSONSerialization.data(withJSONObject: ["observations": rows],
                                          options: [.sortedKeys])
    print(String(decoding: data, as: UTF8.self))
} catch {
    fputs("OCR failed: \(error)\n", stderr)
    exit(2)
}
