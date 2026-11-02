# QQ经典农场辅助

用于维护 QQ / 微信两套《QQ经典农场》的稳定玩法规则、种子资料与本地 deterministic Runner。

当前架构不是“AI 看整张农田后逐步遥控”，而是：

```text
Planner / ChatGPT 决定种什么
→ Runner 按固定窗口、固定 4×6 网格和小 ROI 连续执行
→ DIRTY / UNKNOWN 立即 STOP
```

正式交互使用 macOS CoreGraphics `CGEvent`；视觉只验证预期按钮、图标、空地/占用 ROI 和少量阶段标志，不做通用场景理解。

## 入口

- Agent 入口：`SKILL.md`
- Runner 当前实施：`IMPLEMENTATION_PLAN.md`
- 未完成事项：`tasks/todo.md`
- 当前现场：`docs/CURRENT.md`
- 稳定玩法规则：`docs/gameplay-rules.md`
- 种子资料：`docs/seed-catalog.md` / `data/seed-catalog.json`
- V2 设计：`docs/superpowers/specs/2026-11-01-deterministic-farm-runner-v2-design.md`
- 历史归档：`docs/archive/README.md`

## 数据边界

`data/seed-catalog.json` 是版本化知识数据；`data/farm-state.json` 是 Runner 当前库存/状态事实文件。库存只在已验证的观察或确认成功的动作后更新；存在手动操作或未知奖励时保持 dirty/uncertain，不猜。
