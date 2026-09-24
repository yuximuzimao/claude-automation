# 2026-09-17 Route Lifecycle Stage 8 / DK 实跑锚点 NEAT

## 本轮范围

本轮继续在 `feat/wow-architecture-migration` worktree 内按 Route Lifecycle SOP 逐 stage 完善新架构。用户当前不参与碎片化技术方向判断；局部 owner/schema/script 设计由实现侧依据既定第一原则、既有路线业务经验和历史实跑证据自行把控，待 Stage 1–14 全部形成完整可执行闭环后，再由用户从头按业务流程逐环节/逐支线验收。

本轮另外收到一段地狱火 DK 首跑现场反馈。由于架构仍在重构，该段只原文封存在 Todo，并建立唯一续接锚点；暂不据此修改路线、Task Card、Timing 或其它业务真源。

## Route Lifecycle 当前状态

- Stage 1–6 已完成 implementation 收口。
- Stage 7 Timing 已完成 implementation 收口：新链只消费 Stage 4 Replay 执行结果、Stage 5 canonical movement / Program boundary、Stage 6 Service Context；旧 Timing estimator CLI 已硬退役。相关通用/迁移合同 68/68、Stage 4–7 真实验收 9/9 通过。
- Stage 8 XP / Level Timeline 已建立核心唯一 owner：
  - `data/xp-model/model-config.json`：服务器任务 XP 倍率 + 1–80 升级经验表；
  - `lib/route_xp.py`：唯一任务 XP 衰减/取整与等级推进执行器；
  - Stage 3 的 `min_level` 只在 Stage 8 解析；
  - 五号按各自 level/xp 状态分别推进；
  - Profile/Program 间只传播 fresh XP state；
  - 没有结构化 XP 起点时禁止从标题/goal/旧预算文本猜等级。
- Stage 8 已接入唯一 `scripts/rebuild_route_profile.py`，并提供唯一显式 `--xp-input` 运行时/冷启动输入通道。
- Stage 8 的 XP 风险语义已纠偏：额外自然经验可以形成“提前升级风险场景”，但如果提前升级会改变后续低级任务衰减，该场景不能冒充最终总 XP 上界；此时 `possible_upper_bound` 保持 UNKNOWN。
- Stage 8 当前仍在**收口**，尚未正式按 §17.2 宣告完成：还需完成剩余旧 XP 消费者/倍率硬编码清零、真实 fixture / SOP / tests registry / Todo 对齐及最终回归。Stage 9 Economy 尚未开始业务实现。

## Stage 4 blocked 的真实含义

当前完整 `horde-fivebox-full-clear` 的 Stage 4 implementation 本身已经完成；artifact 仍为 `blocked`，真正造成 blocked 的硬错误目前只有两条：

1. `hellfire-fivebox → zangarmarsh-fivebox`：下游要求携带 9912，但上游当前结构化状态无法满足；
2. `grizzly-fivebox → howling-fivebox`：12181 / 12188 当前被判为互斥冲突。

其它大量诊断主要是旧路线迁移中的 UNKNOWN / 不可证明状态，不代表 Stage 4 架构失败。以上两条继续保留到最终路线业务验收，不为了推进 Stage 8–14 提前修路线。

## XP 起点的执行原则

- XP 起点是运行时/冷启动真实状态，不是 Route Profile 固有属性。
- 没有真实起点时，Stage 8 可以证明模型能力，但不能确定“当前某个任务点角色一定是多少级多少经验”。
- 正式保证账只使用确定发生的任务 XP；沿途击杀、探索、额外怪等不稳定自然经验默认不计入保证下界。
- 因此只要保守任务 XP 路线已经证明某等级门槛可达，实际实跑经验通常只会有正余量；但禁止把历史自然经验比例直接升级成固定保证经验。
- 后续可在地图/阶段起点录入最低号或五号完整 level/xp，Stage 8 从该真实锚点重新计算。

## Stage 8 唯一性治理已做部分

- `lib/wotlk_quest_rewards.py` 已改为复用 `lib/route_xp.py` 的基础任务 XP 衰减/取整实现，避免 Stage 9 以后再维护第二套公式。
- `scripts/build_35_55_task_foundation.py` 的兼容 XP 接口已改为委托统一 XP owner / model config。
- `scripts/build_39_55_evidence_budget.py` 的旧 `XP_TO_NEXT` 已改为统一 XP model config 投影，消除历史 39→40 70,100 / 70,200 冲突。
- `scripts/build_35_55_cost_model.py` 与 `scripts/build_northrend_68_80_time_xp_model.py` CLI/main 已硬退役，只保留历史迁移/校准证据，禁止再写第二套 Timing/XP 派生产物。
- 唯一性扫描仍发现少量现役 foundation 的服务器倍率兼容常量，需要下一会话继续切到统一 config；这正是 Stage 8 当前恢复点。

## 本轮验证记录

本轮已通过的关键回归包括：

- Replay / continuity / Stage 3–4 条件分支修复：27/27；
- Stage 7 通用/迁移合同：68/68；
- Stage 4–7 真实验收：9/9；
- Stage 8 XP + continuity 首轮：14/14；
- XP 上下界纠偏后，XP / reward / continuity：16/16；
- Stage 1 / 4 / 8 接入回归：24/24。

这些测试证明的是 implementation contract，不要求当前路线 artifact 全绿。

## 地狱火 DK 实跑续接锚点

上一条已保存现场状态：

- 从接 10629《肮脏的工作》开始暂停有效计时；
- 10230《战斗的号角》曾误删，等待后续补接。

2026-09-17 新口述继续了这条未闭合历程。新段有效计时口径从“接《血之复仇》”开始；原始反馈已完整封存在 `tasks/todo.md`，重构完成前不拆解处理。

**下次游戏实跑唯一续接锚点：已完成《阿尔泽斯之死》 → 前往黑锋之门学习技能 → 随后炉石回来；用户明确本次历程到此结束，当时约 63 级 / 6100 经验。**

当前 worktree 没有本轮 DK 原始 Questie Journey，同步前以用户现场口述作为当前恢复锚点；以后完整 Journey 到位，只按该锚点对齐事件/时间，不把前段重复并入新段。

## 下一会话唯一开发入口

先读：

1. `docs/verified-routes/CURRENT.md`
2. `tasks/todo.md`
3. `docs/verified-routes/ROUTE-DESIGN-PROCESS.md`
4. 本 NEAT（仅用于恢复本轮形成过程）

然后继续 **Stage 8 收口**：先完成剩余旧 XP 消费者/倍率真源清零、真实 fixture 与文档/测试状态对齐，满足 SOP §17.2 后正式标记 Stage 8 implementation complete，再进入 Stage 9 Economy。

不要为了消除 Stage 4 当前两条业务 blocked 去修改具体路线；不要处理本轮新封存的 DK 实跑细节；不要提前进入 Publisher/最终页面业务验收。

## 版本控制状态

本轮按用户要求只做 NEAT / 恢复入口归档；继续保留整个 `feat/wow-architecture-migration` worktree。**不合并主干、不提交、不推送。** Stage 1–14 全闭环、最终 fresh Publisher / player-view / mechanical audit / cold read 完成以前，worktree 继续隔离承载架构迁移。
