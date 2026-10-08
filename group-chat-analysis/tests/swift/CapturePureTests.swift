import CoreGraphics
import Foundation

private enum TestFailure: Error, CustomStringConvertible {
    case failed(String)

    var description: String {
        switch self {
        case let .failed(message): return message
        }
    }
}

private func expect(_ condition: @autoclosure () -> Bool, _ message: String) throws {
    if !condition() {
        throw TestFailure.failed(message)
    }
}

private func block(
    _ index: Int,
    _ text: String,
    x: Double,
    y: Double,
    width: Double = 0.08,
    height: Double = 0.02,
    confidence: Double = 1.0
) -> CaptureOCRBlock {
    CaptureOCRBlock(
        blockIndex: index,
        text: text,
        bbox: CaptureBBox(x: x, y: y, width: width, height: height),
        confidence: confidence
    )
}

private func solidImage(_ value: UInt8, width: Int = 32, height: Int = 32) throws -> CGImage {
    let bytesPerRow = width * 4
    var bytes = [UInt8](repeating: value, count: bytesPerRow * height)
    for index in stride(from: 3, to: bytes.count, by: 4) {
        bytes[index] = 255
    }
    let colorSpace = CGColorSpaceCreateDeviceRGB()
    let bitmapInfo = CGBitmapInfo.byteOrder32Big.rawValue |
        CGImageAlphaInfo.premultipliedLast.rawValue
    return try bytes.withUnsafeMutableBytes { buffer in
        guard let context = CGContext(
            data: buffer.baseAddress,
            width: width,
            height: height,
            bitsPerComponent: 8,
            bytesPerRow: bytesPerRow,
            space: colorSpace,
            bitmapInfo: bitmapInfo
        ), let image = context.makeImage() else {
            throw TestFailure.failed("could not create synthetic image")
        }
        return image
    }
}

private func testContentRegion() throws {
    let blocks = [
        block(0, "Q搜索", x: 0.02, y: 0.93),
        block(1, "全部", x: 0.02, y: 0.887),
        block(2, "图片/视频", x: 0.07, y: 0.887),
        block(3, "筛选", x: 0.95, y: 0.887, width: 0.03),
        block(4, "玩家甲 12:34", x: 0.05, y: 0.80),
        block(5, "正文", x: 0.05, y: 0.76),
    ]
    let region = try ContentRegionLocator.locate(from: blocks)
    try expect(region.x == 0.0, "content region should begin at normalized left edge")
    try expect(region.maxY < 0.887, "content region must stay below toolbar")
    try expect(region.maxX < 0.95, "content region must stay left of filter controls")
    try expect(region.contains(midX: 0.09, midY: 0.77), "message block should be inside content region")
}

private func testContentRegionIgnoresToolbarWordsInsideMessages() throws {
    let blocks = [
        block(0, "Q搜索", x: 0.02, y: 0.93),
        block(1, "全部", x: 0.02, y: 0.884),
        block(2, "图片/视频", x: 0.06, y: 0.886),
        block(3, "表情 文件 链接", x: 0.12, y: 0.886, width: 0.11),
        block(4, "筛选", x: 0.956, y: 0.889, width: 0.03),
        block(5, "玩家甲 23:10", x: 0.04, y: 0.30),
        block(6, "0/1 在篝火旁使用/sit（/", x: 0.08, y: 0.24),
        block(7, "坐下）表情", x: 0.08, y: 0.22),
    ]
    let region = try ContentRegionLocator.locate(from: blocks)
    try expect(region.maxY > 0.84, "isolated message toolbar word must not lower the toolbar boundary")
    try expect(region.contains(midX: 0.10, midY: 0.23), "message containing 表情 must remain inside content")
}

private func testConversationSwitcherPureGates() throws {
    let blocks = [
        block(0, "魔兽世界2无限国服备战..", x: 0.10, y: 0.48, width: 0.15, height: 0.02),
        block(1, "魔兽世界2无限国服备战总群（1777）", x: 0.33, y: 0.91, width: 0.21, height: 0.02),
        block(2, "群聊成员 1777", x: 0.86, y: 0.66, width: 0.09, height: 0.02),
    ]
    let candidate = try QQConversationSwitcher.conversationCandidate(
        from: blocks,
        prefix: "魔兽世界2无限国服备战"
    )
    try expect(candidate.blockIndex == 0, "only the safe left-list candidate may be selected")

    let target = QQConversationTarget(
        groupKey: "group-b",
        conversationPrefix: "魔兽世界2无限国服备战",
        headerContains: "国服备战总群",
        expectedHistoryTitle: "魔兽世界2无限国服备战总群"
    )
    try expect(
        QQConversationSwitcher.verifiesTarget(blocks, target: target),
        "selected target must be verified by its stable header text"
    )
    let wrongHeader = QQConversationTarget(
        groupKey: "group-b",
        conversationPrefix: target.conversationPrefix,
        headerContains: "另一个群",
        expectedHistoryTitle: target.expectedHistoryTitle
    )
    try expect(
        !QQConversationSwitcher.verifiesTarget(blocks, target: wrongHeader),
        "wrong header text must reject target verification"
    )
    try expect(
        QQConversationSwitcher.isVerifiedHistoryTooltip(["聊天记录"]),
        "exact chat-history tooltip must pass"
    )
    try expect(
        !QQConversationSwitcher.isVerifiedHistoryTooltip(["语音通话"]),
        "unrelated tooltip must fail"
    )

    do {
        _ = try QQConversationSwitcher.conversationCandidate(
            from: [block(0, "魔兽世界2无限国服备战", x: 0.45, y: 0.48, width: 0.15)],
            prefix: "魔兽世界2无限国服备战"
        )
        throw TestFailure.failed("matching text outside the left list must not be clickable")
    } catch ConversationSwitchError.unsafeConversationCandidate {
        // Expected.
    }
}

private func testMAD() throws {
    let black = try solidImage(0)
    let sameBlack = try solidImage(0)
    let white = try solidImage(255)
    let region = CaptureBBox(x: 0, y: 0, width: 1, height: 1)

    let quiet = try SparseRGBMAD.measure(black, sameBlack, region: region, step: 4)
    let changed = try SparseRGBMAD.measure(black, white, region: region, step: 4)
    let onePixelSmaller = try solidImage(0, width: 31, height: 32)
    let smallDrift = try SparseRGBMAD.measure(black, onePixelSmaller, region: region, step: 4)
    try expect(quiet == 0, "identical frames must have zero MAD")
    try expect(changed >= 250, "black/white frames should produce a large MAD")
    try expect(smallDrift == 0, "small SCK size drift should compare on the common crop")

    let largeDrift = try solidImage(0, width: 28, height: 32)
    do {
        _ = try SparseRGBMAD.measure(black, largeDrift, region: region, step: 4)
        throw TestFailure.failed("large frame-size drift must be rejected")
    } catch PixelDiffError.sizeMismatch {
        // Expected.
    }
}

private func testChangeDetectorRejectsReturnToBaseline() async throws {
    let black = try solidImage(0)
    let white = try solidImage(255)
    let region = CaptureBBox(x: 0, y: 0, width: 1, height: 1)
    var frames = [white, black, black, black]

    let result = try await ScrollChangeDetector.waitForStableChange(
        baseline: black,
        region: region
    ) {
        if frames.isEmpty {
            return black
        }
        return frames.removeFirst()
    }

    switch result {
    case .uncertain:
        return
    case .changedAndStable:
        throw TestFailure.failed("returning to baseline must not be accepted as a new stable page")
    case .noChange:
        throw TestFailure.failed("a transient large change must not be reported as never changed")
    }
}

private func testChangeDetectorAcceptsDelayedStability() async throws {
    let black = try solidImage(0)
    let white = try solidImage(255)
    let gray128 = try solidImage(128)
    let gray64 = try solidImage(64)
    let gray32 = try solidImage(32)
    let region = CaptureBBox(x: 0, y: 0, width: 1, height: 1)
    var frames = [white, gray128, gray64, gray32, gray32]

    let result = try await ScrollChangeDetector.waitForStableChange(
        baseline: black,
        region: region
    ) {
        if frames.isEmpty {
            return gray32
        }
        return frames.removeFirst()
    }

    switch result {
    case .changedAndStable:
        return
    case .noChange:
        throw TestFailure.failed("a delayed changed page must not be reported as no-change")
    case .uncertain:
        throw TestFailure.failed("a page stable by 1500ms should be accepted")
    }
}

private func testChangeDetectorAllowsFingerprintStableDynamicNoise() async throws {
    let black = try solidImage(0)
    let gray10 = try solidImage(10)
    let gray11 = try solidImage(11)
    let region = CaptureBBox(x: 0, y: 0, width: 1, height: 1)
    var frames = [gray10, gray11, gray11]

    let result = try await ScrollChangeDetector.waitForStableChange(
        baseline: black,
        region: region
    ) {
        if frames.isEmpty {
            return gray11
        }
        return frames.removeFirst()
    }

    switch result {
    case .changedAndStable(_, let baselineMAD, let adjacentMAD):
        try expect(baselineMAD >= 2.5, "baseline must still prove a real change")
        try expect(adjacentMAD > 0.8 && adjacentMAD <= 2.0, "fingerprint fallback should only cover calibrated dynamic noise")
    case .noChange:
        throw TestFailure.failed("clear baseline change with stable fingerprint must not be no-change")
    case .uncertain:
        throw TestFailure.failed("calibrated dynamic noise should not block a stable changed page")
    }
}

private func testVisualFingerprintDistance() throws {
    let zero = "dhash512:" + String(repeating: "0", count: 128)
    let fourBits = "dhash512:" + String(repeating: "0", count: 127) + "f"
    let twoBits = "dhash512:" + String(repeating: "0", count: 127) + "3"
    let twentyBits = "dhash512:" + String(repeating: "0", count: 123) + "fffff"
    let twentyOneBits = "dhash512:" + String(repeating: "0", count: 122) + "1fffff"
    let distance = try VisualFingerprint.distance(zero, fourBits)
    let sameViewport = try VisualFingerprint.sameViewport(zero, twoBits)
    let thresholdAccepted = try VisualFingerprint.sameViewport(zero, twentyBits)
    let thresholdRejected = try VisualFingerprint.sameViewport(zero, twentyOneBits)
    try expect(distance == 4, "dHash Hamming distance should count differing bits")
    try expect(sameViewport, "small dHash distance should be accepted as the same viewport")
    try expect(thresholdAccepted, "20-bit distance should be accepted at the calibrated boundary")
    try expect(!thresholdRejected, "21-bit distance should be rejected above the calibrated boundary")
}

private func samplePage() -> RawCapturePage {
    RawCapturePage(
        schemaVersion: "2",
        visualFingerprint: "dhash512:" + String(repeating: "0", count: 128),
        batchID: "batch-test",
        groupKey: "group-a",
        groupDisplay: "测试群",
        pageIndex: 0,
        capturedAt: "2026-01-01T00:00:00Z",
        source: "qq_history_window_ocr",
        window: CaptureWindowInfo(
            title: "测试群",
            framePoints: CaptureScreenFrame(x: 1, y: 2, width: 1000, height: 700),
            captureSizePixels: CapturePixelSize(width: 1000, height: 700)
        ),
        contentRegion: CaptureBBox(x: 0, y: 0.02, width: 0.92, height: 0.84),
        blocks: [block(0, "正文", x: 0.05, y: 0.5)]
    )
}

private func pageWithTexts(_ texts: [String], pageIndex: Int) -> RawCapturePage {
    let blocks = texts.enumerated().map { index, text in
        block(
            index,
            text,
            x: 0.05,
            y: 0.78 - Double(index) * 0.035,
            width: 0.20,
            height: 0.02
        )
    }
    return RawCapturePage(
        schemaVersion: "2",
        visualFingerprint: "dhash512:" + String(repeating: "0", count: 128),
        batchID: "batch-test",
        groupKey: "group-a",
        groupDisplay: "测试群",
        pageIndex: pageIndex,
        capturedAt: "2026-01-01T00:00:00Z",
        source: "qq_history_window_ocr",
        window: CaptureWindowInfo(
            title: "测试群",
            framePoints: CaptureScreenFrame(x: 1, y: 2, width: 1000, height: 700),
            captureSizePixels: CapturePixelSize(width: 1000, height: 700)
        ),
        contentRegion: CaptureBBox(x: 0, y: 0.02, width: 0.92, height: 0.84),
        blocks: blocks
    )
}

private func testAmbiguousScrollOCRFallback() throws {
    let previous = pageWithTexts(
        ["共享1", "共享2", "共享3", "旧4", "旧5", "旧6", "旧7", "旧8", "旧9", "旧10"],
        pageIndex: 0
    )
    let clearlyNew = pageWithTexts(
        ["共享1", "共享2", "共享3", "新4", "新5", "新6", "新7", "新8", "新9", "新10"],
        pageIndex: 1
    )
    try expect(
        QQHistoryCapture.isClearlyDifferentByOCR(previous: previous, current: clearlyNew),
        "low-overlap OCR pages should confirm an ambiguous low-motion scroll"
    )

    let partialScroll = pageWithTexts(
        ["共享1", "共享2", "共享3", "旧4", "旧5", "旧6", "旧7", "旧8", "新9", "新10"],
        pageIndex: 1
    )
    try expect(
        QQHistoryCapture.isClearlyDifferentByOCR(previous: previous, current: partialScroll),
        "high-overlap partial scroll should be preserved rather than risk a second scroll"
    )

    let identical = pageWithTexts(
        ["共享1", "共享2", "共享3", "旧4", "旧5", "旧6", "旧7", "旧8", "旧9", "旧10"],
        pageIndex: 1
    )
    try expect(
        !QQHistoryCapture.isClearlyDifferentByOCR(previous: previous, current: identical),
        "identical OCR pages must remain uncertain"
    )

    let sparse = pageWithTexts(["A1", "A2", "A3", "A4", "A5", "A6", "A7"], pageIndex: 1)
    try expect(
        !QQHistoryCapture.isClearlyDifferentByOCR(previous: previous, current: sparse),
        "sparse OCR evidence must remain uncertain"
    )
}

private func testCaptureSchemaShape() throws {
    let page = samplePage()

    let encoded = try JSONEncoder().encode(page)
    guard let object = try JSONSerialization.jsonObject(with: encoded) as? [String: Any] else {
        throw TestFailure.failed("encoded capture page is not an object")
    }
    let schemaData = try Data(contentsOf: URL(fileURLWithPath: "schemas/capture-page.schema.json"))
    guard let schema = try JSONSerialization.jsonObject(with: schemaData) as? [String: Any],
          let required = schema["required"] as? [String] else {
        throw TestFailure.failed("capture schema required fields unavailable")
    }

    try expect(Set(object.keys) == Set(required), "encoded capture page top-level keys drifted from schema")
    try expect(object["captured_at"] as? String == "2026-01-01T00:00:00Z", "captured_at key missing")
    try expect(object["content_region"] != nil, "content_region key missing")
    if let window = object["window"] as? [String: Any] {
        try expect(Set(window.keys) == Set(["title", "frame_points", "capture_size_pixels"]), "window keys drifted")
    } else {
        throw TestFailure.failed("window object missing")
    }
}

private func testRawWriterPersistsAndRefusesOverwrite() throws {
    let directory = URL(fileURLWithPath: NSTemporaryDirectory())
        .appendingPathComponent("group-chat-raw-writer-\(UUID().uuidString)")
    defer { try? FileManager.default.removeItem(at: directory) }
    let destination = directory.appendingPathComponent("page-000000.json")

    try writeRawPageAtomically(samplePage(), to: destination.path)
    try expect(FileManager.default.fileExists(atPath: destination.path), "raw writer must persist destination")

    do {
        try writeRawPageAtomically(samplePage(), to: destination.path)
        throw TestFailure.failed("raw writer must refuse overwrite")
    } catch RawPageWriterError.outputAlreadyExists {
        // Expected.
    }
}

@main
struct CapturePureTestsMain {
    static func main() async {
        do {
            try testContentRegion()
            try testContentRegionIgnoresToolbarWordsInsideMessages()
            try testConversationSwitcherPureGates()
            try testMAD()
            try await testChangeDetectorRejectsReturnToBaseline()
            try await testChangeDetectorAcceptsDelayedStability()
            try await testChangeDetectorAllowsFingerprintStableDynamicNoise()
            try testVisualFingerprintDistance()
            try testAmbiguousScrollOCRFallback()
            try testCaptureSchemaShape()
            try testRawWriterPersistsAndRefusesOverwrite()
            print("CapturePureTests OK")
        } catch {
            fputs("CapturePureTests FAILED: \(error)\n", stderr)
            exit(1)
        }
    }
}
