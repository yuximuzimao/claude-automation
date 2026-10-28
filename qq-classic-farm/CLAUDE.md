# QQ经典农场辅助

项目中文名：QQ经典农场辅助

## Session 启动

1. 读 `SKILL.md`。
2. 读 `tasks/todo.md`。
3. 读 `docs/INDEX.md`。
4. 实际操作前读 `docs/CURRENT.md`；按 SKILL 再进入玩法规则或种子资料。

## 稳定项目目标与安全边界

目标：在用户不方便操作时，可靠地完成 QQ / 微信《QQ经典农场》的状态识别、收获、种植与后续活动决策，并逐步把稳定机械步骤下沉为轻量脚本。

安全边界：
- QQ、微信及游戏交互只允许 CoreGraphics `CGEvent` 鼠标操作；禁止 AppleScript / System Events 模拟账号内输入。
- 不主动充值、购买付费货币、消费不明确的高级资源，不处理账号安全/授权弹窗。
- 画面位置可移动；每轮以当前窗口与截图重新定位，禁止盲点。
- 自动化风险不能承诺为零；优先低频、少点击、使用游戏内“一键”能力。
- 当前阶段优先验证规则，不为尚未稳定的流程提前构建固定坐标脚本。

## Owner

| 文档 | 加载时机 |
| --- | --- |
| `docs/gameplay-rules.md` | 收获、种植、化肥、土地、成熟状态判断与日常交互 |
| `docs/seed-catalog.md` | 种子库存、图标、资料读取 |

## Git / 数据边界

- `data/seed-catalog.json`、`data/ui-layout.json`、`data/ui-anchors.json`、`assets/seeds/`、`assets/ui/` 与 `scripts/` 是可版本化知识/工具资产；原始整屏截图和一次性探针仍只放工作区 `_sandbox/`。
- 仓库数量属于时间点观察值，必须带观察语义，不当作实时真值；再次实际操作时必要则刷新。
- 原始全屏截图、OCR 中间产物、坐标探针和实验脚本放工作区根 `_sandbox/`，不提交。
