#!/usr/bin/env python3
"""Claim the current daily-task reward after friend interaction is already done."""

from farm_daily_clicks import find_point, run_daily


def claim_steps(anchors, platform):
    tasks = anchors["scenes"]["task-book"]["views"]["daily"]["points"]
    reward = anchors["scenes"]["mall-welfare"]["views"]["reward"]["points"]
    home = anchors["home"]["points"]
    return (
        (find_point(home, platform, "task"), 650),
        (find_point(tasks, platform, "login-status"), 900),
        (find_point(reward, platform, "dismiss-blank"), 350),
        (find_point(tasks, platform, "close"), 0),
    )


if __name__ == "__main__":
    raise SystemExit(run_daily(__doc__, claim_steps))
