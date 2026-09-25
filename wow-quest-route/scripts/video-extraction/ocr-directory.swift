import Foundation
import Vision
import AppKit

let args = CommandLine.arguments
if args.count < 3 { fatalError("usage: ocr-directory.swift <input-dir> <output-file>") }
let inputDir = URL(fileURLWithPath: args[1], isDirectory: true)
let outputURL = URL(fileURLWithPath: args[2])
let fm = FileManager.default
let files = try fm.contentsOfDirectory(at: inputDir, includingPropertiesForKeys: nil)
    .filter { $0.pathExtension.lowercased() == "png" }
    .sorted { $0.lastPathComponent < $1.lastPathComponent }
var output = ""
var processed = 0
for url in files {
    autoreleasepool {
        guard let image = NSImage(contentsOf: url),
              let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else { return }
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = false
        request.recognitionLanguages = ["zh-Hans", "en-US"]
        let handler = VNImageRequestHandler(cgImage: cgImage)
        do {
            try handler.perform([request])
            output += "\n=== \(url.lastPathComponent) ===\n"
            for observation in request.results ?? [] {
                guard let candidate = observation.topCandidates(1).first else { continue }
                let box = observation.boundingBox
                output += String(format: "%.4f %.4f %.4f %.4f\t%@\n", box.origin.x, box.origin.y, box.size.width, box.size.height, candidate.string)
            }
            processed += 1
        } catch {
            output += "\n=== \(url.lastPathComponent) ERROR \(error) ===\n"
        }
    }
}
try output.write(to: outputURL, atomically: true, encoding: .utf8)
print("processed=\(processed) output=\(outputURL.path)")
