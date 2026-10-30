// Restore an existing WeChat main window from Stage Manager; no farm-page guesses.
// This helper never purchases, harvests, plants, or clicks inside WeChat content.
import Foundation
import CoreGraphics
import AppKit

struct Window {
    let id: Int
    let pid: Int
    let owner: String
    let title: String
    let x: Double
    let y: Double
    let width: Double
    let height: Double
}

func windows() -> [Window] {
    let opts: CGWindowListOption = [.optionOnScreenOnly, .excludeDesktopElements]
    guard let raw = CGWindowListCopyWindowInfo(opts, kCGNullWindowID) as? [[String: Any]] else { return [] }
    return raw.compactMap { w in
        let owner = w[kCGWindowOwnerName as String] as? String ?? ""
        let title = w[kCGWindowName as String] as? String ?? ""
        let layer = w[kCGWindowLayer as String] as? Int ?? -1
        guard ["微信", "WeChat"].contains(owner), layer == 0,
              let b = w[kCGWindowBounds as String] as? [String: Any],
              let x = b["X"] as? Double, let y = b["Y"] as? Double,
              let width = b["Width"] as? Double, let height = b["Height"] as? Double,
              let id = w[kCGWindowNumber as String] as? Int,
              let pid = w[kCGWindowOwnerPID as String] as? Int,
              id > 0, pid > 0, width > 0, height > 0 else { return nil }
        return Window(id: id, pid: pid, owner: owner, title: title,
                      x: x, y: y, width: width, height: height)
    }
}

func allowedNow() -> Bool {
    let c = Calendar.current.dateComponents([.hour, .minute], from: Date())
    guard let hour = c.hour, let minute = c.minute else { return false }
    let t = hour * 60 + minute
    return ![(0,60),(480,540),(720,780),(840,845),(960,1020),(1200,1260)].contains { t >= $0.0 && t < $0.1 }
}

func fail(_ code: String) -> Never {
    fputs(code + "\n", stderr)
    exit(2)
}

func mainWindows() -> [Window] {
    windows().filter { $0.title == "微信" && $0.width >= 500 && $0.height >= 550 }
}

let existingFarm = windows().filter {
    $0.title == "QQ经典农场" && $0.width >= 500 && $0.height >= 900
}
if existingFarm.count == 1 {
    print("WECHAT_FARM_VISIBLE")
    exit(0)
}
if existingFarm.count > 1 { fail("WECHAT_FARM_AMBIGUOUS") }

if mainWindows().count == 1 {
    print("WECHAT_MAIN_VISIBLE")
    exit(0)
}
if !mainWindows().isEmpty { fail("WECHAT_MAIN_AMBIGUOUS") }
let tiles = windows().filter {
    $0.title == "微信" && $0.width >= 50 && $0.width < 300
    && $0.height >= 50 && $0.height < 300
    && $0.x >= 0 && $0.x < 300
}
guard tiles.count == 1 else { fail("WECHAT_TILE_NOT_UNIQUE") }
guard allowedNow() else { fail("FARM_OPERATION_TIME_BLOCKED") }
let tile = tiles[0]
let clickPoint = CGPoint(x: tile.x + tile.width / 2, y: tile.y + tile.height / 2)
// CGWindowList is front-to-back. Refuse a covered Stage Manager thumbnail.
let topAtPoint = (CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements],
                                            kCGNullWindowID) as? [[String: Any]])?.first { item in
    let alpha = item[kCGWindowAlpha as String] as? Double ?? 1
    guard alpha > 0.01,
          let b = item[kCGWindowBounds as String] as? [String: Any],
          let x = b["X"] as? Double, let y = b["Y"] as? Double,
          let width = b["Width"] as? Double, let height = b["Height"] as? Double
    else { return false }
    return CGRect(x: x, y: y, width: width, height: height).contains(clickPoint)
}
if (topAtPoint?[kCGWindowNumber as String] as? Int) != tile.id {
    // Stage Manager thumbnail can be covered by another app. Activating the
    // *verified tile owner PID* avoids guessing a Dock position or clicking
    // through the occluding business window. Never launch another instance.
    guard allowedNow() else { fail("FARM_OPERATION_TIME_BLOCKED") }
    guard let app = NSRunningApplication(processIdentifier: pid_t(tile.pid)),
          app.activate(options: []) else {
        fail("WECHAT_TILE_OCCLUDED")
    }
    for _ in 0..<12 {
        usleep(250_000)
        guard allowedNow() else { fail("FARM_OPERATION_TIME_BLOCKED") }
        if mainWindows().count == 1 {
            print("WECHAT_MAIN_RESTORED_BY_PID")
            exit(0)
        }
    }
    fail("WECHAT_MAIN_NOT_RESTORED")
}
guard CGPreflightPostEventAccess() else { fail("ACCESSIBILITY_PERMISSION_MISSING") }
let point = CGPoint(x: tile.x + tile.width / 2, y: tile.y + tile.height / 2)
guard let move = CGEvent(mouseEventSource: nil, mouseType: .mouseMoved, mouseCursorPosition: point, mouseButton: .left),
      let down = CGEvent(mouseEventSource: nil, mouseType: .leftMouseDown, mouseCursorPosition: point, mouseButton: .left),
      let up = CGEvent(mouseEventSource: nil, mouseType: .leftMouseUp, mouseCursorPosition: point, mouseButton: .left)
else { fail("CG_EVENT_UNAVAILABLE") }
move.post(tap: .cghidEventTap)
usleep(120_000)
guard allowedNow() else { fail("FARM_OPERATION_TIME_BLOCKED") }
down.post(tap: .cghidEventTap)
usleep(80_000)
up.post(tap: .cghidEventTap)
for _ in 0..<12 {
    usleep(250_000)
    if mainWindows().count == 1 {
        print("WECHAT_MAIN_RESTORED")
        exit(0)
    }
}
fail("WECHAT_MAIN_NOT_RESTORED")
