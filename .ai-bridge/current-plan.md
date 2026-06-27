# Aftersales A1 Step 14 Review and op-queue/API Design

Updated: 2026-06-27T05:15:18.438Z
Workspace: /Users/chat/claude
Target agent: Codex (codex)
Model: gpt-5.5-thinking

## Plan

# 目标

只处理 `aftersales-automation` 售后工单系统。不要继续 Codex Monitor；此前 `.ai-bridge/current-plan.md` 的 Codex Monitor quota 计划已完成但未归档，属于旧计划。

当前 A1 状态：账号 14 茗瑞-KGOS 的关闭自动执行最小整账号固定清单批次已验证；正式 UI/队列入口和自动执行真实工单仍未交付。

# 已完成的 CodexPro 补丁

本轮已写回文档：

- `aftersales-automation/docs/superpowers/handovers/2026-06-27-a1-account-14-fixed-batch-handoff.md`
- `aftersales-automation/tasks/todo.md`
- `aftersales-automation/docs/superpowers/plans/2026-06-19-a1-fixed-batch-user-confirmation.md`
- `aftersales-automation/README.md`
- `aftersales-automation/SKILL.md`

本轮已修改 Step 14：

- `aftersales-automation/scripts/jl-steps/14-process-single-account-fixed-batch.js`
- `aftersales-automation/test/jl/process-single-account-fixed-batch.test.js`

补丁内容：

1. 复用旧 queue item 时强制修正 `mode:"live"` / `source:"fixed_batch"`。
2. 翻页、详情处理、关闭 tab 等逐单异常优先写回 `status:"simulated"` 的人工复核 simulation，避免失败工单从原页面语义中消失。
3. 有目标店铺名时，关闭详情 tab 和账号收尾清理必须具备 `readShopName` 店铺态校验依赖；缺失时 fail-closed。
4. 增加 `disableAutoExecute` / CLI `--disable-auto-execute`；命中 approve 也只写回待确认，不执行退款。

验证：

- `cd aftersales-automation && npm test`：209/209 passed。
- 未运行真实浏览器；未访问鲸灵/ERP；未重启 server；未接前端按钮；未真实 approve/reject。

# 下一步任务

## 1. 先审查本轮 Step 14 小补丁

重点确认是否保持 KISS，没有过度设计：

- `createEnsureQueueItem()` 是否只是把原内联逻辑抽出来，且强制 `mode/source` 合理。
- `buildFailureProcessed()` 是否只解决失败可见性，没有引入独立结果系统。
- `disableAutoExecute` 是否足够小，只阻断自动执行路径，不改变采集/推理/写回。
- `assertCurrentAccountShop()` 的 fail-closed 是否会影响测试和真实安全边界；不能为了测试放松真实安全。

不要做大重构。不要拆服务层。不要接前端按钮。

## 2. 设计正式 op-queue/API 入口

只做后端入口设计和可测实现，不接前端按钮。

要求：

- 单账号入口。
- 显式确认账号参数。
- 默认关闭自动执行，相当于传入 `disableAutoExecute:true`。
- 必须走 `lib/server/op-queue.js` 串行化，不允许直接从前端并发触发浏览器操作。
- 不得复用旧 `scan-all.js`、旧 `/api/scan`、旧 `collect.js` / `pipeline.js` 作为 A1 入口。
- 入口应返回/推送进度，但仍写回原 `queue.json`、`simulations.jsonl` 和原三标签页语义。

建议先写测试，再做最小实现。

## 3. 仍禁止事项

- 不得运行真实浏览器业务脚本，除非用户另行指定账号/范围并明确授权。
- 不得访问鲸灵或 ERP。
- 不得重启 server 让正式入口生效。
- 不得接前端按钮。
- 不得真实 approve/reject。
- 不得放开自动执行真实工单。
- 不得把步骤 14 做成独立结果系统。

## 4. 后续但暂不做

- 前端按钮：等后端 op-queue/API 入口有测试并通过后再做。
- 自动执行真实工单：需要单独设计 auto-execution journal 恢复、人工审计和失败闭环。

# 推荐验证

优先运行：

```bash
cd aftersales-automation
npm test
```

如实现 op-queue/API 入口，补对应 node:test 后再跑全量 `npm test`。

# 工作区提醒

当前 `/Users/chat/claude` 工作区不全是售后改动，还存在 `codex-monitor/`、`product-mapping/`、`lkwj/`、根 `docs/` 等既有脏文件。继续本任务时只关注 `aftersales-automation/` 下的 A1 相关文件。

## Implementation contract

- Work from this plan in small, reviewable steps.
- Keep edits scoped to the requested task and existing project conventions.
- Run focused verification before handing work back.
- Update .ai-bridge/agent-status.md with files touched, checks run, results, blockers, and review notes.
- Save the final review diff to .ai-bridge/implementation-diff.patch when practical.
- Append notable execution events to .ai-bridge/execution-log.jsonl when the implementation agent supports logging.
