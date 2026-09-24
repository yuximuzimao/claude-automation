from __future__ import annotations


RETIREMENT_MESSAGE = """
build_quest_reward_economy.py is retired.

The old data/route-atlas/quest-reward-economy.json is historical migration evidence only.
It must not be regenerated or used as Route Lifecycle runtime truth because it duplicated
reward/max-level-economy logic outside the current owners.

Current authoritative path:
  Task Card rewards
    -> Stage 8 Derived XP
    -> lib/route_economy.py Stage 9 Derived Economy

For one Task Card reward refresh, use scripts/enrich_task_card_rewards.py.
For route-level Economy, use scripts/rebuild_route_profile.py.
For live route-economy evidence, use scripts/record_route_economy_observation.py.
""".strip()


def main() -> None:
    raise SystemExit(RETIREMENT_MESSAGE)


if __name__ == "__main__":
    main()
