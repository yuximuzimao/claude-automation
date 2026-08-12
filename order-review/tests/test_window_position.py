from types import SimpleNamespace

import order_review.window_position as window_position
from order_review.window_position import (
    ChromeActiveTab,
    ChromeAccessibilityWindow,
    ChromeWindowState,
    browser_companion_should_be_visible,
    get_chrome_window_state,
    panel_geometry_from_browser_bounds,
    parse_accessibility_state,
    parse_accessibility_window_list,
    parse_applescript_active_tab,
    parse_applescript_bounds,
    parse_applescript_state,
    select_primary_chrome_window,
)


def test_panel_geometry_clamps_left_of_browser():
    geometry = panel_geometry_from_browser_bounds((400, 80, 1450, 1000), panel_width=340, panel_height=760)

    assert geometry == "340x760+52+80"


def test_panel_geometry_clamps_to_screen_left_edge():
    geometry = panel_geometry_from_browser_bounds((200, 80, 1450, 1000), panel_width=340, panel_height=760)

    assert geometry == "340x760+0+80"


def test_panel_geometry_can_match_browser_height():
    geometry = panel_geometry_from_browser_bounds(
        (400, 80, 1450, 1000),
        panel_width=360,
    )

    assert geometry == "360x920+32+80"


def test_parse_applescript_bounds():
    assert parse_applescript_bounds("313, 40, 1763, 1191") == (313, 40, 1763, 1191)


def test_parse_applescript_state_reads_bounds_and_minimized_flag():
    assert parse_applescript_state("313,40,1763,1191,false") == ChromeWindowState(
        bounds=(313, 40, 1763, 1191),
        minimized=False,
    )
    assert parse_applescript_state("313,40,1763,1191,true") == ChromeWindowState(
        bounds=(313, 40, 1763, 1191),
        minimized=True,
    )


def test_parse_applescript_state_handles_missing_window():
    assert parse_applescript_state("missing") is None


def test_parse_accessibility_state_converts_position_and_size_to_bounds():
    assert parse_accessibility_state(
        "912,90,1450,1191,false"
    ) == ChromeWindowState(
        bounds=(912, 90, 2362, 1281),
        minimized=False,
    )
    assert parse_accessibility_state("missing") is None


def test_accessibility_state_includes_frontmost_process():
    assert parse_accessibility_state(
        "912,90,1450,1191,false\x1fWeChat\x1f204"
    ) == ChromeWindowState(
        bounds=(912, 90, 2362, 1281),
        minimized=False,
        frontmost_process_name="WeChat",
        frontmost_process_id=204,
    )


def test_primary_chrome_window_ignores_front_confirmation_dialog():
    dialog = ChromeAccessibilityWindow(
        bounds=(1200, 400, 1680, 720),
        minimized=False,
        title="确认执行操作",
        subrole="AXDialog",
    )
    browser = ChromeAccessibilityWindow(
        bounds=(1005, 85, 2455, 1276),
        minimized=False,
        title="鲸灵商家后台 - Google Chrome",
        subrole="AXStandardWindow",
    )

    assert select_primary_chrome_window([dialog, browser]) == browser


def test_accessibility_window_list_keeps_main_browser_bounds_with_dialog():
    output = (
        "Google Chrome\x1f2585\x1f"
        "1200,400,480,320,false\x1d确认执行操作\x1dAXDialog\x1e"
        "1005,85,1450,1191,false\x1d鲸灵商家后台 - Google Chrome"
        "\x1dAXStandardWindow"
    )

    assert parse_accessibility_window_list(output) == ChromeWindowState(
        bounds=(1005, 85, 2455, 1276),
        minimized=False,
        frontmost_process_name="Google Chrome",
        frontmost_process_id=2585,
    )


def test_browser_companion_visibility_tracks_frontmost_context():
    chrome_front = ChromeWindowState(
        bounds=(1, 2, 3, 4),
        minimized=False,
        frontmost_process_name="Google Chrome",
        frontmost_process_id=2585,
    )
    companion_front = ChromeWindowState(
        bounds=(1, 2, 3, 4),
        minimized=False,
        frontmost_process_name="python3.13",
        frontmost_process_id=68247,
    )
    other_front = ChromeWindowState(
        bounds=(1, 2, 3, 4),
        minimized=False,
        frontmost_process_name="WeChat",
        frontmost_process_id=204,
    )

    assert browser_companion_should_be_visible(
        chrome_front,
        companion_process_id=68247,
    )
    assert browser_companion_should_be_visible(
        companion_front,
        companion_process_id=68247,
    )
    assert not browser_companion_should_be_visible(
        other_front,
        companion_process_id=68247,
    )
    assert not browser_companion_should_be_visible(
        ChromeWindowState(
            bounds=(1, 2, 3, 4),
            minimized=True,
            frontmost_process_name="Google Chrome",
            frontmost_process_id=2585,
        ),
        companion_process_id=68247,
    )


def test_window_state_falls_back_when_chrome_applescript_reports_missing(
    monkeypatch,
):
    outputs = iter(
        (
            "missing\n",
            "Google Chrome\x1f2585\x1f"
            "912,90,1450,1191,false\x1d快麦ERP - Google Chrome"
            "\x1dAXStandardWindow\n",
        )
    )
    monkeypatch.setattr(
        window_position.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout=next(outputs)),
    )

    assert get_chrome_window_state() == ChromeWindowState(
        bounds=(912, 90, 2362, 1281),
        minimized=False,
        frontmost_process_name="Google Chrome",
        frontmost_process_id=2585,
    )


def test_parse_applescript_active_tab():
    assert parse_applescript_active_tab(
        "快麦ERP--待审核订单\x1fhttps://erpb.superboss.cc/index.html#/trade/toaudit/"
    ) == ChromeActiveTab(
        title="快麦ERP--待审核订单",
        url="https://erpb.superboss.cc/index.html#/trade/toaudit/",
    )
    assert parse_applescript_active_tab("missing") is None
