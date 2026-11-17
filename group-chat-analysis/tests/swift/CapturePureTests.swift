import CoreGraphics
import Foundation
import ImageIO

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

private func testQQWindowInputGuard() throws {
    let display = CGRect(x: 0, y: 0, width: 2560, height: 1440)
    let frame = CGRect(x: 100, y: 100, width: 600, height: 500)
    let point = CGPoint(x: 400, y: 300)
    func row(_ id: UInt32, _ pid: Int32, _ rect: CGRect, owner: String = "QQ",
             layer: Int = 0, alpha: Double = 1) -> [String: Any] {
        [kCGWindowNumber as String: id, kCGWindowOwnerPID as String: pid,
         kCGWindowOwnerName as String: owner, kCGWindowLayer as String: layer,
         kCGWindowAlpha as String: alpha,
         kCGWindowBounds as String: ["X": rect.minX, "Y": rect.minY,
                                    "Width": rect.width, "Height": rect.height]]
    }
    func allowed(_ rows: [[String: Any]]) -> Bool {
        QQWindowInputGuard.isExposed(windowID: 5, pid: 10, frame: frame, at: point,
                                    windows: rows, mainDisplay: display)
    }
    let target = row(5, 10, frame)
    let sameAppCover = row(6, 10, frame)
    let otherAppCover = row(7, 11, frame, owner: "Another app")
    try expect(allowed([target, sameAppCover]), "a window behind the target cannot block the point")
    try expect(!allowed([sameAppCover, target]), "a QQ window covering the target must block input")
    try expect(!allowed([otherAppCover, target]), "a different app covering the target must block input")
    try expect(!allowed([sameAppCover]), "a missing target must block input")
    try expect(!allowed([row(5, 11, frame)]), "window ID must still belong to the verified process")
    try expect(!allowed([row(5, 10, frame.offsetBy(dx: 10, dy: 0))]), "moved target must reject stale coordinates")
    try expect(allowed([row(8, 12, frame, alpha: 0), target]), "fully invisible surfaces do not obscure the target")
    try expect(allowed([row(9, 13, display, owner: "程序坞", layer: 20), target]), "known Dock backing surface passes through")
    try expect(!allowed([row(9, 13, frame, owner: "程序坞", layer: 20), target]), "a Dock panel at the click point must still block input")
    try expect(!allowed([row(9, 13, display, owner: "Unknown overlay", layer: 20), target]), "an unknown full-display overlay must still block input")
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
    let plusTarget = QQConversationTarget(groupKey: "plus", conversationPrefix: "演示世界远征+经典服", headerContains: "远征+经典服玩家群", expectedHistoryTitle: "演示世界远征+经典服玩家群")
    try expect(QQConversationSwitcher.verifiesTarget([block(3, "演示世界远征＋经典服玩家群（123）", x: 0.313, y: 0.914, width: 0.234, height: 0.022)], target: plusTarget), "fullwidth plus in verified header is the same punctuation")
    try expect(!QQConversationSwitcher.verifiesTarget([block(3, "演示世界远征＋经典服玩家群", x: 0.313, y: 0.45, width: 0.234, height: 0.022)], target: plusTarget), "normalizing punctuation must not accept body text")
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
    let bodyOnly = [
        block(0, "刚才有人提到国服备战总群", x: 0.36, y: 0.45, width: 0.20, height: 0.02),
    ]
    try expect(
        !QQConversationSwitcher.verifiesTarget(bodyOnly, target: target),
        "matching text in chat body must not verify the selected target"
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

private func testDisplayBBoxRemapsVisionCoordinates() throws {
    let original = CGRect(x: 0.9680, y: 0.0974, width: 0.0174, height: 0.0139)
    let remapped = VisionTextRecognizer.displayBBox(for: original, orientation: .down)
    try expect(abs(remapped.x - 0.0146) < 0.0002, "180-degree bbox x should map back to the displayed toolbar position")
    try expect(abs(remapped.y - 0.8887) < 0.0002, "180-degree bbox y should map back to the displayed toolbar position")
    try expect(remapped.width == original.width && remapped.height == original.height, "180-degree bbox remap must preserve size")

    let quarterTurn = CGRect(x: 0.10, y: 0.20, width: 0.30, height: 0.40)
    let right = VisionTextRecognizer.displayBBox(for: quarterTurn, orientation: .right)
    try expect(abs(right.x - 0.40) < 0.0001, "90-degree right bbox x remap is wrong")
    try expect(abs(right.y - 0.10) < 0.0001, "90-degree right bbox y remap is wrong")
    try expect(abs(right.width - 0.40) < 0.0001 && abs(right.height - 0.30) < 0.0001, "90-degree right bbox size should swap axes")

    let left = VisionTextRecognizer.displayBBox(for: quarterTurn, orientation: .left)
    try expect(abs(left.x - 0.20) < 0.0001, "90-degree left bbox x remap is wrong")
    try expect(abs(left.y - 0.60) < 0.0001, "90-degree left bbox y remap is wrong")
    try expect(abs(left.width - 0.40) < 0.0001 && abs(left.height - 0.30) < 0.0001, "90-degree left bbox size should swap axes")

    let upright = VisionTextRecognizer.displayBBox(for: original, orientation: .up)
    try expect(upright.x == original.origin.x && upright.y == original.origin.y, "upright bbox must remain unchanged")
}

private func testToolbarEvidenceScoreUsesOnlyCoLinearControls() throws {
    let blocks = [
        block(0, "全部", x: 0.02, y: 0.887),
        block(1, "图片/视频", x: 0.07, y: 0.887),
        block(2, "表情 文件 链接", x: 0.14, y: 0.887),
        block(3, "正文里提到筛选和文件", x: 0.08, y: 0.55),
    ]
    try expect(ContentRegionLocator.toolbarEvidenceScore(from: blocks) == 5, "toolbar evidence should count distinct tokens only on the best toolbar row")
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

@MainActor
private func testWindowPreparationReuse() async throws {
    let target = WindowTargetGeometry(x: 20, y: 30, width: 900, height: 900)
    let moved = WindowTargetGeometry(x: 25, y: 30, width: 900, height: 900)
    let withinTolerance = WindowTargetGeometry(x: 22, y: 28, width: 902, height: 898)
    for (reuse, initial, expectedEvents) in [
        (true, target, ["read", "sck"]),
        (true, withinTolerance, ["read", "sck"]),
        (true, moved, ["read", "set", "settle", "read", "sck"]),
        (false, target, ["set", "settle", "read", "sck"])
    ] {
        var actual = initial
        var events: [String] = []
        try await QQWindowPreparer.prepareGeometry(
            expected: target, tolerance: 2, reuseExisting: reuse,
            read: { events.append("read"); return actual },
            set: { events.append("set"); actual = target },
            settle: { events.append("settle") },
            verifySCK: { events.append("sck") }
        )
        try expect(events == expectedEvents, "geometry reuse must preserve verification and only skip redundant writes")
    }
    // Failure at every boundary must propagate; no further stage may run.
    for failure in ["read", "set", "settle", "readback", "sck"] {
        var events: [String] = []
        var reads = 0
        do {
            try await QQWindowPreparer.prepareGeometry(
                expected: target, tolerance: 2, reuseExisting: true,
                read: {
                    reads += 1
                    let step = reads == 1 ? "read" : "readback"
                    events.append(step)
                    if failure == step { throw TestFailure.failed(step) }
                    return reads == 1 ? moved : target
                },
                set: { events.append("set"); if failure == "set" { throw TestFailure.failed("set") } },
                settle: { events.append("settle"); if failure == "settle" { throw TestFailure.failed("settle") } },
                verifySCK: { events.append("sck"); if failure == "sck" { throw TestFailure.failed("sck") } }
            )
            throw TestFailure.failed("injected failure did not propagate")
        } catch TestFailure.failed(let message) {
            try expect(message == failure && events.last == failure, "stop immediately at failed preparation boundary")
        }
    }
    var reachedSCK = false
    do {
        try await QQWindowPreparer.prepareGeometry(
            expected: target, tolerance: 2, reuseExisting: true,
            read: { moved }, set: {}, settle: {}, verifySCK: { reachedSCK = true }
        )
        throw TestFailure.failed("failed geometry write must not be accepted")
    } catch WindowPreparationError.geometryMismatch {
        try expect(!reachedSCK, "AX readback mismatch must stop before SCK")
    }
    // Even unchanged AX geometry must not bypass SCK failure.
    do {
        try await QQWindowPreparer.prepareGeometry(
            expected: target, tolerance: 2, reuseExisting: true,
            read: { target }, set: { throw TestFailure.failed("unexpected write") },
            settle: { throw TestFailure.failed("unexpected wait") },
            verifySCK: { throw WindowPreparationError.sckWindowNotFound("fixture") }
        )
        throw TestFailure.failed("fast path bypassed SCK rejection")
    } catch WindowPreparationError.sckWindowNotFound { }
}

@main
struct CapturePureTestsMain {
    static func main() async {
        do {
            try await testWindowPreparationReuse()
            try testContentRegion()
            try testContentRegionIgnoresToolbarWordsInsideMessages()
            try testConversationSwitcherPureGates()
            try testQQWindowInputGuard()
            try testMAD()
            try await testChangeDetectorRejectsReturnToBaseline()
            try await testChangeDetectorAcceptsDelayedStability()
            try await testChangeDetectorAllowsFingerprintStableDynamicNoise()
            try testVisualFingerprintDistance()
            try testAmbiguousScrollOCRFallback()
            try testDisplayBBoxRemapsVisionCoordinates()
            try testToolbarEvidenceScoreUsesOnlyCoLinearControls()
            try testCaptureSchemaShape()
            try testRawWriterPersistsAndRefusesOverwrite()
            print("CapturePureTests OK")
        } catch {
            fputs("CapturePureTests FAILED: \(error)\n", stderr)
            exit(1)
        }
    }
}
