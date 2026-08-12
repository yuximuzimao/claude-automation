from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Callable


@dataclass(frozen=True)
class FrontmostApplication:
    name: str
    process_id: int


def _load_appkit() -> Any:
    import AppKit

    return AppKit


def get_frontmost_application(
    appkit_loader: Callable[[], Any] = _load_appkit,
) -> FrontmostApplication | None:
    """通过 macOS 原生接口读取前台应用，不启动 AppleScript 子进程。"""
    try:
        application = (
            appkit_loader().NSWorkspace.sharedWorkspace().frontmostApplication()
        )
        if application is None:
            return None
        return FrontmostApplication(
            name=str(application.localizedName() or ""),
            process_id=int(application.processIdentifier()),
        )
    except Exception:
        return None


def companion_should_be_visible(
    frontmost: FrontmostApplication,
    *,
    companion_process_id: int | None = None,
) -> bool:
    if companion_process_id is None:
        companion_process_id = os.getpid()
    return (
        frontmost.name == "Google Chrome"
        or frontmost.process_id == companion_process_id
    )


class MacOSCompanionWindow:
    """把 Tk 窗口作为不抢焦点、可跨空间出现的 Chrome 伴随窗口。"""

    def __init__(
        self,
        title: str,
        appkit_loader: Callable[[], Any] = _load_appkit,
    ) -> None:
        self.title = title
        self._appkit_loader = appkit_loader
        self._window: Any | None = None
        self._configured = False

    def _find_window(self) -> tuple[Any, Any] | None:
        try:
            appkit = self._appkit_loader()
            if self._window is not None and str(self._window.title()) == self.title:
                return appkit, self._window
            for window in appkit.NSApp.windows():
                if str(window.title()) == self.title:
                    self._window = window
                    return appkit, window
        except Exception:
            return None
        return None

    def configure(self) -> bool:
        found = self._find_window()
        if found is None:
            return False
        appkit, window = found
        try:
            behavior = int(window.collectionBehavior())
            behavior |= int(appkit.NSWindowCollectionBehaviorCanJoinAllSpaces)
            behavior |= int(
                getattr(
                    appkit,
                    "NSWindowCollectionBehaviorCanJoinAllApplications",
                    0,
                )
            )
            behavior |= int(appkit.NSWindowCollectionBehaviorFullScreenAuxiliary)
            behavior |= int(appkit.NSWindowCollectionBehaviorTransient)
            appkit.NSApp.setActivationPolicy_(
                appkit.NSApplicationActivationPolicyAccessory
            )
            window.setCollectionBehavior_(behavior)
            window.setHidesOnDeactivate_(False)
            window.setCanHide_(False)
            window.setLevel_(appkit.NSFloatingWindowLevel)
            self._configured = True
            return True
        except Exception:
            return False

    def set_visible(self, visible: bool) -> bool:
        if not self._configured and not self.configure():
            return False
        found = self._find_window()
        if found is None:
            return False
        _appkit, window = found
        try:
            if visible:
                window.orderFront_(None)
            else:
                window.orderOut_(None)
            return True
        except Exception:
            return False
