# 已自动执行历史与统计口径收尾

> 归档日期：2026-09-26。本文只保留完成证据；当前生产口径以 `docs/automation-policy.md`、`docs/INDEX.md`、`SKILL.md` 和生产代码为准。

## 问题与根因

“已自动执行”页面长期未归档的工单出现了“已自动执行 + 待推理 + `node collect.js --sim`”的矛盾展示。调查确认：

- queue 仍保留 `auto_executed` 状态；
- `auto-execution-journal` 仍保留页面动作成功证据；
- `server.js` 启动时对 `simulations.jsonl` 不区分引用状态，直接只保留最新 500 行；
- 前端在 queue 存在但 simulation 缺失时，落入了 legacy 采集提示。

因此平台动作没有丢失，丢失的是本地推理明细。统计页原先直接展示 simulation 行数，并用“全部 simulation - 差评数”计算正确率，同样受到裁剪影响，且会把未评价工单误算为正确。

## 已完成

### 页面与统计

- “已自动执行”页每页 10 条，顶部和底部复用历史记录分页样式，序号跨页连续。
- 异常情况下 queue 仍在但明细缺失时，自动执行卡片不再误显示“待推理”或引导运行 legacy `node collect.js --sim`；改为提示先核对历史备份再归档。
- 累计处理量改为合并实际 queue、归档 case 和现存 live simulation，排除未处理 `pending` 后按工单号去重。
- 已归档数与历史记录可见 case 数一致。
- 已人工评价和正确率按每单最新明确评价计算；未评价工单不再默认为正确。

### 历史数据恢复

- 先归档 228 条当时仍有完整采集与推理结果的自动执行工单。
- 对剩余 83 条逐单核验：83/83 在 `workspace-20260925-164847-43972.tar.gz` 中存在完整 simulation，83/83 在 execution journal 中为 `auto_executed` 且有页面动作成功时间。
- 从备份恢复这 83 条明细后按 `groundTruth.source=auto_executed` 归档，没有重新执行、重新采集或触碰平台按钮。
- 写入后读回确认：83 条 case 全部含 `collectedData + decision`，83 条恢复 simulation 全部含归档时间，对应 queue item 全部为 `done`。

### 防止再次丢失

- `server.js` 启动清理仍保留最新 500 条，但会额外保留所有 `status !== done` queue item 引用的旧 simulation。
- `lib/server/simulation-retention.js` 承载纯函数筛选；无法解析的旧行也保留供人工排查，不在启动清理时静默删除。
- 长期防错规则已进入 `docs/INDEX.md` #82；统计与缓冲口径已进入 `docs/automation-policy.md`。

## 验证与代码记录

- 分页和统计口径改动：全量回归 502 项通过，提交 `3b185f9`。
- simulation 保护改动：全量回归 505 项通过，提交 `23dd4f7`。
- 服务均在 op-queue 空闲时按 `/aftersales-restart` 流程安全重启；重启不自动重采、不自动重跑工单。
- 数据恢复写入前先创建精确临时备份，写入后逐项读回验证；验完后已清理临时目录。

## 当前权威入口

- 自动授权、顶部统计和 simulation 缓冲口径：`docs/automation-policy.md`
- 未归档 simulation 保护红线：`docs/INDEX.md` #82
- 运行时文件地图和失败模式：`SKILL.md`
- 实现：`lib/server/data.js`、`lib/server/simulation-retention.js`、`server.js`、`public/app.js`
- 回归：`test/server/data-stats.test.js`、`test/server/simulation-retention.test.js`、`test/server/live-toolbar-frontend.test.js`

## 未处理

本阶段无剩余项。`tasks/todo.md` 中原有“平台准备发货 + 平台无物流 + ERP 已揽收”独立拒绝分支仍是另一个待实施任务，本阶段未改变其范围或授权。
