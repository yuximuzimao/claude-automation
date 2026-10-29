import Foundation
import CoreGraphics

struct Bounds {
    let x: Double
    let y: Double
    let width: Double
    let height: Double
}

func windows(owner targetOwner: String) -> [(name: String, bounds: Bounds)] {
    let opts: CGWindowListOption = [.optionOnScreenOnly, .excludeDesktopElements]
    guard let list = CGWindowListCopyWindowInfo(opts, kCGNullWindowID) as? [[String: Any]] else {
        return []
    }
    return list.compactMap { item in
        let owner = item[kCGWindowOwnerName as String] as? String ?? ""
        let name = item[kCGWindowName as String] as? String ?? ""
        let layer = item[kCGWindowLayer as String] as? Int ?? -1
        guard owner == targetOwner, layer == 0,
              let raw = item[kCGWindowBounds as String] as? [String: Any],
              let x = raw["X"] as? Double,
              let y = raw["Y"] as? Double,
              let width = raw["Width"] as? Double,
              let height = raw["Height"] as? Double else {
            return nil
        }
        return (name, Bounds(x: x, y: y, width: width, height: height))
    }
}

func click(_ p: CGPoint) {
    guard let move = CGEvent(mouseEventSource: nil, mouseType: .mouseMoved, mouseCursorPosition: p, mouseButton: .left),
          let down = CGEvent(mouseEventSource: nil, mouseType: .leftMouseDown, mouseCursorPosition: p, mouseButton: .left),
          let up = CGEvent(mouseEventSource: nil, mouseType: .leftMouseUp, mouseCursorPosition: p, mouseButton: .left) else {
        fputs("failed to create CGEvent\n", stderr)
        exit(3)
    }
    move.post(tap: .cghidEventTap)
    usleep(180_000)
    down.post(tap: .cghidEventTap)
    usleep(90_000)
    up.post(tap: .cghidEventTap)
}

func fullFarmWindow() -> Bounds? {
    windows(owner: "QQ小程序").first {
        $0.name == "QQ经典农场" && $0.bounds.width >= 500 && $0.bounds.height >= 900
    }?.bounds
}

func smallFarmTile() -> Bounds? {
    windows(owner: "QQ小程序").first {
        $0.name == "QQ经典农场" && $0.bounds.width < 300 && $0.bounds.height < 300
    }?.bounds
}

func mainQQWindow() -> Bounds? {
    windows(owner: "QQ").first {
        $0.bounds.width >= 1000 && $0.bounds.height >= 800
    }?.bounds
}

let scriptURL = URL(fileURLWithPath: #filePath)
let root = scriptURL.deletingLastPathComponent().deletingLastPathComponent()
let layoutURL = root.appendingPathComponent("data/ui-layout.json")
let rawData = try Data(contentsOf: layoutURL)
guard let rootJSON = try JSONSerialization.jsonObject(with: rawData) as? [String: Any],
      let platforms = rootJSON["platforms"] as? [String: Any],
      let qq = platforms["qq"] as? [String: Any],
      let entry = qq["main_window_entry"] as? [String: Any],
      let baseline = entry["baseline_window_size"] as? [Double],
      let center = entry["farm_icon_center"] as? [Double],
      baseline.count == 2, center.count == 2 else {
    fputs("无法读取 data/ui-layout.json 的 QQ 主窗口入口配置\n", stderr)
    exit(2)
}

if fullFarmWindow() != nil {
    print("QQ经典农场窗口已在前台")
    exit(0)
}

if let tile = smallFarmTile() {
    click(CGPoint(x: tile.x + tile.width / 2, y: tile.y + tile.height / 2))
    for _ in 0..<8 {
        usleep(250_000)
        if fullFarmWindow() != nil {
            print("已从现有 QQ经典农场 Stage Manager 缩略窗恢复农场")
            exit(0)
        }
    }
    fputs("QQ经典农场缩略窗点击后未恢复；停止，不猜坐标\n", stderr)
    exit(4)
}

var main = mainQQWindow()
if main == nil,
   let qqTile = windows(owner: "QQ").first(where: { $0.bounds.width < 300 && $0.bounds.height < 300 })?.bounds {
    click(CGPoint(x: qqTile.x + qqTile.width / 2, y: qqTile.y + qqTile.height / 2))
    usleep(800_000)
    main = mainQQWindow()
}

guard let window = main else {
    fputs("未找到 QQ 主窗口；停止，不猜坐标\n", stderr)
    exit(2)
}

guard abs(window.width - baseline[0]) <= 40,
      abs(window.height - baseline[1]) <= 40 else {
    fputs("QQ 主窗口尺寸不符合已验证基线：\(Int(window.width))×\(Int(window.height))；停止，不缩放猜坐标\n", stderr)
    exit(2)
}

click(CGPoint(x: window.x + center[0], y: window.y + center[1]))

for _ in 0..<12 {
    usleep(250_000)
    if fullFarmWindow() != nil {
        print("已通过 QQ 主窗口固定相对坐标 (\(Int(center[0])),\(Int(center[1]))) 打开 QQ经典农场")
        exit(0)
    }
}

fputs("已点击 QQ 主窗口固定农场入口，但未检测到完整农场窗口；停止，不改走更多功能\n", stderr)
exit(4)
