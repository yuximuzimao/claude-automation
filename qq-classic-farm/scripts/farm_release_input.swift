// Bounded cleanup after this farm's input process group has been terminated.
import Foundation
import CoreGraphics

if CommandLine.arguments.dropFirst().first == "--validate" && CommandLine.arguments.count == 2 {
    print("validated_no_input")
    exit(0)
}
guard CommandLine.arguments.count == 2, CommandLine.arguments[1] == "--release-left" else {
    fputs("Use --release-left or --validate\n", stderr)
    exit(2)
}
if CGEventSource.buttonState(.combinedSessionState, button: .left) {
    guard CGPreflightPostEventAccess(), let position = CGEvent(source: nil)?.location,
          let up = CGEvent(mouseEventSource: nil, mouseType: .leftMouseUp,
                           mouseCursorPosition: position, mouseButton: .left) else {
        fputs("LEFT_RELEASE_UNAVAILABLE\n", stderr)
        exit(2)
    }
    up.post(tap: .cghidEventTap)
    usleep(50_000)
    guard !CGEventSource.buttonState(.combinedSessionState, button: .left) else {
        fputs("LEFT_BUTTON_STILL_DOWN\n", stderr)
        exit(2)
    }
}
print("left_button_released")
