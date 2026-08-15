import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/route-atlas/workbench-routes.json"
HTML = ROOT / "data/routes/route-atlas-workbench.html"


def test_workbench_contains_all_current_route_maps_and_assets():
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    assert set(routes) >= {"zang", "nagrand", "borean"}
    assert len(routes["borean"]["points"]) == 222
    for route in routes.values():
        assert route["points"]
        assert (ROOT / "data/routes" / route["image"]).exists()


def test_route_text_never_leaks_internal_action_tokens():
    routes = json.loads(DATA.read_text(encoding="utf-8"))
    visible = "\n".join(
        str(value)
        for route in routes.values()
        for point in route["points"]
        for value in point[2:6]
    )
    assert not re.search(
        r"(?<![A-Za-z])(?:A|C|T|A/T|C/T|C_partial|SCRIPT)\d{4,5}", visible
    )


def test_single_workbench_uses_established_outland_layout_and_manual_follow():
    html = HTML.read_text(encoding="utf-8")
    for required in (
        'class="top"',
        'class="badge"',
        'class="controls"',
        'class="shell"',
        'class="hud"',
        'class="card legend"',
        'class="card stepsCard"',
    ):
        assert required in html
    assert '<input id="follow" type="checkbox"> 跟随当前段' in html
    assert "if(!document.getElementById('follow').checked||i<=0)return" in html
    assert 'const ROUTES=/* ROUTE_DATA_START */' in html
    assert '/* ROUTE_DATA_END */;' in html


def test_deprecated_route_atlas_htmls_are_not_kept_in_routes_directory():
    forbidden = {
        "outland-route-atlas.html",
        "zangarmarsh-authoritative-v2.html",
        "zangarmarsh-current-remaining-route.html",
        "zangarmarsh-final-reusable-route-preview.html",
        "zangarmarsh-r11-route-preview.html",
        "zangarmarsh-route-atlas-prototype.html",
        "borean-tundra-leveling-clear-v1-preview.html",
        "borean-tundra-partial-r6-preview.html",
    }
    existing = {p.name for p in (ROOT / "data/routes").glob("*.html")}
    assert forbidden.isdisjoint(existing)
    assert HTML.name in existing
