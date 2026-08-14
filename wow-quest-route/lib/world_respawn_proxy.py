from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class RespawnAggregate:
    entity_kind: str
    entry_ids: tuple[int, ...]
    spawn_rows: int
    # Per-spawn point estimate. If the source row carries a min/max range, the
    # point estimate is its midpoint. This is an explicit proxy assumption, not
    # a claim about Titan or about the exact server-side random distribution.
    values_seconds: tuple[float, ...]
    lower_values_seconds: tuple[float, ...]
    upper_values_seconds: tuple[float, ...]
    min_seconds: float | None
    median_seconds: float | None
    max_seconds: float | None
    lower_median_seconds: float | None
    upper_median_seconds: float | None
    uniform: bool
    random_range_rows: int
    source: str
    source_revision: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "entity_kind": self.entity_kind,
            "entry_ids": list(self.entry_ids),
            "spawn_rows": self.spawn_rows,
            "values_seconds": list(self.values_seconds),
            "lower_values_seconds": list(self.lower_values_seconds),
            "upper_values_seconds": list(self.upper_values_seconds),
            "min_seconds": self.min_seconds,
            "median_seconds": self.median_seconds,
            "max_seconds": self.max_seconds,
            "lower_median_seconds": self.lower_median_seconds,
            "upper_median_seconds": self.upper_median_seconds,
            "uniform": self.uniform,
            "random_range_rows": self.random_range_rows,
            "point_estimate_policy": "per_spawn_midpoint_then_median",
            "source": self.source,
            "source_revision": self.source_revision,
        }


class WorldRespawnProxy:
    """Read-only adapter for an externally extracted world DB respawn snapshot.

    Expected file shape::

        {
          "meta": {
            "source_project": "cmangos/tbc-db",
            "source_revision": "<commit sha>",
            "client": "2.4.3"
          },
          "gameobjects": {
            "182069": {
              "spawns": [
                {"guid": 123, "respawn_seconds": 300}
              ]
            }
          },
          "creatures": {
            "18138": {
              "spawns": [
                {"guid": 456, "respawn_seconds": 300}
              ]
            }
          }
        }

    Route Atlas deliberately computes aggregates itself so the extractor remains a simple
    evidence exporter rather than embedding task-specific business logic.
    """

    def __init__(self, path: Path | str):
        self.path = Path(path)
        if self.path.exists():
            self.payload = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.payload = {"meta": {}, "gameobjects": {}, "creatures": {}}

    @property
    def available(self) -> bool:
        return self.path.exists()

    @property
    def meta(self) -> dict[str, Any]:
        value = self.payload.get("meta")
        return value if isinstance(value, dict) else {}

    def _rows_for(self, collection: str, entry_ids: Iterable[int]) -> list[dict[str, Any]]:
        table = self.payload.get(collection)
        if not isinstance(table, dict):
            return []
        rows: list[dict[str, Any]] = []
        seen: set[tuple[int, Any]] = set()
        for entry_id in sorted({int(v) for v in entry_ids}):
            entry = table.get(str(entry_id)) or table.get(entry_id)
            if not isinstance(entry, dict):
                continue
            for spawn in entry.get("spawns") or []:
                if not isinstance(spawn, dict):
                    continue
                guid = spawn.get("guid")
                key = (entry_id, guid)
                if key in seen:
                    continue
                seen.add(key)
                rows.append({"entry_id": entry_id, **spawn})
        return rows

    def aggregate(self, entity_kind: str, entry_ids: Iterable[int]) -> RespawnAggregate | None:
        collection = "gameobjects" if entity_kind == "gameobject" else "creatures"
        ids = tuple(sorted({int(v) for v in entry_ids}))
        rows = self._rows_for(collection, ids)
        lowers: list[float] = []
        uppers: list[float] = []
        points: list[float] = []
        random_range_rows = 0
        for row in rows:
            raw = row.get("respawn_seconds")
            raw_min = row.get("respawn_seconds_min", raw)
            raw_max = row.get("respawn_seconds_max", raw)
            if not isinstance(raw_min, (int, float)) or not isinstance(raw_max, (int, float)):
                continue
            lower = float(raw_min)
            upper = float(raw_max)
            if lower < 0 or upper < 0:
                continue
            if upper < lower:
                lower, upper = upper, lower
            if upper != lower:
                random_range_rows += 1
            lowers.append(lower)
            uppers.append(upper)
            points.append((lower + upper) / 2.0)
        if not points:
            return None
        ordered = tuple(sorted(points))
        lower_ordered = tuple(sorted(lowers))
        upper_ordered = tuple(sorted(uppers))
        min_seconds = min(lower_ordered)
        median_seconds = float(statistics.median(ordered))
        max_seconds = max(upper_ordered)
        lower_median_seconds = float(statistics.median(lower_ordered))
        upper_median_seconds = float(statistics.median(upper_ordered))
        source_project = str(self.meta.get("source_project") or "external_world_db")
        source_revision = self.meta.get("source_revision")
        return RespawnAggregate(
            entity_kind=entity_kind,
            entry_ids=ids,
            spawn_rows=len(rows),
            values_seconds=ordered,
            lower_values_seconds=lower_ordered,
            upper_values_seconds=upper_ordered,
            min_seconds=min_seconds,
            median_seconds=median_seconds,
            max_seconds=max_seconds,
            lower_median_seconds=lower_median_seconds,
            upper_median_seconds=upper_median_seconds,
            uniform=random_range_rows == 0 and min(ordered) == max(ordered),
            random_range_rows=random_range_rows,
            source=source_project,
            source_revision=str(source_revision) if source_revision is not None else None,
        )

    def gameobjects(self, entry_ids: Iterable[int]) -> RespawnAggregate | None:
        return self.aggregate("gameobject", entry_ids)

    def creatures(self, entry_ids: Iterable[int]) -> RespawnAggregate | None:
        return self.aggregate("creature", entry_ids)
