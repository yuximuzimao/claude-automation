from __future__ import annotations

raise SystemExit(
    "RETIRED: this legacy Route Atlas flight-state audit inferred system flights and opened hubs "
    "from workbench point text plus point[6] transport metadata. Stage 3 Route Replay now owns "
    "open_flight_point/taxi legality from structured Route Profile actions and actual RouteState; "
    "Stage 5 owns canonical movement edges. Do not revive the old text/transport inference path. "
    "Use scripts/rebuild_route_profile.py and the Stage 3/5 reports instead."
)
