# 路线经济模型

用途：这是项目中**任务路线收益如何计算、哪些收入/成本可以进入路线G/hour、满级XP如何折金、预测与实跑经济数据怎样分层**的唯一规则owner。Task Card只保存单任务原始奖励事实；Route Profile只保存路线决策；Timing只提供墙钟；Selection只消费本模型结果，不自行复制经济公式。

## 1. 模型回答什么

对任一可执行Route Profile，经济模型至少输出：

- 路线任务奖励收入；
- 固定奖励物卖店总值；
- 可选奖励物按当前规则可兑现的最大卖店值；
- 未满级/满级交付下实际任务金币口径；
- 已明确可量化的路线额外收入/成本；
- `gross / known_cost / net`三种口径及完整性状态；
- 与fresh Derived Timing组合后的route G/hour；
- 输入版本/fingerprint与不确定来源。

经济结果是**Route Profile上下文派生值**，不写回Task Card固有事实。

## 2. 输入真源

### 2.1 Task Card rewards

只消费当前Task Card中的原始奖励事实：

- `full_xp`；
- `reward_money_copper`；
- `fixed_items_sell_total_copper`；
- `choice_item_max_sell_copper`；
- `gear_sale_max_copper`；
- 其它以后明确进入rewards schema的稳定奖励事实。

物品数量、SellPrice和直接金币属于Task Card奖励事实，经济模型不得重新从旧workbench/foundation按任务名反查。

### 2.2 Derived XP / Route Profile

经济模型需要知道每个任务**实际交付时**是否已经满级，因此消费：

- Route Profile真实turnin顺序；
- fresh Derived XP中的预计交付等级/满级时点；
- Profile实际完成/交付任务集合。

它不自己重算经验等级，也不能假定“整张图都按80级”。

### 2.3 Derived Timing

G/hour只允许与**同一Profile、同一输入版本的fresh Derived Timing**组合。旧step分钟快照、不同Profile版本或不匹配action范围的实跑时间不得直接作为当前预测分母。

### 2.4 Economy Model参数

当前服务器经济口径必须进入显式、可版本化模型配置，不得散落在Builder：

- 满级任务XP折金：`6 copper / XP`；这里的XP是**该任务在服务器最高等级（当前80级）按任务等级衰减/取整后的基础任务XP**，与`lib/route_xp.py`的基础XP公式同源，不是Task Card `full_xp`直接乘6；
- 当前时光服满级任务金币口径：`max(reward_money_copper, xp_conversion_copper)`，不是两者相加；这是当前服务器口径，不等同于AzerothCore默认内核的相加行为；
- 服务器任务XP倍率不乘入满级XP折金；
- 可选奖励只取得一件，卖店估值取当前Task Card中可选奖励最大合计卖价；
- 固定奖励物全部计入其可卖店总值。

若以后当前服务器实测推翻以上口径，应修改本owner及模型参数版本，不在单任务/单地图脚本加例外。

## 3. 未满级与满级任务金币

### 未满级交付

任务本体可兑现金币：

`quest_cash = reward_money_copper`

任务经验进入Derived XP，不在当前时点折成金币。

### 满级交付

一般任务：

`xp_conversion_copper = base_quest_xp_at_level(quest_level, full_xp, max_level) × 6`

`quest_cash = max(reward_money_copper, xp_conversion_copper)`

随后再加可卖店奖励物价值：

`quest_reward_value = quest_cash + gear_sale_max_copper`

### 禁止XP折金的任务

`QUEST_FLAGS_NO_MONEY_FROM_XP (0x100)`等会改变满级金币规则的稳定任务事实，必须由结构化机器输入进入Task Card rewards后才能把该任务的满级经济结果标为fresh。当前正式Task Card已由Effective Quest Source机械迁入`rewards.no_money_from_xp`；单卡/批量奖励刷新都必须复用同一reward extractor。字段缺失、来源冲突或未来schema回退时，统一Economy builder仍必须返回requirements，不能静默按普通任务公式猜。

## 4. Gross、Known Cost、Net必须分开

项目第一目标是长期可重复**净金币 / 玩家真实墙钟**，所以模型不得把“已算收入”直接命名为净收益。

统一输出：

- `gross_copper`：当前已纳入的路线收入；
- `known_cost_copper`：当前已结构化并可确定的路线支出；
- `net_copper = gross_copper - known_cost_copper`；
- `cost_coverage`：说明是否已覆盖所有会显著改变净收益的已知成本。

系统飞行费用、必要消耗品、维修等只有在有可靠结构化输入时才进入`known_cost_copper`。未知成本不得偷偷按0后仍宣称“完整净收益”；可以输出gross和partial net。

沉没成本仍服从Selection owner：已经发生的采购/转场/前置支出不重新计入从CURRENT开始的剩余决策成本。

## 5. 非任务奖励与实跑经济Observation

玩家实跑记录的地图内总金币增长、泰坦碎片、普通掉落、材料等**不是Task Card任务奖励事实**。

它们属于Route/Profile范围的经济Observation，至少绑定：

- `profile_id`；
- `profile_version`；跨Profile样本同时记录`program_id/program_version`与经过的Profile边界；
- action/step范围或完整route范围；
- 原始金币增量/物品数量；
- 是否包含拍卖行估值、卖店价或尚未估值物品；
- 估值参数版本；
- 是否含外部交易、采购、邮件转账等污染项。

Observation可以用于校准“真实路线总收益”和验证Derived Economy，但不能反向修改Task Card rewards。泰坦碎片/市场材料若要折成金币，必须读取显式市场估值参数并保留原始数量；没有稳定价格时只报告数量，不伪造精确金币。

## 6. Route级聚合

同一Profile中每个任务只按实际有效交付次数计入，不因为同一task_id在页面多次出现就重复收费/重复记收益。

Route级确定性任务收益：

`route_task_gross = Σ quest_reward_value_at_actual_turnin_state`

再加模型明确纳入、且与当前Profile同scope的其它稳定收入组件，得到`gross_copper`。

G/hour：

`gross_gph = gross_copper / derived_route_hours`

`net_gph = net_copper / derived_route_hours`

必须同时标明经济覆盖和Timing freshness。若Timing或关键经济输入stale/unknown，不产出看似精确的最终G/hour。

## 7. 与Selection的边界

Economy只回答：

- 当前/未来时点能兑现多少任务路线收益；
- 哪些收入/成本已经纳入；
- 当前Profile的gross/net/Gh是多少。

它不回答“任务要不要删”。Selection把Derived Economy与Derived Timing、XP、Availability、后续链一起比较`now / later / never`。

经济结果变化不得自动修改Route Profile；只按Selection触发条件标记review。

## 8. 失效与重算边界

以下变化会使相关Derived Economy失效：

- Task Card rewards变化；
- 会改变满级折金资格的稳定奖励/flag事实变化；
- Route Profile任务集合或turnin顺序变化；
- Derived XP中的实际交付等级/满级时点变化；
- Economy policy/参数变化；
- 参与路线总收益估值的市场参数变化；
- 需要输出G/hour时，Derived Timing变化或stale；
- Economy公式/解析器实现变化。

通过`task_id → Route Profile`反向索引找到可能受影响的Route，只重算真实受影响的Economy结果。fingerprint只用于产物链审计，不负责生成impact名单或跳过执行。

## 9. 可机械验证的不变量

至少检查：

- 每个任务收益只按稳定task_id与实际交付次数聚合；
- 未满级交付不提前折XP金币；
- 满级折金使用模型配置的当前服务器口径；
- 服务器XP倍率不误乘进XP折金；
- choice reward只计一件；
- 固定奖励数量和卖店价直接读取Task Card rewards；
- `gross / known_cost / net`不混名；
- Observation与当前Profile/version/range不匹配时不校准当前预测；
- Economy/Gh输出包含输入version/fingerprint供审计；是否执行Economy owner只由SOP本次变更链决定；
- 旧`quest-reward-economy.json`或workbench不能反向成为当前Task Card/Route收益真源。

## 10. 正式Economy操作

- 单Profile Economy：`python3 scripts/build_route_economy.py <profile_id>`。
- Program没有合法Economy基线，或Program级经济输入改变：`python3 scripts/build_program_economy.py <program_id>`。
- 已有合法Program Economy基线，仅指定成员及其受XP影响的后缀需要刷新：逐个使用`python3 scripts/update_program_member_economy.py <program_id> <profile_id>`，不重算无关前缀。
- 原始Economy Observation追加：`python3 scripts/record_route_economy_observation.py ...`；只记录事实，不自动估值或修改Task Card rewards。
- XP合法保持`requirements`时，Economy只能刷新相应requirements/依赖，不伪造满级时点或收益。

## 11. 本文件明确不负责

- Task Card奖励字段和来源：`docs/task-library/README.md`；
- 任务经验/交付等级：`xp-model.md`；
- 路线墙钟：`timing-and-benchmarking.md`；
- 任务删留：`leveling-and-selection.md`；
- 路线排序/交通：`route-atlas-optimization.md`；
- 跨owner传播原则：`route-profile-and-lifecycle.md`；最小测试组合：`../../tests/README.md`。
