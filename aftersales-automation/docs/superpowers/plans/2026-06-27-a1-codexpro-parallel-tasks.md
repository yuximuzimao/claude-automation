# A1 CodexPro Parallel Tasks Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use code review / TDD discipline as appropriate. This plan is for Web CodexPro connected to the local repo. Do not run real browser, JL, ERP, approve, reject, scan, collect, or fixed-batch production commands unless the user gives a separate explicit instruction.

**Goal:** Split the post-verification A1 work into safe, parallel CodexPro-sized tasks: review, test coverage, small patches, and docs synchronization.

**Architecture:** A1 fixed-batch processing remains centered on `scripts/jl-steps/14-process-single-account-fixed-batch.js`. Official entry should progress from controlled CLI behavior to an op-queue/API entry, then a frontend button. Existing old paths (`scan-all.js`, old `/api/scan`, old `collect.js` / `pipeline.js` entry paths) must not be reused as the A1 entry.

**Tech Stack:** Node.js `node:test`, Express routes, local JSON/jsonl data store, Chrome CDP helpers, existing aftersales automation modules.

---

## Current Verified State

- 2026-06-26/27: account `14` (`茗瑞-KGOS`) real 48h fixed-batch run completed.
- Frozen list size: `4`.
- All 4 tickets were located, opened, collected, inferred, persisted, and detail tabs were closed.
- Queue writeback: all 4 are `status: "simulated"`, `source: "fixed_batch"`.
- No automatic execution happened; no `executedAt` or `autoExecutedAt`.
- Final browser state check: one JL tab left, on after-sale list.
- Test baseline before this task split: `npm test` passed `204/204`.

## Hard Safety Rules For CodexPro

- Do not run:
  - `node scripts/jl-steps/14-process-single-account-fixed-batch.js ...`
  - `node scripts/jl-steps/open-account.js ...`
  - `node cli.js approve ...`
  - `node cli.js reject ...`
  - `node cli.js read-ticket ...`
  - `node cli.js logistics ...`
  - `node cli.js erp-* ...`
  - `node scan-all.js`
  - `node collect.js`
  - any command that opens or manipulates JL/ERP browser tabs.
- Allowed commands:
  - `npm test`
  - `node --test <specific test files>`
  - `node --check <file>`
  - `rg`, `sed`, `git diff`, `git status`, `nl`
- Do not edit runtime data files under `data/`.
- Do not add or expose any frontend button that can trigger real account processing unless the specific task says so.
- If a test requires browser state, write it as a dependency-injected unit test instead.

---

## Recommended Assignment Order

Give CodexPro these in order:

1. Task 1: Docs synchronization. ✅ Completed.
2. Task 2: Step 14 small safety patch and tests. ✅ Completed.
3. Task 3: CLI controllability tests. ✅ Completed.
4. Task 4: op-queue/API design review and backend/frontend no-auto entry. ✅ Completed.
5. Task 5: Live tab store filter and legacy cleanup review + scoped implementation. ✅ Completed 2026-06-27.
6. Task 6: Auto-execution journal recovery design. ✅ Completed 2026-06-27 as design-only.

Current remaining CodexPro-sized work is Task 7: frontend button load/smoke plan only. Keep real fixed-batch runs, server restart, and true approve/reject automatic execution under direct user/operator control.

For the 2026-06-27 user request about `待确认` / `等待重查` store filters and old/new logic cleanup, implementation is now complete. The plan remains archived in place at `docs/superpowers/plans/2026-06-27-live-tab-store-filter-and-legacy-cleanup.md`, with neat handoff at `docs/superpowers/handovers/2026-06-27-live-tab-store-filter-neat-handoff.md`.

For Task 6, recovery design is complete at `docs/superpowers/plans/2026-06-27-auto-execution-journal-recovery-design.md`. It explicitly requires manual recovery to update journal + queue + simulation/audit + execution gates together; `manually_resolved` is audit closure, not automatic re-release.

---

### Task 1: Sync A1 Docs After Account 14 Full-Batch Verification

**Best fit for CodexPro:** Yes. This is low-risk documentation work.

**Files:**
- Modify: `tasks/todo.md`
- Modify: `docs/superpowers/plans/2026-06-19-a1-fixed-batch-user-confirmation.md`
- Modify or create: `docs/superpowers/handovers/2026-06-27-a1-account-14-fixed-batch-handoff.md`
- Optionally modify: `README.md`
- Optionally modify: `SKILL.md`

**Prompt To Give CodexPro:**

```text
你在 /Users/chat/claude/aftersales-automation。请只做文档同步，不改代码，不运行真实浏览器或业务脚本。

背景：
- A1 account 14 茗瑞-KGOS 的 48h fixed-batch 真机全量验证已成功。
- 冻结清单 4 张；4 张均完成列表定位、详情 tab、采集、推理、写回 queue/simulation、关闭详情 tab。
- 4 张结果均为 queue status simulated，source fixed_batch；没有自动执行，没有 executedAt/autoExecutedAt。
- 收尾后只剩 1 个鲸灵售后列表主 tab。
- npm test 曾通过 204/204。

请更新：
1. tasks/todo.md：把“整账号固定清单批处理未验证”改为“账号14最小整账号批次已验证”，同时保留“正式入口未交付、自动执行真实场景未放开”的门禁。
2. docs/superpowers/plans/2026-06-19-a1-fixed-batch-user-confirmation.md：补充账号14验证证据和剩余正式入口前缺口。
3. 新建 docs/superpowers/handovers/2026-06-27-a1-account-14-fixed-batch-handoff.md：写明验证对象、结果摘要、仍禁止事项、下一步。
4. 如果 README.md 或 SKILL.md 仍写“整账号批处理未验证”，同步改成“账号14最小整账号批次已验证；正式 UI/队列入口未交付”。

禁止输出或写入任何收件人、电话、地址等个人信息。

验证：
- rg -n "整账号固定清单批处理.*未验证|下一步.*最小批次|账号 14|204/204" tasks docs README.md SKILL.md
- git diff -- tasks docs README.md SKILL.md

交付：列出修改文件和关键文案变化。
```

**Acceptance Criteria:**
- Docs no longer imply that no full-account fixed-batch validation has happened.
- Docs still clearly say formal UI/op-queue entry is not delivered.
- Docs still clearly say real auto-execution expansion requires separate work.
- No personal recipient data is added.

---

### Task 2: Step 14 Safety Patch For Queue Reuse And Failure Visibility

**Best fit for CodexPro:** Yes, if limited to unit-testable small patch.

**Files:**
- Modify: `scripts/jl-steps/14-process-single-account-fixed-batch.js`
- Modify: `test/jl/process-single-account-fixed-batch.test.js`

**Issues To Fix:**
- `ensureQueueItem` reuses an unfinished existing queue item but does not force `mode: "live"` and `source: "fixed_batch"`.
- Per-item processing failure currently sets in-memory `item.status = "failed"` and throws, but does not persist a visible queue/simulation failure result.
- `cleanupCurrentAccountJlTargets` has a fallback where missing `readShopName` can weaken account-boundary checks. Default dependencies are safe, but the helper should fail closed when account matching is required.

**Prompt To Give CodexPro:**

```text
你在 /Users/chat/claude/aftersales-automation。请做一个小补丁，必须 TDD，禁止运行真实浏览器或业务脚本。

目标：
1. 在 scripts/jl-steps/14-process-single-account-fixed-batch.js 的默认 ensureQueueItem 中，复用已有未完成 queue item 时也强制 patch mode:'live' 和 source:'fixed_batch'。
2. 当某一张 fixed_batch 工单处理失败时，尽量写回原系统可见结果：queue status 回 simulated，append simulation，decision.action='escalate' 或类似人工复核语义，reason 包含 fixed_batch 失败原因；然后仍停止批次。
3. cleanupCurrentAccountJlTargets / close detail 的当前账号校验，在有 account.matchedNote 时必须要求 readShopName 依赖存在；缺失时抛错，不允许降级为关闭所有鲸灵 tab。

只改：
- scripts/jl-steps/14-process-single-account-fixed-batch.js
- test/jl/process-single-account-fixed-batch.test.js

先写失败测试，再实现。

建议测试名：
- 复用旧queue item时强制修正mode和source为live/fixed_batch
- 详情处理失败时写回simulated人工复核simulation后停止批次
- 有目标店铺名但缺readShopName时拒绝账号收尾清理

验证：
- node --test test/jl/process-single-account-fixed-batch.test.js
- npm test

禁止运行：
- node scripts/jl-steps/14-process-single-account-fixed-batch.js 14
- node cli.js read-ticket/logistics/approve/reject
- node scan-all.js
- node collect.js

交付：说明测试 RED/GREEN 结果、修改点、剩余风险。
```

**Acceptance Criteria:**
- Existing queue item reuse cannot leave fixed_batch results attached to a non-live/non-fixed_batch queue item.
- A failed item is visible in the original pending/manual-review semantics instead of only appearing in CLI output.
- Account tab cleanup fails closed if shop identity cannot be verified.
- `node --test test/jl/process-single-account-fixed-batch.test.js` passes.

---

### Task 3: CLI Controllability And No-Auto Mode Tests

**Best fit for CodexPro:** Yes, small unit-testable patch. This can run in parallel with Task 2 only if both agents coordinate on the same test file. Prefer sequential after Task 2 to avoid conflicts.

**Files:**
- Modify: `scripts/jl-steps/14-process-single-account-fixed-batch.js`
- Modify: `test/jl/process-single-account-fixed-batch.test.js`

**Prompt To Give CodexPro:**

```text
你在 /Users/chat/claude/aftersales-automation。请补步骤14的 CLI 可控性测试和必要的小实现，禁止真实浏览器操作。

目标：
1. runCli 可以通过注入 dependencies 做纯单测，合法账号输出 JSON 并返回 0。
2. 非法 accountNum 返回 1，且不调用 openAccountFlow。
3. 为未来正式入口预留 no-auto / dry-run-auto 开关：当 options.disableAutoExecute === true 时，即使 decision.action='approve' 且 shouldAutoExecute 原本会返回 true，也必须写 simulated，不调用 executeDecision。

注意：
- 不要默认改变当前生产 CLI 行为，除非任务中明确有参数。
- 如果加 CLI flag，优先用显式安全命名，例如 --disable-auto-execute。
- 测试必须通过 dependency injection，不运行真实脚本。

验证：
- node --test test/jl/process-single-account-fixed-batch.test.js
- npm test

交付：说明新增 API/flag、测试覆盖和是否改变默认行为。
```

**Acceptance Criteria:**
- There is a tested way for op-queue/API entry to call fixed-batch with automatic execution disabled.
- Default behavior is explicit and documented in code/tests.
- Tests do not touch real browser state.

---

### Task 4: op-queue/API Entry Design Or Small Patch

**Best fit for CodexPro:** Good for planning or first small backend patch. Do not assign frontend button yet.

**Files For Design Review:**
- `lib/server/op-queue.js`
- `lib/server/routes.js`
- `test/server/`
- `scripts/jl-steps/14-process-single-account-fixed-batch.js`

**Preferred First Ask: design only.**

**Prompt To Give CodexPro:**

```text
你在 /Users/chat/claude/aftersales-automation。请只做 op-queue/API 入口设计审查，不改代码。

目标：为 A1 fixed_batch 增加正式受控入口，但第一版只允许单账号、必须显式确认、默认关闭自动执行或要求显式参数。

请设计：
1. 新 op-queue 类型名称，例如 fixed-batch-account。
2. 新 API 路由，例如 POST /api/accounts/:num/fixed-batch。
3. 参数门禁：confirmed 必须为 true；account num 必须合法；默认 disableAutoExecute=true，或明确说明是否允许真实自动执行。
4. 如何调用 scripts/jl-steps/14-process-single-account-fixed-batch.js，不走 scan-all.js、collect.js、pipeline.js、sessions/jl.js inject。
5. 需要新增哪些测试文件和测试名。
6. 前端按钮暂不接，最多说明后续按钮位置。

禁止运行真实浏览器或业务脚本。

交付：一份具体设计，列文件、函数、测试命令和风险。
```

**If User Wants CodexPro To Implement A Small Backend Patch:**

Only after Task 2/3 are merged, ask it to implement:

- `op-queue` new type `fixed-batch-account`
- route `POST /api/accounts/:num/fixed-batch`
- tests proving it does not use old `scan`/`pipeline`/`collect`

**Acceptance Criteria For Implementation:**
- New route enqueues only one account.
- Missing confirmation is rejected.
- New op calls fixed-batch script/module with no-auto mode unless explicitly allowed.
- Tests prove old paths are not used.

---

### Task 5: Review Live Tab Store Filter And Legacy Cleanup ✅ Completed 2026-06-27

**Status:** Completed. Review found the expected high-risk issue: UI filtering without backend scope would still batch hidden stores. Implementation now has frontend store filters, explicit request scopes, backend validation, tests, and neat handoff.

**Plan File:**
- `docs/superpowers/plans/2026-06-27-live-tab-store-filter-and-legacy-cleanup.md` — archived in place, not moved to a new archive directory.

**Handoff:**
- `docs/superpowers/handovers/2026-06-27-live-tab-store-filter-neat-handoff.md`

**Original User Requirement Summary:**
- Add `全部` plus store/account filters to `待确认` and `等待重查`.
- Preserve current deadline/urgency sorting.
- When one store is selected, batch actions must apply only to that store, not hidden stores.
- Review old logic after the new A1 flow has been introduced; classify what is still reused, what is transitional, and what must not be reused.
- Do not create another local archive directory for old files. Either delete with git history as archive, or keep in place with clear classification.

**Prompt To Give CodexPro:**

```text
你在 /Users/chat/claude/aftersales-automation。请只做审查，不改代码，不运行真实浏览器或业务脚本。

请审查 docs/superpowers/plans/2026-06-27-live-tab-store-filter-and-legacy-cleanup.md，并结合当前源码判断：

1. 需求是否描述完整：待确认/等待重查店铺筛选、全部视角、仍按时效排序、筛选后批量操作只作用于当前店铺。
2. 推荐解释是否合理：等待重查默认只允许批量重来，不允许批量执行。若你不同意，请说明业务和安全理由。
3. 前端方案是否会造成“看起来筛选了，实际后端全量执行”的风险；如有，指出必须补的后端门禁。
4. 后端 batch-execute / batch-reprocess 的 accountNum 和 statusScope 设计是否足够 fail-closed。
5. 旧逻辑分类是否准确：哪些是新 A1 入口、哪些是仍复用的原系统语义、哪些是 transitional legacy、哪些是禁止作为 A1 入口的旧路径。
6. 是否有遗漏的测试、文档或迁移风险。

禁止运行：
- node scripts/jl-steps/14-process-single-account-fixed-batch.js ...
- node scripts/jl-steps/open-account.js ...
- node scan-all.js
- node collect.js
- node cli.js approve/reject/read-ticket/logistics/erp-*
- 任何会打开或操作 JL/ERP/Chrome 的命令

允许运行：
- rg
- sed
- nl
- git diff
- git status
- node --check <file>

请输出：
- 高风险问题（按严重度排序，带文件/行号）
- 需求歧义或需要用户确认的问题
- 建议修改计划
- 不要直接修改文件
```

**Acceptance Criteria:**
- GPT review explicitly addresses scoped batch action risk.
- GPT review distinguishes UI filtering from backend action scope.
- GPT review challenges or accepts the “waiting tab only batch reprocess” interpretation.
- GPT review identifies which old paths should be forbidden as A1 entries.

---

### Task 6: Auto-Execution Journal Recovery Design ✅ Completed 2026-06-27

**Best fit for CodexPro:** Design/review now; implementation later.

**Status:** Design-only completed at `docs/superpowers/plans/2026-06-27-auto-execution-journal-recovery-design.md`. No code implementation, no CLI recovery command, no true automatic execution enablement.

**Design Conclusion:** `auto-execution-journal` must become an audit/recovery ledger, not a retry helper. Any page-action uncertainty must block blind retry. Human recovery must close journal, queue, simulation/audit, and execution gates together; resolving only the journal is forbidden because it can hide a hazardous queue/simulation state.

**Why Not First:** It affects real refund execution semantics. It should not block a no-auto official entry, but must be solved before expanding true automatic execution.

**Files:**
- `lib/server/auto-execution-journal.js`
- `scripts/jl-steps/14-process-single-account-fixed-batch.js`
- `test/server/auto-execution-journal.test.js`
- `test/jl/process-single-account-fixed-batch.test.js`

**Prompt To Give CodexPro:**

```text
你在 /Users/chat/claude/aftersales-automation。请只做自动执行 journal 恢复策略设计，不改代码。

当前问题：
- reserve 后 approveTicket 失败或 markExecuted 失败，会留下 auto_executing intent。
- 这能防重复执行，但没有可运营恢复路径。
- 步骤 14 也没有把 auto_executing 中间态写回 queue，自动执行失败没有降级为 simulated + autoExecuteError。

请设计：
1. journal 状态机：auto_executing / auto_executed / failed / manually_resolved。
2. 哪些失败可以自动转 simulated，哪些必须阻断并等待人工确认。
3. 如何避免“退款其实成功但 markExecuted 失败”导致误重试。
4. 需要的 API 或 CLI 恢复入口。
5. 测试矩阵。

禁止实现真实自动执行放开。
交付：设计结论和推荐分阶段实施顺序。
```

**Acceptance Criteria:**
- Design distinguishes page-action uncertainty from pure writeback failure.
- No proposal allows blind retry of approve/reject.
- There is a human-auditable recovery path.

---

### Task 7: Frontend Button Load/Smoke Plan Only

**Best fit for CodexPro:** Planning only for now.

**Do Not Implement Yet.**

**Current Reality:** The single-account no-auto fixed-batch button code already exists and is covered by tests. The remaining planning task is how to load it safely, smoke-test UI behavior, and avoid duplicating or changing the already implemented button.

**Prompt To Give CodexPro:**

```text
你在 /Users/chat/claude/aftersales-automation。请只设计前端入口，不改代码。

目标：为已经接入代码但尚未重启加载的单账号 no-auto “A1固定清单”按钮做加载/冒烟计划，不新增第二套按钮，不改现有按钮逻辑。

要求：
- 先核对当前实现：按钮只对 ok + 有 session 文件的账号显示；expired/error/unknown 不得入队 fixed-batch。
- 点击后只能调用新的 `POST /api/accounts/:num/a1-fixed-batch`，不得调用 `/api/scan`、batch-reprocess、batch-execute。
- UI 文案必须清楚说明：单账号、48小时固定清单、串行处理、默认关闭真实自动执行、可能写入待确认，不是批量全店铺扫描。
- 设计 server restart 后的只读/UI smoke 检查步骤，但不要实际重启 server、不要点击真实按钮、不要跑 fixed-batch。
- 如果发现按钮已偏离旧售后系统功能或现有测试约束，输出风险和补丁建议，不直接改代码。

请输出设计和测试点，不改代码。
```

---

## Work I Recommend Keeping In Main Session

Keep these out of CodexPro unless explicitly needed:

- Running real fixed-batch against account 14 or any other account.
- Starting/restarting the launchd server.
- Restarting/loading the frontend button into the running production server or clicking it against a real account.
- Any true approve/reject automatic execution test.
- Deciding whether automatic execution should be enabled in the official entry.

These require live browser/account context and should stay under direct operator control.

---

## Summary For User

Best CodexPro tasks right now:

1. Docs sync: safe and immediately useful.
2. Step 14 safety patch: small, testable, no browser.
3. CLI/no-auto tests: useful before op-queue entry.
4. op-queue/API design: good planning task.
5. Live tab store filter and legacy cleanup: completed and archived in place.
6. Auto-exec recovery: design completed; implementation remains future gated work.
7. Frontend button load/smoke plan: next suitable CodexPro task is planning only, not restart or implementation.

Do not ask CodexPro to run real fixed-batch, restart server, or enable true approve/reject automatic execution from this plan. Those remain direct operator-controlled actions.
