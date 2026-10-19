from __future__ import annotations

import scripts.build_route_display as build_route_display


def test_program_lookup_ignores_retired_programs(monkeypatch) -> None:
    monkeypatch.setattr(
        build_route_display,
        "load_all_route_programs",
        lambda **_: {
            "retired-program": {"profile_ids": ["icecrown-fivebox"], "status": "retired"},
            "active-program": {"profile_ids": ["icecrown-fivebox"], "status": "active"},
        },
    )

    assert build_route_display._program_id_for_profile("icecrown-fivebox") == "active-program"


def test_program_lookup_treats_retired_only_membership_as_standalone(monkeypatch) -> None:
    monkeypatch.setattr(
        build_route_display,
        "load_all_route_programs",
        lambda **_: {
            "retired-program": {"profile_ids": ["icecrown-fivebox"], "status": "retired"},
        },
    )

    assert build_route_display._program_id_for_profile("icecrown-fivebox") is None
