from __future__ import annotations

from lib.quest_reward_source import RewardDatabase, batch_quest_reward_facts, quest_reward_facts


def _tuple(values: list[object]) -> str:
    rendered = []
    for value in values:
        if isinstance(value, str):
            rendered.append("'" + value.replace("'", "''") + "'")
        else:
            rendered.append(str(value))
    return "(" + ",".join(rendered) + ")"


def test_reward_facts_respect_reward_counts_and_sort_choices_by_total_sell_value() -> None:
    quest = [0] * 50
    quest[0] = 42
    quest[13] = 27000
    quest[22] = 1001
    quest[23] = 2
    quest[38] = 2001
    quest[39] = 1
    quest[40] = 2002
    quest[41] = 3

    item_a = [0] * 12
    item_a[0] = 1001
    item_a[4] = "Fixed"
    item_a[11] = 100

    item_b = [0] * 12
    item_b[0] = 2001
    item_b[4] = "Choice Expensive Each"
    item_b[11] = 250

    item_c = [0] * 12
    item_c[0] = 2002
    item_c[4] = "Choice Expensive Total"
    item_c[11] = 100

    database = RewardDatabase(
        quest_template_text="INSERT INTO `quest_template` VALUES\n" + _tuple(quest) + ";\n",
        item_template_text=(
            "INSERT INTO `item_template` VALUES\n"
            + ",\n".join((_tuple(item_a), _tuple(item_b), _tuple(item_c)))
            + ";\n"
        ),
        quest_template_sha256="quest",
        item_template_sha256="item",
    )

    rewards = quest_reward_facts(database, 42)
    assert rewards["reward_money_copper"] == 27000
    assert rewards["fixed_items"][0]["quantity"] == 2
    assert rewards["fixed_items"][0]["sell_price_total_copper"] == 200
    assert [item["item_id"] for item in rewards["choice_items_desc_by_sell"]] == [2002, 2001]
    assert rewards["choice_item_max_sell_copper"] == 300
    assert rewards["gear_sale_max_copper"] == 500

    batch, audit = batch_quest_reward_facts(database, {42})
    assert batch[42] == rewards
    assert audit["matched_quest_count"] == 1
    assert audit["missing_quest_ids"] == []
    assert audit["matched_reward_item_count"] == 3


def test_reward_facts_project_no_money_from_xp_from_effective_quest_flags() -> None:
    quest = [0] * 50
    quest[0] = 42
    database = RewardDatabase(
        quest_template_text="INSERT INTO `quest_template` VALUES\n" + _tuple(quest) + ";\n",
        item_template_text="",
        quest_template_sha256="quest",
        item_template_sha256="item",
    )

    flagged, _ = batch_quest_reward_facts(database, {42}, effective_quest_rows={42: {23: 0x100}})
    normal, _ = batch_quest_reward_facts(database, {42}, effective_quest_rows={42: {23: 0}})

    assert flagged[42]["no_money_from_xp"] is True
    assert normal[42]["no_money_from_xp"] is False
