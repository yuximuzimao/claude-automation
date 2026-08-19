from __future__ import annotations

import math
from typing import Any

# WotLK 3.3.5 quest flag: experience is not converted to bonus money at max level.
QUEST_FLAGS_NO_MONEY_FROM_XP = 0x100
MAX_LEVEL = 80
COPPER_PER_XP_AT_MAX_LEVEL = 6


def _round_quest_xp(xp: float) -> int:
    """Mirror the 3.3.5 Quest::XPValue rounding bands used by AzerothCore/Trinity-style cores."""
    if xp <= 100:
        return int(5 * math.floor((xp + 2) / 5))
    if xp <= 500:
        return int(10 * math.floor((xp + 5) / 10))
    if xp <= 1000:
        return int(25 * math.floor((xp + 12) / 25))
    return int(50 * math.floor((xp + 25) / 50))


def base_quest_xp_at_level(questie_data: Any, quest_id: int, player_level: int) -> int:
    """Return base (unmultiplied server-rate) quest XP at a player level from Questie's XP DB."""
    row = questie_data.quest_xp.get(quest_id)
    if not isinstance(row, dict):
        return 0
    quest_level = row.get(1)
    full_xp = row.get(2)
    if not isinstance(quest_level, int) or not isinstance(full_xp, int) or quest_level <= 0 or full_xp <= 0:
        return 0
    diff_factor = max(1, min(10, 2 * (quest_level - player_level) + 20))
    return _round_quest_xp(full_xp * diff_factor / 10.0)


def max_level_bonus_money(questie_data: Any, quest_id: int, quest_flags: int | None = None) -> dict[str, Any]:
    """Compute WotLK max-level XP->money bonus, explicitly excluding any normal direct-money reward.

    AzerothCore 3.3.5 Quest::GetRewMoneyMaxLevel() computes XPValue(max_level) * 6 copper,
    unless QUEST_FLAGS_NO_MONEY_FROM_XP is set. This value is independent of the project's
    2x leveling-XP planning multiplier.
    """
    flags = int(quest_flags or 0)
    no_money = bool(flags & QUEST_FLAGS_NO_MONEY_FROM_XP)
    xp_at_80 = 0 if no_money else base_quest_xp_at_level(questie_data, quest_id, MAX_LEVEL)
    copper = xp_at_80 * COPPER_PER_XP_AT_MAX_LEVEL
    gold = copper // 10000
    silver = (copper % 10000) // 100
    copper_remainder = copper % 100
    return {
        "level": MAX_LEVEL,
        "xp_at_level_80_base": xp_at_80,
        "bonus_money_from_xp_copper": copper,
        "bonus_money_from_xp_gold_decimal": round(copper / 10000.0, 4),
        "display": f"{gold}g {silver:02d}s {copper_remainder:02d}c",
        "no_money_from_xp": no_money,
        "rate": "6 copper per base XP at level 80",
        "server_leveling_xp_multiplier_applied": False,
    }
