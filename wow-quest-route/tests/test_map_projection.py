from __future__ import annotations

import pytest

from lib.map_projection import MapBounds, full_image_bounds, project_questie_point


def test_projects_full_image_percent_coordinates() -> None:
    bounds = full_image_bounds(1000, 500)

    assert project_questie_point(0, 0, bounds).x == pytest.approx(0)
    assert project_questie_point(0, 0, bounds).y == pytest.approx(0)
    assert project_questie_point(50, 50, bounds).x == pytest.approx(500)
    assert project_questie_point(50, 50, bounds).y == pytest.approx(250)
    assert project_questie_point(100, 100, bounds).x == pytest.approx(1000)
    assert project_questie_point(100, 100, bounds).y == pytest.approx(500)


def test_projects_into_inner_map_bounds() -> None:
    bounds = MapBounds(left=100, top=50, right=900, bottom=450)

    point = project_questie_point(25, 75, bounds)

    assert point.x == pytest.approx(300)
    assert point.y == pytest.approx(350)


def test_does_not_hide_bad_sentinel_coordinates() -> None:
    bounds = full_image_bounds(1000, 500)

    point = project_questie_point(-1, -1, bounds)

    assert point.x == pytest.approx(-10)
    assert point.y == pytest.approx(-5)


def test_rejects_invalid_bounds() -> None:
    with pytest.raises(ValueError):
        project_questie_point(50, 50, MapBounds(10, 10, 10, 20))

    with pytest.raises(ValueError):
        full_image_bounds(0, 500)
