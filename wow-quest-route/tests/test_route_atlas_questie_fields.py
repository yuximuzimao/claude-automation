from scripts.build_route_atlas_prototype import Q_PRE_GROUP, Q_PRE_SINGLE


def test_questie_precedence_field_indexes_match_questdb_schema():
    # Questie/Database/questDB.lua: preQuestGroup=12, preQuestSingle=13.
    assert Q_PRE_GROUP == 12
    assert Q_PRE_SINGLE == 13
