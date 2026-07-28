from order_review.window_position import (
    ChromeActiveTab,
    ChromeWindowState,
    panel_geometry_from_browser_bounds,
    parse_applescript_active_tab,
    parse_applescript_bounds,
    parse_applescript_state,
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


def test_parse_applescript_active_tab():
    assert parse_applescript_active_tab(
        "快麦ERP--待审核订单\x1fhttps://erpb.superboss.cc/index.html#/trade/toaudit/"
    ) == ChromeActiveTab(
        title="快麦ERP--待审核订单",
        url="https://erpb.superboss.cc/index.html#/trade/toaudit/",
    )
    assert parse_applescript_active_tab("missing") is None
