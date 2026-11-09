from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from farm_qq_round import workflow
from farm_radish_restock import DEFAULT_PURCHASES
from farm_radish_xp import DEFAULT_ROUNDS, RADISH_BATCH, radish_plan


def test_radish_default_is_five_full_fields():
    assert DEFAULT_ROUNDS == 5
    assert DEFAULT_ROUNDS * RADISH_BATCH == 120


def test_monthly_restock_is_thirty_seven_max_purchases():
    assert DEFAULT_PURCHASES == 37
    assert DEFAULT_PURCHASES * 99 == 3663
    assert DEFAULT_PURCHASES * 99 >= 30 * DEFAULT_ROUNDS * RADISH_BATCH


def test_radish_plan_is_qq_ordinary_page7_slot4_only():
    plan = radish_plan()
    assert plan["qq"]["planting"] == {
        "special": [],
        "ordinary": {"page": 7, "slot": 4},
    }
    assert plan["wechat"]["planting"] == {"special": [], "ordinary": None}


def test_qq_round_order_keeps_friend_sweep_before_task_claim():
    steps = workflow(5, ROOT / "data/operation-plan.json")
    scripts = [Path(step[1]).name for step in steps if not isinstance(step, tuple)]
    assert scripts == [
        "farm_fertilize_once.py",
        "farm_harvest_once.py",
        "farm_radish_xp.py",
        "farm_plant_once.py",
        "farm_friend_sweep.py",
        "farm_daily_task_claim.py",
        "farm_daily_fertilizer_reward.py",
    ]
