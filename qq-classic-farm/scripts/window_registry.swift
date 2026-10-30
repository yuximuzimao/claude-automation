// M1 read-only on-screen window registry; no focus change and no CGEvent.
import Foundation
import CoreGraphics

struct FarmWindow: Codable {
    let owner: String
    let title: String
    let window_id: Int
    let pid: Int
    let x: Double
    let y: Double
    let width: Double
    let height: Double
}

guard CommandLine.arguments.count == 3,
      CommandLine.arguments[1] == "--platform",
      ["qq", "wechat"].contains(CommandLine.arguments[2]) else {
    fputs("Usage: window_registry --platform qq|wechat\n", stderr)
    exit(2)
}

let platform = CommandLine.arguments[2]
let owners: Set<String> = platform == "qq" ? ["QQ", "QQ小程序"] : ["微信", "WeChat"]
let opts: CGWindowListOption = [.optionOnScreenOnly, .excludeDesktopElements]
guard let raw = CGWindowListCopyWindowInfo(opts, kCGNullWindowID) as? [[String: Any]] else {
    fputs("CGWindowListCopyWindowInfo failed\n", stderr)
    exit(3)
}

let results: [FarmWindow] = raw.compactMap { item in
    let owner = item[kCGWindowOwnerName as String] as? String ?? ""
    let title = item[kCGWindowName as String] as? String ?? ""
    let layer = item[kCGWindowLayer as String] as? Int ?? -1
    guard owners.contains(owner), layer == 0,
          let bounds = item[kCGWindowBounds as String] as? [String: Any],
          let x = bounds["X"] as? Double,
          let y = bounds["Y"] as? Double,
          let width = bounds["Width"] as? Double,
          let height = bounds["Height"] as? Double,
          width > 0, height > 0 else {
        return nil
    }
    let windowID = item[kCGWindowNumber as String] as? Int ?? -1
    let pid = item[kCGWindowOwnerPID as String] as? Int ?? -1
    guard windowID > 0, pid > 0 else { return nil }
    return FarmWindow(owner: owner, title: title, window_id: windowID, pid: pid,
                      x: x, y: y, width: width, height: height)
}

let payload: [String: Any] = [
    "platform": platform,
    "windows": results.map { [
        "owner": $0.owner, "title": $0.title,
        "window_id": $0.window_id, "pid": $0.pid,
        "x": $0.x, "y": $0.y, "width": $0.width, "height": $0.height
    ] }
]
let data = try JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys])
print(String(decoding: data, as: UTF8.self))
