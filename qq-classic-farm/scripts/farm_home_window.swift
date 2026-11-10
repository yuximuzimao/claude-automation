// QQ home window gate. --check is read-only; --prepare activates the existing farm only.
import AppKit
import CoreGraphics
import Foundation

func emit(_ state: String, _ extra: [String: Any] = [:]) -> Never {
    let data = try! JSONSerialization.data(withJSONObject: extra.merging(["state": state]) { _, new in new }, options: [.sortedKeys])
    print(String(decoding: data, as: UTF8.self))
    exit(state == "window_ready" ? 0 : 2)
}
func listWindows() -> [[String: Any]] {
    return CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] ?? []
}
func rectangle(_ info: [String: Any]) -> CGRect? {
    guard let b = info[kCGWindowBounds as String] as? [String: Any],
          let x = b["X"] as? Double, let y = b["Y"] as? Double,
          let w = b["Width"] as? Double, let h = b["Height"] as? Double else { return nil }
    return CGRect(x: x, y: y, width: w, height: h)
}
func farms(_ list: [[String: Any]]) -> [[String: Any]] {
    return list.filter {
        ($0[kCGWindowOwnerName as String] as? String) == "QQ小程序" &&
        ($0[kCGWindowName as String] as? String) == "QQ经典农场" &&
        ($0[kCGWindowLayer as String] as? Int) == 0
    }
}
func passThrough(_ info: [String: Any], _ rect: CGRect) -> Bool {
    let owner = info[kCGWindowOwnerName as String] as? String ?? ""
    let layer = info[kCGWindowLayer as String] as? Int ?? -1
    let known = (["Dock", "程序坞"].contains(owner) && layer == 20) ||
                (["Notification Center", "通知中心"].contains(owner) && layer == 21)
    let screen = CGDisplayBounds(CGMainDisplayID())
    return known && abs(rect.minX-screen.minX) <= 2 && abs(rect.minY-screen.minY) <= 2 &&
        abs(rect.width-screen.width) <= 2 && abs(rect.height-screen.height) <= 2
}
let args = Array(CommandLine.arguments.dropFirst())
guard args == ["--check"] || args == ["--prepare"] else { emit("invalid_arguments") }
var list = listWindows()
let initial = farms(list)
guard initial.count == 1 else { emit(initial.isEmpty ? "farm_not_found" : "farm_not_unique") }
guard let id = initial[0][kCGWindowNumber as String] as? Int,
      let pid = initial[0][kCGWindowOwnerPID as String] as? Int32 else { emit("invalid_window_identity") }
if args == ["--prepare"] {
    guard let app = NSRunningApplication(processIdentifier: pid), app.localizedName == "QQ小程序",
          app.activate(options: [.activateAllWindows]) else { emit("activation_failed") }
    Thread.sleep(forTimeInterval: 5)
    list = listWindows()
}
let current = farms(list)
guard current.count == 1, (current[0][kCGWindowNumber as String] as? Int) == id,
      (current[0][kCGWindowOwnerPID as String] as? Int32) == pid,
      let rect = rectangle(current[0]) else { emit("window_identity_changed") }
guard rect.width == 603 && rect.height == 1111 else { emit("nonstandard_window") }
guard NSWorkspace.shared.frontmostApplication?.processIdentifier == pid else { emit("farm_not_frontmost") }
for w in list {
    if (w[kCGWindowNumber as String] as? Int) == id { break }
    guard (w[kCGWindowAlpha as String] as? Double ?? 1) > 0.01,
          let other = rectangle(w), other.intersects(rect), !passThrough(w, other) else { continue }
    emit("window_occluded")
}
emit("window_ready", ["window_id": id, "pid": pid, "owner": "QQ小程序", "title": "QQ经典农场",
                       "frame": ["x":rect.minX,"y":rect.minY,"width":rect.width,"height":rect.height]])
