# 2026-10-30 本地 Runner 架构重构与自恢复续跑交接

## 阶段范围

本阶段不再继续优化“Agent 看截图 → 单击 → 再截图”的实时遥控流程，而是重新定义 QQ / 微信《QQ经典农场》的执行架构：稳定机械步骤必须下沉为本机 deterministic Runner；Planner 只提供策略，Runner 连续执行，异常才交回 Agent。

同时完成了种子位置模型的重新设计、旧三轮 page/slot 方案降级、QQ 固定入口脚本化、Runner 实施计划建立，以及每小时“检查点式自恢复续跑”任务的启用。

## 核心架构决策

- 第一目标改为：**用户可感知的连续流畅执行**，而不是继续增加逐步截图和判断。
- 正常结构：
  `Planner → RUN_PLAN（只写策略）→ Local Runner → 本地阶段验收 → 异常才回 Agent`。
- 正常 phase 内 LLM/tool round-trip 必须为 0。
- Runner 不拥有“今天种什么、库存不足换什么、8h/12h怎么选”等策略权；这些只属于 Planner。
- 未来运行计划只写：种子名、数量、成熟档、四格 placement 等策略数据；**不再写死 picker page/slot**。
- page/slot 是 Runner 根据本地顺序状态和库存计算出来的 UI 派生数据。

## 种子顺序模型的收敛

### 已废弃的旧约束

旧三轮计划曾刻意保证目标种子计划结束后仍 >0，以防库存归零后 picker 条目消失、后续槽位左移。

该约束正式废弃。

原因：位置左移是纯数组/分页问题，不需要 Planner 或 AI 绕开。

### 当前默认模型

当前首选实现：

`stable_order + quantities → visible_order → page/slot`

- `stable_order`：重新进入农场后校准的稳定相对顺序。
- `quantities`：Runner 维护的当前数量事实。
- `visible_order`：每次过滤数量 <=0 的种子后临时计算，不长期保存。
- page = index // 5 + 1；slot = index % 5 + 1。
- 成功消费到 0 只更新数量；下一次 visible_order 自动过滤，后续种子自动左移。
- 历史已知种子从 0 重新获得时，当前首要假设是：重新进入后会按 stable_order 恢复到稳定位置。

### 需要真机验证的关键假设

历史数据里微信曾出现 `艾草 / 森野白桃` 相对顺序差异。

本阶段没有直接把它解释为“活动永久改序”，而采用用户提出的更简单假设：

> 刚获取新种子时，当前会话可能临时插入/调整顺序；重新进入农场后恢复正常稳定顺序。

后续执行者/Runner 必须设计一次真机验证：

1. 记录重新进入后的正常顺序。
2. 获得一个原本为0/不存在的种子。
3. 不退出，立即读取顺序。
4. 退出/关闭并按正常入口重新进入。
5. 再读取顺序。
6. 若恢复稳定顺序，保留简单 stable_order 模型。
7. 只有重进后仍不恢复，才升级到 `order_revision/order_dirty` 复杂备选模型。

## Runner 实施计划

根目录新增 `IMPLEMENTATION_PLAN.md`，作为本地 Codex/后续 Agent 开发 Runner 的第一入口。

计划按以下里程碑推进：

- M0：数据模型、stable_order、farm-state、动态 page/slot 算法、dry-run、单元测试。
- M1：窗口、本地 I/O、截图、收获状态机。
- M2：四格种植事务、普通一键种植、目标图标/数量校验、24格终验。**这是当前最重要里程碑。**
- M3：神秘商人、商城福利、分享、好友互动、每日任务。
- M4：普通/高级化肥与阶段跟踪。
- M5：成熟时间调度、自动打开/执行/关闭。

M2 稳定前不做定时化、复杂化肥、通用视觉 Agent。

## 已明确写入的主要踩坑约束

- 禁止恢复 Agent 单击级正常路径。
- macOS 截图像素、裁图坐标、CGEvent 屏幕逻辑坐标不得混用；Runner 统一使用 window-local logical coordinate。
- 跨应用/恢复窗口后必须重新读取 window bounds。
- QQ 农场入口固定复用 `scripts/open_qq_farm.swift` / 已验证主窗口相对入口，不再临场走“更多功能”。
- 四格种植是不可拆事务：`目标土地 → 选种 → 2×2 preview → confirm → landed 验收`。
- preview 不是已经落地；preview 位置由最初点击土地决定。
- QQ 四格目标使用纯金地组合；微信使用纯紫晶组合，不跨土地等级。
- 普通一键种植后必须做 24-cell occupancy 阶段终验。
- 四格收获批量识别后连续点完，再全局手形一次，不允许每颗回 Agent。
- picker 不允许盲假设每次从第1页打开；页导航必须本地验证/归一。
- 目标 slot 不只做图标校验，还要本地校验数量足够，避免库存被手动消耗后只种一半。
- 未知遮罩/账号授权/支付安全提示一律结构化 STOP，不盲试坐标。
- 用户与 Runner 同时操作导致关键状态漂移时 STOP，不抢鼠标恢复。

## 自恢复续跑模式

本阶段启用了“农场 Runner 重构”的每小时自恢复续跑任务。

其语义不是普通“每小时重复同一动作”，而是：

> 定时唤醒 → 读取 IMPLEMENTATION_PLAN / CURRENT / Todo → 从最近检查点恢复 → 做下一段可验证工作 → 写回进度 → 下次继续。

当前任务约束：

- 默认由当前助手直接使用 CodexPro workspace/read/edit/bash 等能力开发、测试和验收。
- **Codex CLI 不是默认依赖。** 只有某一步明确更适合交给 Codex agent 时才可选调用。
- 因此用户的 Codex 5h/weekly 额度不是本自动续跑的正常瓶颈。
- 每轮结束都要做对抗式审查：是否偏离第一目标、是否把策略塞进 Runner、是否重新变成一步一截图。
- 普通续跑不打扰用户。
- 只有实质里程碑、需要用户输入/授权、或不可安全推断的阻塞才报告。
- 完成条件：M0/M1/M2 全部验收通过，QQ/微信正常一轮可本地连续完成收获+种植，正常 phase 的 LLM/tool round-trip=0，关键异常可结构化停止。
- 达到完成条件后，自动化任务必须自行停用。

用户以后可用关键词：**“自恢复续跑”** 或 **“检查点式自恢复续跑”**，表示这种持续恢复、推进、验收、完成后自动停止的工作方式。

## Codex reset credit 旁注

本阶段确认用户当前仍有 1 张 Codex Full reset（Weekly + 5 hr），但农场自恢复续跑已明确不依赖 Codex CLI，因此没有必要为了本项目提前消耗 reset credit。

这条仅作为本次执行资源判断，不属于农场 Runner 的运行规则。

## 当前收尾状态

- 根目录 `IMPLEMENTATION_PLAN.md` 已成为 Runner 开发最高优先级文档。
- `SKILL.md`、`CLAUDE.md`、`docs/CURRENT.md`、`docs/gameplay-rules.md`、`docs/seed-catalog.md`、`tasks/todo.md` 均已切换到新架构口径。
- `data/next-cycle-plan.json` 仅保留为 2026-10-28 旧三轮历史样本，不再作为正常执行入口。
- `data/picker-order.json` 仅作为 stable_order 与“刚获取/重进”假设的历史证据。
- 当前农场真实现场和下一步恢复入口见 `../../CURRENT.md`。
- 后续无需继续本会话人工推进，等待自恢复任务按 `IMPLEMENTATION_PLAN.md` 继续。
