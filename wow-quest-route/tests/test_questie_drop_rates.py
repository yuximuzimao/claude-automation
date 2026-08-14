from pathlib import Path

from lib.questie_drop_rates import QuestieDropRateDB


QUESTIE = Path(__file__).resolve().parents[2] / ".ai-bridge" / "Questie.zip"


def test_wotlk_drop_rate_respects_forced_wowhead_correction():
    db = QuestieDropRateDB(QUESTIE)
    rate = db.get(24374, 18138)  # 电鳗鱼片 <- 暗泽鳗鱼
    assert rate is not None
    assert round(rate.rate, 4) == 37.2684
    assert rate.source == "wowhead_forced"


def test_wotlk_drop_rate_uses_pserver_before_wowhead_without_correction():
    db = QuestieDropRateDB(QUESTIE)
    rate = db.get(25448, 18283)  # 黑钉之刺 <- 黑钉
    assert rate is not None
    assert rate.rate == 100.0
    assert rate.source == "pserver"


def test_diaphanous_wing_keeps_per_npc_rates():
    db = QuestieDropRateDB(QUESTIE)
    expected = {
        18132: 35.6227,
        18133: 8.6415,
        18283: 9.1993,
        20197: 19.6229,
        20198: 11.2939,
    }
    for npc_id, value in expected.items():
        rate = db.get(24372, npc_id)
        assert rate is not None
        assert round(rate.rate, 4) == value
        assert rate.source == "wowhead_forced"
