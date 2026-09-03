# 2026-09 退货入库稳定性与实时结果阶段交接

状态：代码已完成、测试通过、售后服务已重启并健康；真实业务稳定性仍待下一次正常退货批次顺带观察。当前运行规则以 `../../../SKILL.md` 与 `../../../../return-inbound/SKILL.md` 为准，本文只保存阶段证据和边界。

## 1. 目标

在不重构退货入库主流程、不改变「创建并收货」提交语义、也不增加真实写操作自动重试的前提下，解决三个问题：隔一段时间首次运行前 1–2 单更易异常、ERP 在后台时成功率下降；结果必须每处理一条就显示一条；提供安全停止按钮。

## 2. 根因与最终修复

- 冷启动缺口：`return-inbound/lib/navigate.js` 旧逻辑在已处于「售后工单新版」时直接返回，没有重新确认页面内容就绪。现改为导航前先激活 ERP，即使 hash 已正确也执行 `waitForPageContent()`。
- 后台 Input 缺口：退货入库自己的旧 `lib/cdp.js` 没有售后主项目已有的后台标签页 Input 防护。现 `typeText()` 和 `key()` 在真正发送 `Input.insertText` / `Input.dispatchKeyEvent` 前都会重新激活目标 ERP tab。
- 输入触发缺口：填入单号后不再只靠固定等待直接按 Enter；必须读回目标输入框，确认值等于本次快递单号后才允许搜索。
- 等待参数错误：修正 `navigate.js` 中 `waitFor` / `retry` 的旧参数名，使预期的 timeout、interval、retry 次数真正生效。
- 保留原安全边界：没有给「创建并收货」增加自动重试，没有全局拉长所有 sleep，也没有改订单/仓库/商品选择业务流程。

## 3. Web 行为

- 后端原有 `ri-progress` 每条 SSE 保持不变；前端改为收到 `completed` 就立刻写入并重绘该条结果，不再等 `ri-done` 才生成结果表。
- 批次开始后可看到 `待处理 / 处理中 / 已入库 / 未出库无需入库 / 错误` 的逐条状态。
- 「停止」按钮复用已有 `/api/op-queue/:id` 取消能力，不新增第二套队列。
- 停止采用单条边界语义：当前 `processOne()` 完整结束后，下一条开始前由 `assertNotAborted(op)` 停止；不会在「创建并收货」已经触发但结果尚未确认时中断。
- 停止后保留已完成结果，并显示已处理/未处理数量。

## 4. 当前入口与测试

- 退货入库核心：`return-inbound/lib/workflow.js`、`lib/navigate.js`、`lib/cdp.js`。
- Web 集成：`aftersales-automation/public/app.js`、`public/index.html`、`lib/server/op-queue.js`。
- 新增契约测试：`return-inbound/test/cold-start-contract.test.js`、`aftersales-automation/test/server/return-inbound-ui.test.js`。
- 永久运行约束已写回 `return-inbound/SKILL.md`；下一次真实批次观察项只保存在 `return-inbound/tasks/todo.md`，不在本归档复制第二份待办。

## 5. 验证证据

- `return-inbound`: `node --check lib/cdp.js`、`lib/navigate.js`、`lib/workflow.js` 均通过；`npm test` 最终 `7/7` 通过。
- `aftersales-automation`: `node --check public/app.js` 通过；全量 `npm test` `446/446` 通过；退货入库 Web 专项 `3/3` 通过。
- 未使用真实快递单号做端到端验证，避免为了测试制造实际 ERP「创建并收货」。
- 2026-09-03 已执行 `launchctl kickstart -k gui/501/com.heizong.aftersale-server` 重启售后服务；随后 `/health` 返回 `{"ok":true}`。

## 6. 待自然实测

下次正常真实退货批次重点观察两个历史高风险场景：一是 ERP 闲置较久后的首 1–2 单；二是用户停留在售后系统面板、ERP 不是当前标签页时是否仍稳定。若仍报错，优先根据具体错误位置继续定位，不先追加无差别等待或自动重试。
