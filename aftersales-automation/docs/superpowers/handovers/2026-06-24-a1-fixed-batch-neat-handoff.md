# A1 固定清单逐单处理：Neat 归档交接

日期：2026-06-24
状态：代码草案已补关键纯单测，但仍未交付。禁止真机、禁止接正式 UI/队列、禁止重启、禁止自动执行真实工单。

## 一句话结论

A1 的核心编排已经从“独立脚本草案”拉回原售后系统数据流：固定清单逐单处理结果会写回 `queue.json` / `simulations.jsonl`，并继续进入原三类页面状态：待确认、已自动执行、等待重查。

现在不要继续解释业务口径，也不要急着接入口。下一步只处理一个安全收尾点：自动执行 intent 残留恢复。

## 本阶段已经完成

- 首次读取的 `<=48h` 工单作为本轮不可变清单。
- 步骤 10 翻页读取已等待 loading 消失、页码正确、列表指纹变化并稳定读取。
- 有工单号但倒计时解析失败时停止冻结清单，不再跳过。
- 步骤 14 已写回原系统 queue/simulation，而不是只返回内部 items。
- 非自动执行、列表消失、自动执行成功、等待重查都映射回原系统状态。
- `fixed_batch` 来源的终态 `skip` 已按扫描来源语义进入原“已自动执行”列表。
- 关闭详情 tab 前校验：必须是当前账号鲸灵详情页，不能是售后列表主 tab，不能是 ERP/非鲸灵/其他店铺 tab。
- 账号收尾只关闭当前账号鲸灵非列表 tab，并复核售后列表主 tab 仍匹配当前账号。

## 验证证据

最近一次验证：

```bash
npm test
```

结果：193/193 通过，失败 0。

该验证只代表纯单测通过，不代表真实平台可运行，也不构成真机授权。

## 当前仍禁止

- 禁止运行真实账号批次。
- 禁止接入 `routes.js` / `op-queue.js` / `server.js` 正式入口。
- 禁止重启 server 让草案生效。
- 禁止执行真实 approve/reject。
- 禁止恢复旧 `/api/scan`、`/queue/batch-reprocess`、`/simulations/batch-execute` 链路。
- 禁止把旧 `collect.js` / `pipeline.js` 原样接入步骤 14，避免重新注入、重新导航或跨账号错 tab。

## 真正下一步

只做 `lib/server/auto-execution-journal.js` 的残留 intent 恢复策略。

目标不是自动恢复执行，而是更保守：发现残留 intent 时，阻断该工单再次自动执行，并把它降级到人工待确认。

建议实现口径：

1. journal 里存在未完成 intent 时，同一工单不得再次 `approve`。
2. 同一工单再次进入步骤 14 时，`assertAutoExecutionAllowed` 返回拒绝原因，例如 `存在未完成自动执行 intent，需人工复核`。
3. 被拒绝后仍要写 simulation，queue status 回 `simulated`，显示在原待确认列表。
4. 不自动清理 intent，不自动重试 approve。
5. journal JSON 损坏或读取 EIO 时，继续保持当前策略：抛错停止，不覆盖原文件。

## 下一步应补的测试

- reserve 成功但 approve 未发生：下次同工单禁止自动执行，回待确认。
- reserve 成功、approve 成功但 markExecuted 失败：下次同工单禁止重复自动执行。
- intent 残留时，simulation 保留 `autoBlockedReason` 或同等说明。
- journal JSON 损坏/EIO：不得覆盖原文件，不得视为空日志。

## 暂不处理

点击后 target 枚举异常可能遗留 tab：当前已有保守失败和 `newTargetIds` 清理路径。它仍是风险，但优先级低于自动执行 intent 残留。处理 journal 后再复审是否需要补测试或文档即可。

## 相关文件

- `scripts/jl-steps/14-process-single-account-fixed-batch.js`
- `lib/server/auto-execution-journal.js`
- `test/jl/process-single-account-fixed-batch.test.js`
- `test/server/auto-execution-journal.test.js`
- `docs/superpowers/plans/2026-06-19-a1-fixed-batch-user-confirmation.md`
- `tasks/todo.md`
