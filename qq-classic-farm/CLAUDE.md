# QQ经典农场辅助

项目中文名：QQ经典农场辅助

## Session 启动

1. 读 `SKILL.md`。
2. 读 `tasks/todo.md`。
3. 读 `docs/INDEX.md`。
4. 真机操作前读 `docs/CURRENT.md`；再按 SKILL 进入玩法规则或种子资料。

## 稳定目标

本项目不是让 AI 自主“玩游戏”，而是把用户已经确定的重复操作做成本地 deterministic Runner。

职责分工：

- 用户 + ChatGPT / Planner：活动选择、种什么、种多少、成熟时间与库存策略。
- Runner：固定窗口、固定 UI、固定网格和确定性流程执行。
- 视觉：只在限定 ROI 验证预期按钮、图标、空地模板和标志，不做通用场景理解。

正常路径：

```text
EMPTY → PLANTING → GROWING/MATURE → HARVESTING → EMPTY
DIRTY/UNKNOWN → STOP
```

异常优先停止并重新同步，不为部分种植、意外中断或未知 UI 构建复杂自动恢复。

## 安全边界

- QQ、微信及游戏交互只允许 CoreGraphics `CGEvent` 鼠标操作；禁止 AppleScript / System Events 模拟账号内输入。
- 不主动充值、购买付费货币、消费不明确的高级资源，不处理账号安全/授权弹窗。
- 正常路径禁止 Agent 单击级遥控；机械动作必须下沉本地 Runner。
- 固定 UI 使用已校准的 window-local 坐标与局部锚点；UI 与预期不符立即 STOP。
- 自动化风险不能承诺为零；优先使用游戏自身的一键能力。

## Git / 数据边界

- `data/seed-catalog.json`、`data/ui-layout.json`、`data/ui-anchors.json`、`assets/seeds/`、`assets/ui/` 与 `scripts/` 是可版本化知识/工具资产。
- 原始整屏截图、OCR 中间产物、坐标探针和实验脚本放工作区根 `_sandbox/`，不提交。
- 仓库数量是时间点观察值，再次实际操作时必要则刷新。
