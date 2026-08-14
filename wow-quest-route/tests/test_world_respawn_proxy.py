import json

from lib.world_respawn_proxy import WorldRespawnProxy


def test_respawn_proxy_aggregates_spawn_rows_and_median(tmp_path):
    path = tmp_path / "respawn.json"
    path.write_text(
        json.dumps(
            {
                "meta": {"source_project": "cmangos/tbc-db", "source_revision": "abc123"},
                "gameobjects": {
                    "182069": {
                        "spawns": [
                            {"guid": 1, "respawn_seconds": 300},
                            {"guid": 2, "respawn_seconds": 600},
                        ]
                    },
                    "182070": {"spawns": [{"guid": 3, "respawn_seconds": 300}]},
                },
                "creatures": {},
            }
        ),
        encoding="utf-8",
    )
    proxy = WorldRespawnProxy(path)
    result = proxy.gameobjects([182069, 182070])
    assert result is not None
    assert result.spawn_rows == 3
    assert result.values_seconds == (300.0, 300.0, 600.0)
    assert result.median_seconds == 300.0
    assert result.min_seconds == 300.0
    assert result.max_seconds == 600.0
    assert result.uniform is False
    assert result.source == "cmangos/tbc-db"
    assert result.source_revision == "abc123"


def test_respawn_proxy_preserves_min_max_range_and_uses_midpoint_proxy(tmp_path):
    path = tmp_path / "respawn-range.json"
    path.write_text(
        json.dumps(
            {
                "meta": {"source_project": "cmangos/wotlk-db", "source_revision": "range123"},
                "gameobjects": {
                    "181871": {
                        "spawns": [
                            {
                                "guid": 10,
                                "respawn_seconds": 300,
                                "respawn_seconds_min": 300,
                                "respawn_seconds_max": 600,
                            },
                            {
                                "guid": 11,
                                "respawn_seconds": 300,
                                "respawn_seconds_min": 300,
                                "respawn_seconds_max": 600,
                            },
                        ]
                    }
                },
                "creatures": {},
            }
        ),
        encoding="utf-8",
    )
    result = WorldRespawnProxy(path).gameobjects([181871])
    assert result is not None
    assert result.lower_median_seconds == 300.0
    assert result.median_seconds == 450.0
    assert result.upper_median_seconds == 600.0
    assert result.random_range_rows == 2
    assert result.uniform is False


def test_respawn_proxy_missing_file_is_clean_fallback(tmp_path):
    proxy = WorldRespawnProxy(tmp_path / "missing.json")
    assert proxy.available is False
    assert proxy.gameobjects([182069]) is None
