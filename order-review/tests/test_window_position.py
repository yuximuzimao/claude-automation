from order_review.window_position import panel_geometry_from_browser_bounds, parse_applescript_bounds


def test_panel_geometry_clamps_left_of_browser():
    geometry = panel_geometry_from_browser_bounds((400, 80, 1450, 1000), panel_width=340, panel_height=760)

    assert geometry == "340x760+52+80"


def test_panel_geometry_clamps_to_screen_left_edge():
    geometry = panel_geometry_from_browser_bounds((200, 80, 1450, 1000), panel_width=340, panel_height=760)

    assert geometry == "340x760+0+80"


def test_parse_applescript_bounds():
    assert parse_applescript_bounds("313, 40, 1763, 1191") == (313, 40, 1763, 1191)
