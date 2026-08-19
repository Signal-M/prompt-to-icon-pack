#!/usr/bin/env swift

import AppKit
import Foundation
import Vision

struct OCRItem: Codable {
    let text: String
    let confidence: Float
    let x: Double
    let y: Double
    let width: Double
    let height: Double
}

guard CommandLine.arguments.count == 2 else {
    fputs("Usage: ocr_vision.swift IMAGE\n", stderr)
    exit(2)
}

let imageURL = URL(fileURLWithPath: CommandLine.arguments[1])
guard let image = NSImage(contentsOf: imageURL) else {
    fputs("Unable to open image: \(imageURL.path)\n", stderr)
    exit(2)
}

var proposed = CGRect(origin: .zero, size: image.size)
guard let cgImage = image.cgImage(forProposedRect: &proposed, context: nil, hints: nil) else {
    fputs("Unable to decode image: \(imageURL.path)\n", stderr)
    exit(2)
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = true
request.recognitionLanguages = ["zh-Hans", "en-US"]
request.minimumTextHeight = 0.008

do {
    try VNImageRequestHandler(cgImage: cgImage, options: [:]).perform([request])
} catch {
    let nsError = error as NSError
    fputs("Vision OCR failed: \(nsError.domain) \(nsError.code) \(nsError.userInfo)\n", stderr)
    exit(1)
}

let observations = request.results ?? []
let items = observations.compactMap { observation -> OCRItem? in
    guard let candidate = observation.topCandidates(1).first else { return nil }
    let box = observation.boundingBox
    return OCRItem(
        text: candidate.string,
        confidence: candidate.confidence,
        x: box.origin.x,
        y: 1.0 - box.origin.y - box.height,
        width: box.width,
        height: box.height
    )
}

let encoder = JSONEncoder()
encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
do {
    let data = try encoder.encode(items)
    FileHandle.standardOutput.write(data)
    FileHandle.standardOutput.write(Data("\n".utf8))
} catch {
    fputs("Unable to encode OCR results: \(error)\n", stderr)
    exit(1)
}
