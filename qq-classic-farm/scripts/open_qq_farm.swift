import Foundation
import CoreGraphics
import AppKit

struct Window: Codable {
    let id: Int
    let pid: Int32
    let owner: String
    let title: String
    let x: Double
    let y: Double
    let width: Double
    let height: Double
    let layer: Int
    let alpha: Double
    var rect: CGRect { CGRect(x: x, y: y, width: width, height: height) }
}

func visibleWindows() -> [Window] {
    guard let rows = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID)
        as? [[String: Any]] else { return [] }
    return rows.compactMap { row in
        guard let id = row[kCGWindowNumber as String] as? Int,
              let pid = row[kCGWindowOwnerPID as String] as? Int,
              let b = row[kCGWindowBounds as String] as? [String: Any],
              let x = b["X"] as? Double, let y = b["Y"] as? Double,
              let w = b["Width"] as? Double, let h = b["Height"] as? Double else { return nil }
        return Window(id: id, pid: Int32(pid), owner: row[kCGWindowOwnerName as String] as? String ?? "",
                      title: row[kCGWindowName as String] as? String ?? "", x: x, y: y, width: w, height: h,
                      layer: row[kCGWindowLayer as String] as? Int ?? -1,
                      alpha: row[kCGWindowAlpha as String] as? Double ?? 1)
    }
}

func targetIssue(_ target: Window, _ point: CGPoint, _ list: [Window], _ frontPID: Int32,
                 _ display: CGRect) -> String? {
    guard let current = list.first(where: { $0.id == target.id }),
          current.pid == target.pid, current.owner == target.owner, current.title == target.title,
          current.layer == 0, current.alpha > 0.01 else { return "TARGET_IDENTITY_CHANGED" }
    guard abs(current.x - target.x) <= 1, abs(current.y - target.y) <= 1,
          abs(current.width - target.width) <= 1, abs(current.height - target.height) <= 1
    else { return "TARGET_FRAME_CHANGED" }
    guard current.rect.contains(point) else { return "POINT_OUTSIDE_TARGET" }
    guard frontPID == target.pid else { return "TARGET_NOT_FRONTMOST" }
    for w in list where w.alpha > 0.01 && w.rect.contains(point) {
        // Match the same known transparent system surfaces as farm_click_batch.
        let system = ((w.owner == "Dock" || w.owner == "程序坞") && w.layer == 20)
            || ((w.owner == "Notification Center" || w.owner == "通知中心") && w.layer == 21)
        if system && abs(w.x - display.minX) <= 2 && abs(w.y - display.minY) <= 2
            && abs(w.width - display.width) <= 2 && abs(w.height - display.height) <= 2 { continue }
        return w.id == target.id ? nil : "TARGET_OCCLUDED"
    }
    return "TARGET_NOT_VISIBLE_AT_POINT"
}

func stop(_ reason: String) -> Never {
    fputs(reason + "\n", stderr)
    exit(2)
}

func validateTarget(_ target: Window, _ point: CGPoint) {
    if let issue = targetIssue(target, point, visibleWindows(),
                               NSWorkspace.shared.frontmostApplication?.processIdentifier ?? -1,
                               CGDisplayBounds(CGMainDisplayID())) { stop(issue) }
}

func click(_ target: Window, _ point: CGPoint) {
    validateTarget(target, point)
    guard let move = CGEvent(mouseEventSource: nil, mouseType: .mouseMoved, mouseCursorPosition: point, mouseButton: .left),
          let down = CGEvent(mouseEventSource: nil, mouseType: .leftMouseDown, mouseCursorPosition: point, mouseButton: .left),
          let up = CGEvent(mouseEventSource: nil, mouseType: .leftMouseUp, mouseCursorPosition: point, mouseButton: .left)
    else { stop("CGEVENT_CREATION_FAILED") }
    move.post(tap: .cghidEventTap)
    usleep(180_000)
    validateTarget(target, point)
    down.post(tap: .cghidEventTap)
    usleep(90_000)
    up.post(tap: .cghidEventTap)
}

func fullFarm() -> [Window] {
    visibleWindows().filter { $0.owner == "QQ小程序" && $0.title == "QQ经典农场" && $0.layer == 0
        && $0.width >= 500 && $0.height >= 900 }
}

func activate(_ pid: Int32) {
    guard let app = NSRunningApplication(processIdentifier: pid), app.activate(options: [])
    else { stop("VERIFIED_PROCESS_ACTIVATION_FAILED") }
    // Same preparation delay used by the existing home-window helper.
    Thread.sleep(forTimeInterval: 5)
}

// Offline contract tests do not enumerate/activate any real app or post input.
if CommandLine.arguments.dropFirst().first == "--validate-target" {
    struct Probe: Decodable { let target: Window; let windows: [Window]; let frontPID: Int32; let point: [Double]; let display: [Double] }
    let input = FileHandle.standardInput.readDataToEndOfFile()
    guard let p = try? JSONDecoder().decode(Probe.self, from: input), p.point.count == 2, p.display.count == 4
    else { stop("INVALID_PROBE") }
    let issue = targetIssue(p.target, CGPoint(x: p.point[0], y: p.point[1]), p.windows, p.frontPID,
                            CGRect(x: p.display[0], y: p.display[1], width: p.display[2], height: p.display[3]))
    print(issue ?? "validated_no_click")
    exit(issue == nil ? 0 : 2)
}
guard CommandLine.arguments.count == 1 else { stop("INVALID_ARGUMENT") }

let root = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
let raw = try Data(contentsOf: root.appendingPathComponent("data/ui-layout.json"))
guard let obj = try JSONSerialization.jsonObject(with: raw) as? [String: Any],
      let platforms = obj["platforms"] as? [String: Any], let qq = platforms["qq"] as? [String: Any],
      let entry = qq["main_window_entry"] as? [String: Any],
      let baseline = entry["baseline_window_size"] as? [Double],
      let center = entry["farm_icon_center"] as? [Double], baseline.count == 2, center.count == 2
else { stop("QQ_ENTRY_CONFIG_INVALID") }

let farms = fullFarm()
if farms.count > 1 { stop("FARM_NOT_UNIQUE") }
if farms.count == 1 { print("QQ经典农场窗口已存在，交首页prepare核验"); exit(0) }
let farmTiles = visibleWindows().filter { $0.owner == "QQ小程序" && $0.title == "QQ经典农场" && $0.layer == 0
    && $0.width > 20 && $0.width < 300 && $0.height > 50 && $0.height < 300 }
if !farmTiles.isEmpty {
    guard farmTiles.count == 1 else { stop("FARM_TILE_NOT_UNIQUE") }
    activate(farmTiles[0].pid)
    let found = fullFarm()
    if found.count == 1 && found[0].pid == farmTiles[0].pid { print("已按PID恢复农场"); exit(0) }
    stop("FARM_ACTIVATED_BUT_NOT_RESTORED")
}

// Restore the QQ process by identity, never click a Stage Manager thumbnail.
let qqWindows = visibleWindows().filter { $0.owner == "QQ" && $0.layer == 0 && $0.pid > 0 }
let pids = Set(qqWindows.map { $0.pid })
guard pids.count == 1, let pid = pids.first else { stop("QQ_PROCESS_NOT_UNIQUE") }
activate(pid)
let candidates = visibleWindows().filter { $0.owner == "QQ" && $0.pid == pid && $0.layer == 0
    && abs($0.width - baseline[0]) <= 40 && abs($0.height - baseline[1]) <= 40 }
if candidates.count > 1 { stop("QQ_MAIN_WINDOW_NOT_UNIQUE") }
guard let target = candidates.first else { stop("QQ_MAIN_WINDOW_NOT_AT_BASELINE") }
click(target, CGPoint(x: target.x + center[0], y: target.y + center[1]))
for _ in 0..<12 {
    usleep(250_000)
    if fullFarm().count == 1 { print("已通过受保护QQ入口打开农场"); exit(0) }
}
stop("FARM_NOT_OPEN_AFTER_SINGLE_CLICK")
