import Foundation
import Vision
import AppKit

let args = CommandLine.arguments
if args.count < 2 { fatalError("usage: ocr-image.swift <image>") }
let url = URL(fileURLWithPath: args[1])
guard let image = NSImage(contentsOf: url),
      let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
  fatalError("cannot load image")
}
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false
request.recognitionLanguages = ["zh-Hans", "en-US"]
let handler = VNImageRequestHandler(cgImage: cgImage)
try handler.perform([request])
for observation in request.results ?? [] {
  guard let candidate = observation.topCandidates(1).first else { continue }
  let box = observation.boundingBox
  print(String(format: "%.4f %.4f %.4f %.4f\t%@", box.origin.x, box.origin.y, box.size.width, box.size.height, candidate.string))
}
