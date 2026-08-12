from types import SimpleNamespace

from order_review.macos_companion import (
    FrontmostApplication,
    MacOSCompanionWindow,
    companion_should_be_visible,
    get_frontmost_application,
)


class FakeWindow:
    def __init__(self, title: str, behavior: int = 0) -> None:
        self._title = title
        self.behavior = behavior
        self.hides_on_deactivate = True
        self.can_hide = True
        self.level = 0
        self.actions: list[str] = []

    def title(self):
        return self._title

    def collectionBehavior(self):
        return self.behavior

    def setCollectionBehavior_(self, behavior):
        self.behavior = behavior

    def setHidesOnDeactivate_(self, value):
        self.hides_on_deactivate = value

    def setCanHide_(self, value):
        self.can_hide = value

    def setLevel_(self, value):
        self.level = value

    def orderFront_(self, _sender):
        self.actions.append("show")

    def orderOut_(self, _sender):
        self.actions.append("hide")


def _fake_appkit(window: FakeWindow):
    application = SimpleNamespace(
        windows=lambda: [window],
        setActivationPolicy_=lambda value: window.actions.append(
            f"policy:{value}"
        ),
    )
    return SimpleNamespace(
        NSApp=application,
        NSWindowCollectionBehaviorCanJoinAllSpaces=1,
        NSWindowCollectionBehaviorCanJoinAllApplications=262144,
        NSWindowCollectionBehaviorFullScreenAuxiliary=256,
        NSWindowCollectionBehaviorTransient=8,
        NSApplicationActivationPolicyAccessory=1,
        NSFloatingWindowLevel=3,
    )


def test_reads_frontmost_application_from_native_workspace():
    application = SimpleNamespace(
        localizedName=lambda: "Google Chrome",
        processIdentifier=lambda: 2585,
    )
    appkit = SimpleNamespace(
        NSWorkspace=SimpleNamespace(
            sharedWorkspace=lambda: SimpleNamespace(
                frontmostApplication=lambda: application
            )
        )
    )

    assert get_frontmost_application(lambda: appkit) == FrontmostApplication(
        name="Google Chrome",
        process_id=2585,
    )


def test_companion_visibility_accepts_chrome_or_its_own_process():
    assert companion_should_be_visible(
        FrontmostApplication("Google Chrome", 2585),
        companion_process_id=99,
    )
    assert companion_should_be_visible(
        FrontmostApplication("Python", 99),
        companion_process_id=99,
    )
    assert not companion_should_be_visible(
        FrontmostApplication("WeChat", 513),
        companion_process_id=99,
    )


def test_native_companion_configures_and_orders_window_without_activation():
    window = FakeWindow("审单悬浮窗", behavior=64)
    companion = MacOSCompanionWindow(
        "审单悬浮窗",
        appkit_loader=lambda: _fake_appkit(window),
    )

    assert companion.set_visible(False)
    assert companion.set_visible(True)
    assert window.behavior == 64 | 1 | 8 | 256 | 262144
    assert window.hides_on_deactivate is False
    assert window.can_hide is False
    assert window.level == 3
    assert window.actions == ["policy:1", "hide", "show"]
