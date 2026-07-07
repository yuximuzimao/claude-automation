# A1 账号 14 最小整账号固定清单批次交接

> 2026-07 状态覆盖：本交接文档记录的是 2026-06-27 no-auto 验证阶段。当前版本已继续推进：fixed-batch 前端按钮、后端 API、op-queue 和 Step14 自动执行门禁均已运行；不再以本文“真实自动执行未交付”为当前状态。

> 日期：2026-06-27  
> 状态：账号 14 茗瑞-KGOS 的关闭自动执行最小整账号固定清单批次已验证；后端 op-queue/API 入口已接入并经审查加固；前端单账号 no-auto 入队按钮代码已接入；自动执行真实工单仍未交付。

## 结论

A1 已从“单工单完整采集验证”推进到“单账号最小整账号固定清单批次验证”。这证明步骤 14 的 no-auto 固定清单串行链路可以在真实页面下完成多张工单的列表定位、详情 tab、采集、推理、写回和关闭详情 tab。

但这仍未在运行中的 server 生效。当前已接后端 op-queue/API 入口并补齐审查风险，前端按钮代码也已接入；但没有重启加载正式入口，也没有放开真实 approve/reject。

## 验证对象

- 账号：`14`
- 店铺备注：`茗瑞-KGOS`
- 验证范围：48 小时内固定清单，关闭自动执行
- 冻结清单：4 张工单
- 执行边界：只采集、推理和写回原售后系统语义；不真实同意、不真实拒绝

## 结果摘要

- 4 张工单均完成列表定位。
- 4 张工单均打开并锁定各自详情 tab。
- 4 张工单均完成采集和推理。
- 4 张工单均写回原系统 `queue.json` / `simulations.jsonl` 语义。
- 4 张工单的 queue writeback 均为 `status:"simulated"`、`source:"fixed_batch"`。
- 没有发生自动执行；没有 `executedAt` 或 `autoExecutedAt`。
- 每张工单处理后详情 tab 已关闭。
- 收尾后浏览器只剩 1 个鲸灵售后列表主 tab。

## 仍禁止事项

- 不得重启 server 让正式入口生效。
- 不得真实 approve/reject。
- 不得放开自动执行真实工单。
- 不得把步骤 14 做成独立结果系统；仍必须写回原 `queue.json`、`simulations.jsonl` 和原三标签页语义。
- 不得复用旧 `scan-all.js`、旧 `/api/scan`、旧 `collect.js` / `pipeline.js` 作为 A1 正式入口。

## 2026-06-27 CodexPro 第一轮补丁结果

本轮只处理 `aftersales-automation`，没有继续修改 Codex Monitor、product-mapping、lkwj 或其他项目。

已完成：

1. 文档同步：`tasks/todo.md`、本确认计划、`README.md`、`SKILL.md` 均已从“最小整账号批次未验证”同步为“账号 14 no-auto 最小整账号批次已验证；当时正式入口仍未交付”。
2. Step 14 safety patch：复用旧 queue item 时强制修正为 `mode:"live"` / `source:"fixed_batch"`，避免旧来源语义污染固定清单状态流转。
3. 失败可见性：翻页、详情处理、关闭 tab 等逐单异常会优先写回 `status:"simulated"` 的人工复核 simulation，不再只在进度里标记 `failed` 后直接抛错。
4. 账号边界 fail-closed：只要当前上下文有目标店铺名，关闭详情 tab 和账号收尾清理都必须具备 `readShopName` 店铺态校验依赖；缺失时拒绝关闭，避免误关其他账号或用户手动鲸灵 tab。
5. CLI/no-auto：`processSingleAccountFixedBatch(..., { disableAutoExecute:true })` 和 CLI `--disable-auto-execute` 会禁止自动执行路径；即使命中 approve，也只写回待确认并记录 `autoBlockedReason`。

已验证：

- `npm test`：209/209 通过。
- 未运行真实浏览器、未访问鲸灵/ERP、未重启 server、未接前端按钮、未真实 approve/reject。

## 2026-06-27 CodexPro 第二轮后端入口结果

已完成：

1. 新增后端入口 `POST /api/accounts/:num/a1-fixed-batch`，只接收显式单账号参数。
2. 入口校验账号存在和 session 文件存在，失败时拒绝入队。
3. 入队走 `op-queue` 串行化，类型为 `a1-fixed-batch`，默认 `thresholdHours:48` 且强制 `disableAutoExecute:true`。
4. 未接前端按钮、未重启 server、未运行真实浏览器、未访问鲸灵/ERP、未真实 approve/reject。

## 2026-06-27 GPT 审查后加固结果

已完成：

1. 固定清单入口复用账号状态门，读取 `data/account-status.json`；状态读取失败直接 fail-closed，`expired/error` 不支持 `confirmed:true` 绕过。
2. 入队前预检 session 文件：文件名必须匹配当前账号 `account<num>.json`，realpath 必须在 `../sessions` 内，JSON 必须可解析，且必须包含鲸灵认证 Cookie 和目标域身份 localStorage。
3. `op-queue` 执行层也强制 `thresholdHours:48` 和 `disableAutoExecute:true`，即使有人绕过 API 注入异常参数也不会放开。
4. 新增负边界测试覆盖异常账号、状态文件读取失败、坏 session JSON、路径穿越、错号文件名、缺认证信息、body 参数注入和队列层参数篡改。

已验证：

- 窄测：49/49 通过。
- 全量 `npm test`：216/216 通过。
- 提交：`52a85fd aftersales: harden fixed-batch entry guards`。

## 2026-06-27 前端按钮代码接入结果

已完成：

1. 店铺管理账号卡片新增 `A1固定清单` 小按钮，仅 `hasFile=true` 且 `status=ok` 的账号显示。
2. 点击按钮先弹二次确认，再调用 `POST /api/accounts/:num/a1-fixed-batch`；前端不传 `thresholdHours`、`disableAutoExecute` 或账号数组。
3. 成功/失败只展示 toast，并刷新队列面板状态；不会绕过后端状态/session 门禁。
4. 未重启 server、未点击按钮、未运行真实浏览器、未访问鲸灵/ERP、未真实 approve/reject。

已验证：

- 窄测：59/59 通过。
- 全量 `npm test`：219/219 通过。

## 下一步

1. 用户明确授权后，重启 server 加载后端 route 和前端按钮。
2. 只做 UI smoke test：确认账号 14 按钮可见、点击后能入队或正确展示后端错误；不放开真实 approve/reject。
3. 自动执行真实工单前，再单独处理 auto-execution journal 的恢复、人工审计和失败闭环。

前端按钮代码已排在后端入口和测试之后完成；运行验证仍等待用户授权重启。
