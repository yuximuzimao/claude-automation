#!/usr/bin/env python3
"""Claim the gift mall's daily free fertilizer from the standard farm home."""

from farm_daily_clicks import find_point, run_daily


def fertilizer_reward_steps(anchors, platform):
    mall = anchors["scenes"]["mall-welfare"]["views"]
    return (
        (find_point(anchors["home"]["points"], platform, "mall"), 650),
        (find_point(mall["home"]["points"], platform, "gift-tab"), 650),
        (find_point(mall["gift"]["points"], platform, "free"), 950),
        (find_point(mall["reward"]["points"], platform, "dismiss-blank"), 350),
        (find_point(mall["home"]["points"], platform, "return"), 0),
    )


if __name__ == "__main__":
    raise SystemExit(run_daily(__doc__, fertilizer_reward_steps))
