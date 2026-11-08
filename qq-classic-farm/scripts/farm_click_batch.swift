// Precompile once: swiftc scripts/farm_click_batch.swift -o _sandbox/farm_click_batch
// Default mode is JSON validation only. --execute requires live target/focus/occlusion checks.
// No AppleScript/System Events; only CoreGraphics CGEvent is used for clicks.
import AppKit
import ApplicationServices
import CoreGraphics
import Foundation

struct Frame: Decodable {
    let x: Double
    let y: Double
    let width: Double
    let height: Double
}
struct Action: Decodable {
    let x: Double // WINDOW-LOCAL logical coordinate
    let y: Double
    let delay_ms: Int
    let hover_ms: Int?
}
struct Batch: Decodable {
    let window_id: Int
    let pid: Int
    let owner: String
    let title: String
    let frame: Frame
    let window_frame: Frame?
    let actions: [Action]
}
struct Result: Encodable {
    let status: String
    let code: String?
    let click_count: Int
}

func allowedNow() -> Bool {
    // Interactive Chat operation is explicitly user-authorized.
    // Time collision windows belong to the future scheduler layer.
    return true
}

func stop(_ code: String, _ detail: String, clicksSent: Int = 0) -> Never {
    // A phase can have changed the farm before a later click fails. Report
    // confirmed posts so recovery never treats the entire batch as untouched.
    let payload: [String: Any] = [
        "status": "stopped", "code": code, "message": detail,
        "click_count": clicksSent,
    ]
    if let data = try? JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys]),
       let json = String(data: data, encoding: .utf8) { print(json) }
    exit(2)
}
func field(_ window: [String: Any], _ key: CFString) -> String {
    return window[key as String] as? String ?? ""
}
func windows(clicksSent: Int) -> [[String: Any]] {
    guard let raw = CGWindowListCopyWindowInfo(
        [.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID
    ) as? [[String: Any]] else {
        stop("WINDOW_NOT_FOUND", "Cannot enumerate on-screen windows", clicksSent: clicksSent)
    }
    return raw
}
func bounds(_ info: [String: Any]) -> CGRect? {
    guard let b = info[kCGWindowBounds as String] as? [String: Any],
          let x = b["X"] as? Double, let y = b["Y"] as? Double,
          let w = b["Width"] as? Double, let h = b["Height"] as? Double
    else { return nil }
    return CGRect(x: x, y: y, width: w, height: h)
}
// Dock and Notification Center expose transparent full-screen system surfaces
// with alpha=1, despite passing pointer events to the farm. Ignore only these
// exact main-display/layer combinations. Occlusion checking remains strict:
// after those system pass-through surfaces, the first real visible window at
// the click point must be the target farm. Other apps and unknown layers STOP.
func isSystemPassThrough(_ info: [String: Any], _ rect: CGRect) -> Bool {
    let owner = field(info, kCGWindowOwnerName)
    let layer = info[kCGWindowLayer as String] as? Int ?? -1
    let recognized = ((owner == "程序坞" || owner == "Dock") && layer == 20)
        || ((owner == "通知中心" || owner == "Notification Center") && layer == 21)
    guard recognized else { return false }
    let screen = CGDisplayBounds(CGMainDisplayID())
    return abs(rect.minX - screen.minX) <= 2
        && abs(rect.minY - screen.minY) <= 2
        && abs(rect.width - screen.width) <= 2
        && abs(rect.height - screen.height) <= 2
}

func liveWindow(_ batch: Batch, _ point: CGPoint, clicksSent: Int) {
    let list = windows(clicksSent: clicksSent)
    guard let target = list.first(where: {
        ($0[kCGWindowNumber as String] as? Int) == batch.window_id
    }) else { stop("WINDOW_NOT_FOUND", "Target window ID no longer visible", clicksSent: clicksSent) }
    guard field(target, kCGWindowOwnerName) == batch.owner,
          field(target, kCGWindowName) == batch.title,
          (target[kCGWindowOwnerPID as String] as? Int) == batch.pid,
          let current = bounds(target)
    else { stop("WINDOW_NOT_FOUND", "Target window identity changed", clicksSent: clicksSent) }
    let expectedWindow = batch.window_frame ?? batch.frame
    if abs(current.origin.x - expectedWindow.x) > 1 ||
       abs(current.origin.y - expectedWindow.y) > 1 ||
       abs(current.width - expectedWindow.width) > 1 ||
       abs(current.height - expectedWindow.height) > 1 {
        stop("WINDOW_SIZE_CHANGED", "Window moved/resized since batch preparation", clicksSent: clicksSent)
    }
    guard NSWorkspace.shared.frontmostApplication?.processIdentifier == pid_t(batch.pid) else {
        stop("WRONG_FRONTMOST_APP", "Target app is not frontmost", clicksSent: clicksSent)
    }
    // CGWindowList is front-to-back. Any visible overlapping window blocks input.
    for info in list {
        let alpha = info[kCGWindowAlpha as String] as? Double ?? 1
        guard alpha > 0.01, let rect = bounds(info), rect.contains(point) else { continue }
        let id = info[kCGWindowNumber as String] as? Int ?? -1
        if isSystemPassThrough(info, rect) {
            continue
        }
        if id == batch.window_id { return }
        stop("WINDOW_OCCLUDED", "Another visible window covers click target", clicksSent: clicksSent)
    }
    stop("WINDOW_OCCLUDED", "Target window is not topmost at click point", clicksSent: clicksSent)
}

let arguments = Array(CommandLine.arguments.dropFirst())
let wechatMain = arguments.count == 2 && arguments.last == "--wechat-main"
let mode = arguments.first
guard arguments.isEmpty ||
      ((arguments.count == 1 || wechatMain) && (mode == "--preflight" || mode == "--execute")) else {
    stop("INVALID_ARGUMENT", "Use no arguments, --preflight, or --execute; --wechat-main is optional for input modes")
}
let execute = mode == "--execute"
let preflight = mode == "--preflight"
let input = FileHandle.standardInput.readDataToEndOfFile()
guard let batch = try? JSONDecoder().decode(Batch.self, from: input) else {
    stop("INVALID_BATCH", "Expected JSON Batch on stdin")
}
let wechatOwners = ["微信", "WeChat"]
if execute && wechatOwners.contains(batch.owner) {
    let statusURL = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent().deletingLastPathComponent()
        .appendingPathComponent("data/wechat-live-status.txt")
    let status = try? String(contentsOf: statusURL, encoding: .utf8)
    guard status?.trimmingCharacters(in: .whitespacesAndNewlines) == "active" else {
        stop("WECHAT_FARM_SEALED", "WeChat farm live input is disabled")
    }
}
let validIdentity = wechatMain
    ? (wechatOwners.contains(batch.owner) && wechatOwners.contains(batch.title)
       && [1007, 1008].contains(batch.frame.width) && batch.frame.height == 974
       && batch.window_frame == nil && batch.actions.count == 1)
    : (batch.title == "QQ经典农场" && (["QQ小程序"] + wechatOwners).contains(batch.owner))
guard batch.window_id > 0, batch.pid > 0, validIdentity,
      batch.frame.width > 0, batch.frame.height > 0,
      [batch.frame.x, batch.frame.y, batch.frame.width, batch.frame.height].allSatisfy({ $0.isFinite }),
      (1...24).contains(batch.actions.count)
else { stop("INVALID_BATCH", "Invalid window identity/frame/action count") }
let expectedWindow = batch.window_frame ?? batch.frame
guard expectedWindow.width > 0, expectedWindow.height > 0,
      [expectedWindow.x, expectedWindow.y,
       expectedWindow.width, expectedWindow.height].allSatisfy({ $0.isFinite })
else { stop("INVALID_BATCH", "Invalid OS window frame") }
let frameTolerance = 1.0
guard batch.frame.x >= expectedWindow.x - frameTolerance,
      batch.frame.y >= expectedWindow.y - frameTolerance,
      batch.frame.x + batch.frame.width <= expectedWindow.x + expectedWindow.width + frameTolerance,
      batch.frame.y + batch.frame.height <= expectedWindow.y + expectedWindow.height + frameTolerance
else { stop("CANVAS_OUTSIDE_WINDOW", "Game canvas must stay inside the target OS window") }
for a in batch.actions {
    guard a.x.isFinite, a.y.isFinite,
          a.x >= 0, a.y >= 0,
          a.x < batch.frame.width, a.y < batch.frame.height,
          (0...1500).contains(a.delay_ms)
    else { stop("CLICK_OUTSIDE_WINDOW", "Invalid local click/delay") }
}
guard batch.actions.reduce(0, { $0 + $1.delay_ms }) <= 20000 else {
    stop("INVALID_BATCH", "Batch delay budget exceeded")
}
if !execute && !preflight {
    let result = Result(status: "validated_no_click", code: nil, click_count: 0)
    let data = try JSONEncoder().encode(result)
    print(String(decoding: data, as: UTF8.self))
    exit(0)
}
guard allowedNow() else {
    stop("FARM_OPERATION_TIME_BLOCKED", "Mac local clock is in a prohibited automation window")
}
guard CGPreflightPostEventAccess() else {
    stop("ACCESSIBILITY_PERMISSION_MISSING", "CGEvent posting not permitted")
}
if preflight {
    for a in batch.actions {
        let p = CGPoint(x: batch.frame.x + a.x, y: batch.frame.y + a.y)
        liveWindow(batch, p, clicksSent: 0)
    }
    let result = Result(status: "preflight_ok_no_click", code: nil, click_count: 0)
    let data = try JSONEncoder().encode(result)
    print(String(decoding: data, as: UTF8.self))
    exit(0)
}
var clicked = 0
for a in batch.actions {
    guard allowedNow() else {
        stop("FARM_OPERATION_TIME_BLOCKED", "Mac local clock is in a prohibited automation window", clicksSent: clicked)
    }
    let p = CGPoint(x: batch.frame.x + a.x, y: batch.frame.y + a.y)
    liveWindow(batch, p, clicksSent: clicked) // Recheck before every click.
    if let hoverMs = a.hover_ms, hoverMs > 0 {
        guard hoverMs <= 1000 else {
            stop("INVALID_HOVER", "Hover delay exceeds safety bound", clicksSent: clicked)
        }
        guard let move = CGEvent(mouseEventSource: nil, mouseType: .mouseMoved,
                                 mouseCursorPosition: p, mouseButton: .left)
        else { stop("CGEVENT_FAILED", "Cannot construct mouse move", clicksSent: clicked) }
        move.post(tap: .cghidEventTap)
        usleep(useconds_t(hoverMs * 1000))
        liveWindow(batch, p, clicksSent: clicked)
    }
    guard let down = CGEvent(mouseEventSource: nil, mouseType: .leftMouseDown,
                             mouseCursorPosition: p, mouseButton: .left),
          let up = CGEvent(mouseEventSource: nil, mouseType: .leftMouseUp,
                           mouseCursorPosition: p, mouseButton: .left)
    else { stop("CGEVENT_FAILED", "Cannot construct mouse event", clicksSent: clicked) }
    down.post(tap: .cghidEventTap)
    usleep(50_000)
    up.post(tap: .cghidEventTap)
    clicked += 1
    if a.delay_ms > 0 { usleep(useconds_t(a.delay_ms * 1000)) }
}
let data = try JSONEncoder().encode(Result(status: "clicks_sent_unverified",
                                            code: nil, click_count: clicked))
print(String(decoding: data, as: UTF8.self))
