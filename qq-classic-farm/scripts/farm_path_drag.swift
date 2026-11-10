// One held-button gesture through verified land centers. No retries or waypoint clicks.
import AppKit
import ApplicationServices
import CoreGraphics
import Foundation

struct Frame: Decodable { let x: Double; let y: Double; let width: Double; let height: Double }
struct Request: Decodable {
    let window_id: Int; let pid: Int; let owner: String; let title: String
    let frame: Frame; let points: [[Double]]
}
struct Stop: Error { let reason: String }
func require(_ yes: Bool, _ reason: String) throws { if !yes { throw Stop(reason: reason) } }
func windows() -> [[String: Any]] {
    CGWindowListCopyWindowInfo([.optionOnScreenOnly,.excludeDesktopElements],kCGNullWindowID) as? [[String:Any]] ?? []
}
func rect(_ w: [String:Any]) -> CGRect? {
    guard let b=w[kCGWindowBounds as String] as? [String:Any],let x=b["X"] as? Double,
          let y=b["Y"] as? Double,let width=b["Width"] as? Double,let height=b["Height"] as? Double else { return nil }
    return CGRect(x:x,y:y,width:width,height:height)
}
func safe(_ r: Request, _ p: CGPoint) throws {
    try require(NSWorkspace.shared.frontmostApplication?.processIdentifier == pid_t(r.pid),"FOCUS_CHANGED")
    let list=windows()
    guard let target=list.first(where:{($0[kCGWindowNumber as String] as? Int)==r.window_id}),let frame=rect(target) else {throw Stop(reason:"WINDOW_MISSING")}
    try require((target[kCGWindowOwnerPID as String] as? Int)==r.pid &&
                (target[kCGWindowOwnerName as String] as? String)==r.owner &&
                (target[kCGWindowName as String] as? String)==r.title &&
                abs(frame.minX-r.frame.x)<1 && abs(frame.minY-r.frame.y)<1 &&
                frame.width==r.frame.width && frame.height==r.frame.height,"WINDOW_CHANGED")
    for w in list {
        guard (w[kCGWindowAlpha as String] as? Double ?? 1)>0.01,let bounds=rect(w),bounds.contains(p) else {continue}
        if (w[kCGWindowNumber as String] as? Int)==r.window_id {return}
        let owner=w[kCGWindowOwnerName as String] as? String ?? ""
        let layer=w[kCGWindowLayer as String] as? Int ?? -1
        let screen=CGDisplayBounds(CGMainDisplayID())
        let known=(["Dock","程序坞"].contains(owner) && layer==20) || (["Notification Center","通知中心"].contains(owner) && layer==21)
        if known && abs(bounds.minX-screen.minX)<=2 && abs(bounds.minY-screen.minY)<=2 && abs(bounds.width-screen.width)<=2 && abs(bounds.height-screen.height)<=2 {continue}
        throw Stop(reason:"PATH_OCCLUDED")
    }
    throw Stop(reason:"PATH_NOT_VISIBLE")
}
func post(_ type: CGEventType, _ point: CGPoint) throws {
    guard let e=CGEvent(mouseEventSource:nil,mouseType:type,mouseCursorPosition:point,mouseButton:.left) else {throw Stop(reason:"EVENT_FAILED")}
    e.post(tap:.cghidEventTap)
}
var events=0
func gesture(_ r: Request, _ path: [CGPoint]) throws {
    var held=false
    var last=path[0]
    // Even when a later guard fails, release at the last posted location before reporting failure.
    defer {if held {try? post(.leftMouseUp,last)}}
    for p in path {try safe(r,p)}
    try post(.leftMouseDown,path[0]);held=true;events+=1;usleep(150_000)
    for i in 1..<path.count {
        let start=path[i-1],end=path[i]
        for step in 1...8 {
            let f=Double(step)/8
            let p=CGPoint(x:start.x+(end.x-start.x)*f,y:start.y+(end.y-start.y)*f)
            try safe(r,p)
            try post(.leftMouseDragged,p);last=p;events+=1;usleep(25_000)
        }
    }
    try post(.leftMouseUp,last);held=false;events+=1
}
let mode=CommandLine.arguments.dropFirst().first ?? "--validate"
do {
    try require(CommandLine.arguments.count<=2 && ["--validate","--preflight","--execute","--release"].contains(mode),"INVALID_MODE")
    let r=try JSONDecoder().decode(Request.self,from:FileHandle.standardInput.readDataToEndOfFile())
    try require(r.owner=="QQ小程序" && r.title=="QQ经典农场" && r.pid>0 && r.window_id>0,"INVALID_TARGET")
    try require(r.frame.width==603 && r.frame.height==1111 && r.frame.x.isFinite && r.frame.y.isFinite,"INVALID_FRAME")
    try require(r.points.count==25 && r.points.allSatisfy{$0.count==2 && $0[0].isFinite && $0[1].isFinite && $0[0]>=0 && $0[0]<603 && $0[1]>=0 && $0[1]<1111},"INVALID_PATH")
    let path=r.points.map{CGPoint(x:r.frame.x+$0[0],y:r.frame.y+$0[1])}
    if mode=="--validate" { print("{\"status\":\"validated_no_input\",\"events_sent\":0}");exit(0) }
    try require(CGPreflightPostEventAccess(),"INPUT_PERMISSION_MISSING")
    if mode=="--release" {
        guard let point=CGEvent(source:nil)?.location else {throw Stop(reason:"CURSOR_UNAVAILABLE")}
        try post(.leftMouseUp,point);print("{\"status\":\"mouse_released\"}");exit(0)
    }
    if mode=="--preflight" {
        for p in path {try safe(r,p)}
        print("{\"status\":\"preflight_ok_no_input\",\"events_sent\":0}");exit(0)
    }
    try gesture(r,path)
    print("{\"status\":\"path_drag_sent_unverified\",\"events_sent\":\(events)}")
} catch {
    let reason=(error as? Stop)?.reason ?? String(describing:error)
    let data=try! JSONSerialization.data(withJSONObject:["status":"stopped","reason":reason,"events_sent":events])
    print(String(decoding:data,as:UTF8.self));exit(2)
}
