# QQ经典农场辅助

项目中文名：QQ经典农场辅助

## Session 启动

1. 读 `SKILL.md`。
2. 读 `docs/CURRENT.md` 和 `tasks/todo.md`。
3. 读 `docs/INDEX.md`，按任务加载玩法规则、种子资料或规划底表。
4. 真机操作前确认平台状态和当前 Chat 的操作授权。

## 当前目标

保留种子资料、土地等级与种植规则、收益和经验计算。QQ 现有 PC 独立脚本继续可用，按需开发具体功能；每次实际种植后，必须更新已知库存记录并创建、核验收菜提醒。

微信真机操作保持封存。旧 Runner 路线已经结束，不再恢复，也不建立无人值守或自恢复执行器。

## 当前工作边界

- 用户未指定平台的农场操作、库存及状态变动，默认指QQ；只有明确说微信农场才按微信记录，微信真机恢复仍需明确授权。

- 当前唯一种植计划：`data/operation-plan.json`。不维护 next plan 或多轮预排文件。
- QQ 真机操作按当前 Chat 对具体平台和动作的明确授权执行。
- 微信真机状态由 `data/wechat-live-status.txt` 控制；`sealed` 期间禁止打开、登录、田内操作和真机补采，只有用户明确决定恢复后才能改变。
- 现役自动化保持独立脚本。不要恢复旧 Runner、自动重试或检查点式自恢复；用户明确授权的单次定时执行以CURRENT记录为准，不自动续排。
- 坐标核对只有在用户明确要求时进行；核对阶段只标点和观察，不执行有业务副作用的动作。
- 当前已验证的本机鼠标输入路径使用 CoreGraphics CGEvent，不通过 AppleScript / System Events 模拟账号内操作。
- 遇到账号安全、重新登录或授权提示立即停止，不处理、不重试。
- 正常固定脚本退出 0 即按动作完成处理，不做例行截图/LLM 复核；显式停止或实际遗漏才排错。种植后的库存和阶段提醒收尾遵循 `SKILL.md`；共享提醒协议见工作区根目录 `docs/reminders.md`。

## Git / 数据边界

- `data/seed-catalog.json`、`data/farm-planning-reference.json`、`data/ui-layout.json`、`data/ui-anchors.json`、`data/home-recognition.json`、`assets/seeds/`、`assets/ui/` 与 `scripts/` 是可版本化知识和工具资产。
- 原始整屏截图、OCR 中间产物、坐标探针和实验脚本放工作区根 `_sandbox/`，不提交。
- 种子数量是最近一次清点加已确认种植扣减后的已知值；不要在每次操作时打开仓库刷新。
