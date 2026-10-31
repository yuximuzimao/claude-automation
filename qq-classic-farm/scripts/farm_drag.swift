// Guarded single drag for the existing farm seed shop/warehouse scroll.
// Only one local gesture; no automatic retries or screen interpretation.
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
struct Drag: Decodable {
    let window_id: Int
    let pid: Int
    let owner: String
    let title: String
    let frame: Frame
    let from_x: Double
    let from_y: Double
    let to_x: Double
    let to_y: Double
    let steps: Int
}
func stop(_ code: String, _ message: String) -> Never {
    let body: [String: Any] = ["status":"stopped","code":code,"message":message]
    if let data = try? JSONSerialization.data(withJSONObject: body),
       let text = String(data:data,encoding:.utf8) { print(text) }
    exit(2)
}
func allowedNow() -> Bool {
    let c = Calendar.current.dateComponents([.hour,.minute],from:Date())
    guard let h = c.hour, let m = c.minute else { return false }
    let t = h*60+m
    return ![(0,60),(480,540),(720,780),(840,845),(960,1020),(1200,1260)]
        .contains { t >= $0.0 && t < $0.1 }
}
func safeHit(_ d: Drag, _ point: CGPoint) {
    guard let list = CGWindowListCopyWindowInfo(
        [.optionOnScreenOnly,.excludeDesktopElements],kCGNullWindowID
    ) as? [[String:Any]] else {
        stop("WINDOW_NOT_FOUND","Cannot enumerate windows")
    }
    for info in list {
        let alpha = info[kCGWindowAlpha as String] as? Double ?? 1
        guard alpha > 0.01,
              let b = info[kCGWindowBounds as String] as? [String:Any],
              let x = b["X"] as? Double, let y = b["Y"] as? Double,
              let w = b["Width"] as? Double, let h = b["Height"] as? Double else { continue }
        let rect = CGRect(x:x,y:y,width:w,height:h)
        guard rect.contains(point) else { continue }
        if (info[kCGWindowNumber as String] as? Int) == d.window_id { return }
        let owner = info[kCGWindowOwnerName as String] as? String ?? ""
        let layer = info[kCGWindowLayer as String] as? Int ?? -1
        let passThrough = ((owner == "程序坞" || owner == "Dock") && layer == 20)
            || ((owner == "通知中心" || owner == "Notification Center") && layer == 21)
        if passThrough {
            let screen = CGDisplayBounds(CGMainDisplayID())
            if abs(rect.minX-screen.minX) <= 2 && abs(rect.minY-screen.minY) <= 2
                && abs(rect.width-screen.width) <= 2 && abs(rect.height-screen.height) <= 2 {
                let system = AXUIElementCreateSystemWide()
                var element: AXUIElement?
                if AXUIElementCopyElementAtPosition(system,Float(point.x),
                    Float(point.y),&element) == .success,let hit = element {
                    var pid: pid_t = 0
                    if AXUIElementGetPid(hit,&pid) == .success && pid == pid_t(d.pid) {
                        continue
                    }
                }
            }
        }
        stop("WINDOW_OCCLUDED","Visible window covers drag path")
    }
    stop("WINDOW_OCCLUDED","Farm window not topmost at drag point")
}
func check(_ d: Drag) {
    guard allowedNow() else { stop("FARM_OPERATION_TIME_BLOCKED","Mac local blackout") }
    guard NSWorkspace.shared.frontmostApplication?.processIdentifier == pid_t(d.pid) else {
        stop("WRONG_FRONTMOST_APP","Target farm is not frontmost")
    }
    guard let list = CGWindowListCopyWindowInfo(
        [.optionOnScreenOnly,.excludeDesktopElements],kCGNullWindowID
    ) as? [[String:Any]],
    let info = list.first(where: { ($0[kCGWindowNumber as String] as? Int) == d.window_id }),
    (info[kCGWindowOwnerPID as String] as? Int) == d.pid,
    (info[kCGWindowOwnerName as String] as? String) == d.owner,
    (info[kCGWindowName as String] as? String) == d.title,
    let bounds = info[kCGWindowBounds as String] as? [String:Any],
    let x = bounds["X"] as? Double, let y = bounds["Y"] as? Double,
    let w = bounds["Width"] as? Double, let h = bounds["Height"] as? Double,
    abs(x-d.frame.x)<1,abs(y-d.frame.y)<1,
    abs(w-d.frame.width)<1,abs(h-d.frame.height)<1 else {
        stop("WINDOW_CHANGED","Farm identity or frame changed")
    }
}
guard CommandLine.arguments.count == 2,
      ["--preflight","--execute"].contains(CommandLine.arguments[1]) else {
    stop("INVALID_ARGUMENT","Use --preflight or --execute")
}
let execute = CommandLine.arguments[1] == "--execute"
guard let d = try? JSONDecoder().decode(
    Drag.self,from:FileHandle.standardInput.readDataToEndOfFile()
) else { stop("INVALID_DRAG","Invalid JSON drag request") }
guard d.window_id > 0,d.pid > 0,d.title == "QQ经典农场",
      ["QQ小程序","微信","WeChat"].contains(d.owner),
      (8...32).contains(d.steps),
      [d.from_x,d.to_x].allSatisfy({ $0 >= 0 && $0 < d.frame.width && $0.isFinite }),
      [d.from_y,d.to_y].allSatisfy({ $0 >= 0 && $0 < d.frame.height && $0.isFinite }),
      hypot(d.from_x-d.to_x,d.from_y-d.to_y) <= 650 else {
    stop("INVALID_DRAG","Invalid farm identity or drag geometry")
}
check(d)
let from = CGPoint(x:d.frame.x+d.from_x,y:d.frame.y+d.from_y)
let to = CGPoint(x:d.frame.x+d.to_x,y:d.frame.y+d.to_y)
let midpoint = CGPoint(x:(from.x+to.x)/2,y:(from.y+to.y)/2)
for point in [from,midpoint,to] { safeHit(d,point) }
if !execute {
    print("{\"status\":\"preflight_ok_no_input\",\"events_sent\":0}")
    exit(0)
}
guard CGPreflightPostEventAccess() else {
    stop("ACCESSIBILITY_PERMISSION_MISSING","CGEvent posting not permitted")
}
guard let down = CGEvent(mouseEventSource:nil,mouseType:.leftMouseDown,
                         mouseCursorPosition:from,mouseButton:.left) else {
    stop("CGEVENT_FAILED","Cannot construct mouse down")
}
down.post(tap:.cghidEventTap)
var sent = 1
for i in 1...d.steps {
    // The drag is one bounded gesture; recheck focus, clock and window for
    // every motion segment, and always release the button on STOP.
    if !allowedNow() ||
        NSWorkspace.shared.frontmostApplication?.processIdentifier != pid_t(d.pid) {
        let up = CGEvent(mouseEventSource:nil,mouseType:.leftMouseUp,
                         mouseCursorPosition:from,mouseButton:.left)
        up?.post(tap:.cghidEventTap)
        stop("DRAG_PARTIAL_UNCERTAIN","Clock/focus changed during drag; do not retry")
    }
    let f = Double(i)/Double(d.steps)
    let p = CGPoint(x:from.x+(to.x-from.x)*f,y:from.y+(to.y-from.y)*f)
    guard let drag = CGEvent(mouseEventSource:nil,mouseType:.leftMouseDragged,
                             mouseCursorPosition:p,mouseButton:.left) else {
        // A failed motion must not leave the system mouse button held.
        let release = CGEvent(mouseEventSource:nil,mouseType:.leftMouseUp,
                              mouseCursorPosition:p,mouseButton:.left)
        release?.post(tap:.cghidEventTap)
        stop("DRAG_PARTIAL_UNCERTAIN","Cannot construct drag event")
    }
    drag.post(tap:.cghidEventTap)
    sent += 1
    usleep(25_000)
}
let up = CGEvent(mouseEventSource:nil,mouseType:.leftMouseUp,
                 mouseCursorPosition:to,mouseButton:.left)
up?.post(tap:.cghidEventTap)
check(d) // Release first; an end-of-gesture STOP must not leave mouse held.
print("{\"status\":\"drag_sent_unverified\",\"events_sent\":\(sent+1)}")
