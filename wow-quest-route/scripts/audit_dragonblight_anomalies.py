from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.questie_effective import effective_quest_rows
from lib.questie_source import load_questie
from scripts import build_borean_tundra_foundation as helper

ROOT = Path(__file__).resolve().parents[1]
QUESTIE = ROOT.parent / ".ai-bridge" / "Questie.zip"
OUT = ROOT / "data/route-atlas/dragonblight-anomaly-details.json"
QIDS = {11916, 11930, 12033, 12043, 12050, 12051, 12052, 12112}


def compact_entity(data, row, key):
    values = helper.entity_group(data, row.get(key))
    out = []
    for item in values:
        out.append({
            "type": item.get("entity_type"),
            "id": item.get("entity_id"),
            "name": item.get("name"),
            "zones": item.get("zones"),
            "representative_by_zone": item.get("representative_by_zone"),
        })
    return out


def main():
    data = load_questie(QUESTIE)
    effective, audit = effective_quest_rows(data, QUESTIE, QIDS)
    result = {"questie_version": data.version, "audit": audit, "rows": {}}
    for qid in sorted(QIDS):
        raw = data.quests.get(qid) or {}
        eff = effective.get(qid) or raw
        result["rows"][str(qid)] = {
            "name": helper.localized_name(data, qid, eff),
            "raw_start": compact_entity(data, raw, 2),
            "raw_finish": compact_entity(data, raw, 3),
            "effective_start": compact_entity(data, eff, 2),
            "effective_finish": compact_entity(data, eff, 3),
            "raw_pre_all": raw.get(12),
            "raw_pre_any": raw.get(13),
            "effective_pre_all": eff.get(12),
            "effective_pre_any": eff.get(13),
            "next": eff.get(22),
            "parent": eff.get(25),
            "available_starting_with": eff.get(34),
            "objective_zh": helper.localized_objective(data, qid),
            "objective_en": helper.english_objective(eff),
        }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
