#!/usr/bin/env python3
"""After harvest, visit the first friend once and click the first daily claim."""

from farm_daily_clicks import find_point, run_daily


def task_steps(anchors, platform):
    scenes = anchors["scenes"]
    home = anchors["home"]["points"]
    friends = scenes["friend-list"]["views"]["first-visit"]["points"]
    tasks = scenes["task-book"]["views"]["daily"]["points"]
    reward = scenes["mall-welfare"]["views"]["reward"]["points"]
    return (
        (find_point(home, platform, "friends"), 650),
        (find_point(friends, platform, "first-visit"), 850),
        ("friend-action", 650),
        (None, 800),  # Locate the visible return-home button before leaving the friend farm.
        (find_point(home, platform, "task"), 650),
        (find_point(tasks, platform, "login-status"), 900),
        (find_point(reward, platform, "dismiss-blank"), 350),
        (find_point(tasks, platform, "close"), 0),
    )


if __name__ == "__main__":
    raise SystemExit(run_daily(__doc__, task_steps))
