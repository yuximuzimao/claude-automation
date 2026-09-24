from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_dk_outland_speed_routes import build_hellfire  # noqa: E402
from normalize_hellfire_task_cards_v1 import normalize  # noqa: E402
from lib.task_cards import load_task_card  # noqa: E402


def test_10208_dk_builder_uses_task_card_projection_not_legacy_fivebox_text() -> None:
    routes = json.loads((ROOT / "data/route-atlas/workbench-routes.json").read_text(encoding="utf-8"))
    route = build_hellfire(routes["hellfire"])

    point = next(point for point in route["points"] if "做《阻断援军》" in str(point[3]))
    assert str(point[8]).strip() == ""

    group = next(group for group in route["stepGroups"] if "阻断援军" in group.get("actionHtml", ""))
    match = re.search(
        r'<div class="ra-note-task">《阻断援军》</div>'
        r'<div class="ra-note-text">(.*?)</div>',
        group.get("noteHtml", ""),
    )
    assert match
    task_body = match.group(1)
    assert "ra-special" in task_body
    assert "已实测" not in task_body
    assert "恶魔符文石" not in task_body


def test_10208_legacy_hardcoded_long_note_is_gone_from_dk_builder_source() -> None:
    source = (ROOT / "scripts/build_dk_outland_speed_routes.py").read_text(encoding="utf-8")
    assert "已实测：恶魔符文石个人拾取" not in source
    assert "load_task_card(10208)" in source
    assert "project_task_presentation" in source


def test_current_task_card_normalizer_is_idempotent_and_preserves_10208_status_and_note() -> None:
    card = load_task_card(10208)
    first = normalize(copy.deepcopy(card))
    second = normalize(copy.deepcopy(first))

    assert first == second
    assert first["fivebox"]["status"] == "special"
    assert first["presentation"]["note_override"]["text"] == ""
