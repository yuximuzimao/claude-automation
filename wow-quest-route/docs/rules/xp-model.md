# 任务经验模型

用途：这是项目中**任务经验计算、经验衰减、保证下界/风险上界**的唯一规则owner。Task Card只保存任务等级、基础经验/来源等输入事实；Route Profile只引用任务并保存路线决策；任务选择和路线算法需要经验值时调用本模型，不得各自复制一套公式。

## 1. 输入与输出

### 输入

每次计算至少需要：

- `quest_id`：稳定任务ID；
- `quest_level`：当前版本任务等级；
- `base_xp`：Task Card当前`rewards.full_xp`/当前权威基础经验；
- `player_level`：预计实际交付时的角色等级；
- `server_quest_xp_multiplier`：当前服务器任务经验倍率，属于**可校准模型参数**，不能写进每张Task Card，也不能把某次阶段值当永久游戏常数；
- 当前路线若做保证账，还需要五号各自的起始等级/经验和该窗口确定会发生的任务奖励/强制击杀经验。

### 路线起始等级/经验必须是机器输入

Derived XP不能从`goal/subtitle/标题`里的“67→68”“68—80”等人类文案解析起始等级。每次Profile级计算必须明确一个`entry_level_xp_source`：

- 继续当前实跑：来自与当前`profile_id + profile_version`匹配的CURRENT真实五号等级/经验；
- 可复用冷启动Profile：来自调用方按本owner合同显式提供的结构化等级/经验起始输入；Profile `entry_requirements`不承载XP，且当前Stage 8尚未闭合时不得用subtitle/goal或路线名代填；
- 承接上一Profile：XP数值只来自上一Profile fresh Derived XP；Profile顺序与RouteState边界来源必须先由Stage 4按Route Program顺序确认，边界RouteState来自唯一Replay派生输出而非人工exit合同。XP数值传播与等级门槛判定仍只由本owner/Stage 8执行，不在Stage 4复制第二套逻辑；
- 如果只有区间而没有精确五号状态，模型可以输出与输入区间一致的上下界，但不得伪造一个精确起点。

起始状态的来源/版本必须进入Derived XP fingerprint，用于审计XP结果对应的输入版本。Profile版本、CURRENT恢复点、上一Profile XP结果、Program边界或XP算法本身变化时，只重算真实受影响的XP结果；fingerprint只负责审计，不负责替代这项impact判断。

### 单任务输出

至少输出：

- `xp_at_turnin_level`；
- `last_full_xp_level`；
- 是否进入经验衰减；
- 输入来源/模型版本，便于实跑差异定位。

### 路线窗口输出

需要经验闭合时，同时输出：

- `guaranteed_lower_bound`：最低号保证获得的经验；
- `possible_upper_bound`：最高/最快号可能获得的经验上界；
- 下一硬等级门槛是否可达；
- 尚未交付的一次性任务是否可能越过完整经验截止。

## 2. 当前WotLK任务经验公式

现役实现`quest_xp_at_level()`使用：

`multiplier10 = clamp(2 × (quest_level - player_level) + 20, 1, 10)`

`raw_xp = base_xp × multiplier10 / 10`

随后按WotLK任务经验显示规则取整：

- `raw_xp <= 100`：按5取整；
- `100 < raw_xp <= 500`：按10取整；
- `500 < raw_xp <= 1000`：按25取整；
- `raw_xp > 1000`：按50取整；

最后：

`xp_at_turnin_level = floor(rounded_xp × server_quest_xp_multiplier)`

历史实现曾在多个foundation/model脚本直接硬编码倍率`2.0`。当前治理已收口：**公式可以固定，服务器倍率只能来自`data/xp-model/model-config.json`的显式版本化输入**；现役Questie兼容消费者经`lib/wotlk_quest_rewards.py`委托本owner，任何其它现役脚本不得再复制该常量。已硬退役的旧模型可保留历史常量作为迁移证据，但不得重新成为执行入口。

## 3. 完整经验截止

当前WotLK一次性任务的完整经验截止：

`last_full_xp_level = quest_level + 5`

判断使用**预计实际交付等级**，不是接取等级。

若`predicted_level_before_turnin > last_full_xp_level`，该角色已经进入衰减区。未满级路线中，如果任务经验仍影响后续可接性或任务打金周期，应打开最小受影响窗口重排交付/任务块；不能为了维护旧顺序忽略衰减。

满级后不再用“完整经验截止”改变路线顺序；满级XP折金由经济模型消费任务奖励事实，不属于本文件的路线选择结论。

## 4. 保证下界

保证下界只计算能够确定发生的经验：

1. 当前路线确定会完成并交付的任务奖励；
2. 任务明确强制的必要击杀经验，可按保守值加入；
3. 沿途误拉、探索、竞争补杀、随机掉落额外补刷、休息经验等不稳定来源按0进入保证账。

五开号是否能达到下一等级/任务门槛，以**等级/经验最低号**为唯一保证基准。

当前服务器实跑的新等级/经验一旦获得，立即替换旧预测作为后续窗口的新基线；禁止为了保持理论表不变继续使用过时起点。

## 5. 风险上界

经验上界用于检查某个角色是否可能过早升级、使后续低等级一次性任务衰减。可计入：

- 当前最高经验角色真实状态；
- 确定任务奖励；
- 强制击杀的合理高值；
- 个人掉落导致的额外击杀；
- 首次探索经验；
- 当前确实存在的休息经验可能增加的杀怪经验。

下界和上界用途不同：

- 下界回答“最低号一定够不够”；
- 上界回答“最快号会不会提前越线”。

两者不得合成一个模糊“预计经验”。

## 6. 任务经验不是任务选择结论

本模型只产出经验事实/派生值，不决定任务`保留/删除/以后做`。

任务选择规则可以消费：

- 当前做的任务经验；
- 因删除导致的后续等级门槛变化；
- 80级XP折金时点变化；
- 替代任务需要补多少经验；

但最终是否删留统一由`leveling-and-selection.md`的任务选择规则决定。

路线顺序如何调整统一由`route-atlas-optimization.md`决定。

## 7. 数据归属

- Task Card：`quest_level`、基础经验/奖励事实、来源和置信度。
- XP Model：本文件的计算规则与全局参数接口。
- Route Profile / 生成结果：某一具体路线节点预计交付等级、由本模型算出的当前派生经验；它不是Task Card永久字段。
- 实跑状态：CURRENT/Journey中的真实等级经验，用作下一计算窗口输入。

禁止：

- 每张Task Card复制经验公式；
- Builder各自实现不同衰减公式；
- 把当前路线某次预测经验回写成任务固有事实；
- 用任务数量、当前XP/h或步骤比例线性外推不同任务块的经验。

## 8. 失效与重算边界

以下输入变化会使现有XP派生值失效：

- 当前有效`quest_level/base_xp`改变；
- `server_quest_xp_multiplier`改变；
- XP公式/取整实现改变；
- Route Profile中的预计交付等级改变。

发生变化后，只需要对引用相关Task Card的Profile重新计算XP派生结果；不维护独立字段传播分类。是否因此进入Selection Review由`leveling-and-selection.md`的触发条件决定。

XP结果变化本身不得自动删除任务。

## 9. 正式XP操作

- 单Profile XP：`python3 scripts/build_route_xp.py <profile_id>`。
- Program没有合法XP基线，或Program起始XP/合同改变：`python3 scripts/build_program_xp.py <program_id>`。
- 已有合法Program XP基线，仅某成员及其后缀受影响：`python3 scripts/update_program_xp_from_member.py <program_id> <profile_id>`，只从该成员向后传播。
- Program没有显式合法entry XP时，完整builder只能刷新`requirements`与fingerprint，不得从标题、subtitle或旧结果伪造起点。
- XP结果若触发任务删留复审，只把当前fresh结果交给`leveling-and-selection.md`；不得在XP脚本里直接改Profile。
