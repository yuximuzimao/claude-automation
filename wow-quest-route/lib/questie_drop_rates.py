from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lib.questie_lua import LuaTableParser


WOWHEAD_REF = -1
PSERVER_REF = -2


@dataclass(frozen=True)
class DropRate:
    item_id: int
    npc_id: int
    rate: float
    source: str


class QuestieDropRateDB:
    """Read Questie's effective WotLK item drop-rate data from a supplied package.

    Mirrors DropDB.GetItemDroprate precedence for the WotLK client:
    propagated manual corrections (Era -> TBC -> WotLK), then pserver/cmangos,
    then Wowhead. Correction references can explicitly force one backing source.
    """

    def __init__(self, zip_path: str | Path):
        self.zip_path = Path(zip_path)
        with zipfile.ZipFile(self.zip_path) as zf:
            drop_text = zf.read("Questie/Database/DropTables/data/wotlkItemDrops.lua").decode("utf-8", "ignore")
            correction_text = zf.read("Questie/Database/DropTables/data/itemDropCorrections.lua").decode("utf-8", "ignore")
        self.wowhead = self._embedded_table(drop_text, "QuestieWotlkItemDrops.wowheadData")
        self.pserver = self._embedded_table(drop_text, "QuestieWotlkItemDrops.cmangosData")
        self.corrections: dict[int, dict[int, int | float]] = {}
        for table_name in (
            "QuestieItemDropCorrections.Era",
            "QuestieItemDropCorrections.Tbc",
            "QuestieItemDropCorrections.Wotlk",
        ):
            table = self._assignment_table(correction_text, table_name)
            for item_id, npc_map in table.items():
                if not isinstance(item_id, int) or not isinstance(npc_map, dict):
                    continue
                merged = self.corrections.setdefault(item_id, {})
                for npc_id, value in npc_map.items():
                    if isinstance(npc_id, int) and isinstance(value, (int, float)):
                        merged[npc_id] = value

    @staticmethod
    def _embedded_table(text: str, variable_name: str) -> dict[Any, Any]:
        marker = f"{variable_name} = [["
        start = text.index(marker) + len(marker)
        end = text.index("]]", start)
        parsed = LuaTableParser(text[start:end]).parse()
        if not isinstance(parsed, dict):
            raise ValueError(f"Expected table in {variable_name}")
        return parsed

    @staticmethod
    def _assignment_table(text: str, variable_name: str) -> dict[Any, Any]:
        marker = f"{variable_name} ="
        start = text.index(marker) + len(marker)
        transformed = text[start:].replace("DropKeys.WOWHEAD", str(WOWHEAD_REF)).replace(
            "DropKeys.PSERVER", str(PSERVER_REF)
        )
        parsed = LuaTableParser(transformed).parse()
        if not isinstance(parsed, dict):
            raise ValueError(f"Expected table in {variable_name}")
        return parsed

    @staticmethod
    def _lookup(table: dict[Any, Any], item_id: int, npc_id: int) -> float | None:
        row = table.get(item_id)
        if not isinstance(row, dict):
            return None
        value = row.get(npc_id)
        return float(value) if isinstance(value, (int, float)) else None

    def get(self, item_id: int, npc_id: int) -> DropRate | None:
        correction = None
        row = self.corrections.get(item_id)
        if row:
            correction = row.get(npc_id)

        if isinstance(correction, (int, float)):
            if correction >= 0:
                return DropRate(item_id, npc_id, float(correction), "questie_correction")
            if correction == WOWHEAD_REF:
                value = self._lookup(self.wowhead, item_id, npc_id)
                return DropRate(item_id, npc_id, value, "wowhead_forced") if value is not None else None
            if correction == PSERVER_REF:
                value = self._lookup(self.pserver, item_id, npc_id)
                return DropRate(item_id, npc_id, value, "pserver_forced") if value is not None else None

        value = self._lookup(self.pserver, item_id, npc_id)
        if value is not None:
            return DropRate(item_id, npc_id, value, "pserver")
        value = self._lookup(self.wowhead, item_id, npc_id)
        if value is not None:
            return DropRate(item_id, npc_id, value, "wowhead")
        return None
