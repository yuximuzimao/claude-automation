from __future__ import annotations

from typing import Any

from .route_xp import base_quest_xp_at_level_values, load_xp_model_config, quest_xp_at_level

# WotLK 3.3.5 quest flag: experience is not converted to bonus money at max level.
QUEST_FLAGS_NO_MONEY_FROM_XP = 0x100
MAX_LEVEL = 80
COPPER_PER_XP_AT_MAX_LEVEL = 6


def _quest_xp_inputs(questie_data: Any, quest_id: int) -> tuple[int, int] | None:
    row = questie_data.quest_xp.get(quest_id)
    if not isinstance(row, dict):
        return None
    quest_level = row.get(1)
    full_xp = row.get(2)
    if not isinstance(quest_level, int) or not isinstance(full_xp, int) or quest_level <= 0 or full_xp <= 0:
        return None
    return quest_level, full_xp


def base_quest_xp_at_level(questie_data: Any, quest_id: int, player_level: int) -> int:
    """Return base (unmultiplied server-rate) quest XP at a player level from Questie's XP DB."""
    inputs = _quest_xp_inputs(questie_data, quest_id)
    if inputs is None:
        return 0
    quest_level, full_xp = inputs
    return base_quest_xp_at_level_values(
        quest_level=quest_level,
        full_xp=full_xp,
        player_level=player_level,
    )


def server_quest_xp_at_level(
    questie_data: Any,
    quest_id: int,
    player_level: int,
    *,
    model_config: dict[str, Any] | None = None,
) -> int:
    """Return server-rate leveling XP through the sole Stage 8 XP implementation/config."""
    inputs = _quest_xp_inputs(questie_data, quest_id)
    if inputs is None:
        return 0
    quest_level, full_xp = inputs
    return quest_xp_at_level(
        quest_level=quest_level,
        full_xp=full_xp,
        player_level=player_level,
        model_config=model_config or load_xp_model_config(),
    )


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
