from __future__ import annotations

from pathlib import Path

from lib.questie_effective import parse_wotlk_quest_corrections


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_wotlk_corrections_support_two_arg_l10n_and_profession_namespace(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "Database/Corrections/wotlkQuestFixes.lua",
        '''return {
        [12686] = {
            [questKeys.extraObjectives] = {{nil, Questie.ICON_TYPE_EVENT, l10n("Use Scepter",Questie.ICON_TYPE_INTERACT), 0, {{"monster", 28802}}}},
        },
        [13843] = {
            [questKeys.requiredSkill] = {profKeys.ENGINEERING,400},
        },
}\n''',
    )
    _write(tmp_path, "Database/questDB.lua", "QuestieDB.factionIDs = {}\n")
    _write(tmp_path, "Database/Zones/data/zoneIds.lua", "ZoneDB.zoneIDs = {}\n")
    _write(tmp_path, "Database/Constants.lua", "QuestieDB.sortKeys = {}\n")
    _write(
        tmp_path,
        "Modules/QuestieProfessions.lua",
        "QuestieProfessions.professionKeys = {\n    ENGINEERING = 202,\n}\n",
    )

    parsed, failures, meta = parse_wotlk_quest_corrections(tmp_path, {12686, 13843})

    assert failures == {}
    assert meta["unresolved_symbols"] == {}
    assert parsed[13843][18] == {1: 202, 2: 400}
    assert parsed[12686][29][1][3] == "Use Scepter"
