# Route Atlas world respawn proxy contract

## Purpose

Provide an external, reproducible proxy for creature/gameobject respawn times that Questie does not contain. This is evidence input, not TitanReforged ground truth. Titan observations may later override it.

## Primary / secondary sources

- Primary proxy: `cmangos/wotlk-db` (3.3.5a world content DB).
- Secondary cross-check: `cmangos/tbc-db` (2.4.3 world content DB) for Outland entries.
- Record exact git commit SHAs used for both repositories.

## Output

Write exactly:

`data/route-atlas/world-respawn-proxy.json`

Top-level shape:

```json
{
  "meta": {
    "source_project": "cmangos/wotlk-db",
    "source_revision": "<wotlk commit sha>",
    "client": "3.3.5a",
    "secondary_source_project": "cmangos/tbc-db",
    "secondary_source_revision": "<tbc commit sha>",
    "extraction_method": "<how current SQL + updates were resolved>",
    "crosscheck_summary": {
      "matched_entries": 0,
      "different_entries": 0,
      "missing_in_secondary": 0
    }
  },
  "gameobjects": {
    "182069": {
      "entry": 182069,
      "spawns": [
        {
          "guid": 123,
          "map": 530,
          "position_x": 0.0,
          "position_y": 0.0,
          "position_z": 0.0,
          "respawn_seconds": 300
        }
      ],
      "secondary_crosscheck": {
        "status": "same|different|missing",
        "values_seconds": [300]
      }
    }
  },
  "creatures": {
    "18138": {
      "entry": 18138,
      "spawns": [
        {
          "guid": 456,
          "map": 530,
          "position_x": 0.0,
          "position_y": 0.0,
          "position_z": 0.0,
          "respawn_seconds": 300
        }
      ],
      "secondary_crosscheck": {
        "status": "same|different|missing",
        "values_seconds": [300]
      }
    }
  }
}
```

## Which IDs to extract

Derive them from the current materialized task layer rather than hardcoding a hand-maintained list:

`data/route-atlas/zangarmarsh-task-profiles.json`

- Every component/source with `kind == "object"` -> gameobject entry.
- Every component/source with `kind == "npc"` -> creature entry.
- Deduplicate entry IDs.

The first use is multi-refresh-object timing, but creature respawn evidence is exported now so the next kill/drop model can use it without repeating the database extraction.

## SQL correctness requirements

Do not assume the first large SQL dump alone is current. Determine whether the repository release/full DB already includes updates. If not, resolve later update SQL that changes target creature/gameobject rows. Use an ephemeral local DB if that is the safest method; otherwise replay target-relevant INSERT/REPLACE/UPDATE/DELETE statements in repository order. Document the method in `meta.extraction_method`.

Do not silently drop complex update statements. If a target entry cannot be resolved reliably, omit its spawn rows and report it in the audit instead of inventing a value.

## Semantics

For CMaNGOS/Trinity-style world DBs, respawn is spawn-instance data. Preserve every available spawn GUID and its respawn seconds. Do not reduce to one value in the extractor. Route Atlas computes min/median/max itself and currently uses the median as a proxy if values differ.

The exporter must not claim these values are TitanReforged values. They are a WotLK/TBC open-source server proxy until replaced by Titan observations.

## Audit report

Also write:

`docs/archive/analysis/2026-08-13-zangarmarsh-respawn-proxy-audit.md`

Include:

- both repository commit SHAs;
- number of requested/found/missing creature IDs;
- number of requested/found/missing gameobject IDs;
- entries where WotLK and TBC disagree;
- any entries affected by later update SQL;
- SQL/table/column names actually used;
- commands or parser script used, enough to reproduce the extraction.
