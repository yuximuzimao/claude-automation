# Live Tab Store Filter And Legacy Cleanup Review Plan

> **For GPT/CodexPro reviewers:** This is a review-first plan. Do not edit code during the first pass. Do not run real browser, JL, ERP, scan, collect, approve, reject, fixed-batch, or account-opening commands. Use read-only commands such as `rg`, `sed`, `nl`, `git diff`, `git status`, `node --check`, and unit tests only if explicitly asked after review.

**Goal:** Add store/account-scoped views and batch actions to the existing `待确认` and `等待重查` tabs while preventing old scan/collect/pipeline entry points from confusing the new A1 fixed-batch flow.

**Architecture:** The original three live tabs remain the source of truth: `待确认`, `已自动执行`, `等待重查`. Store filtering is a view and action scope on top of the existing queue/simulation data; it must not create a new business status or a parallel result page. Batch actions must pass an explicit server-validated scope so a filtered UI cannot accidentally enqueue all stores.

**Tech Stack:** Node.js, Express routes in `lib/server/routes.js`, FIFO op queue in `lib/server/op-queue.js`, frontend in `public/index.html` and `public/app.js`, tests with `node:test`.

---

## Original User Requirement

1. Add a store/account filter view to both `待确认` and `等待重查` tabs.
2. The filter must include an `全部` option.
3. Sorting must remain by urgency/deadline, not by store.
4. After selecting one store, the user should be able to run batch actions for that store only.
5. `批量重来` and `批量执行` must not silently operate on hidden stores when the UI is filtered.
6. Because new A1 logic has been introduced, old logic must be reviewed so it does not confuse or interfere with the new logic.
7. Old code that is not reused should either be removed and preserved only by git history, or explicitly classified as retained legacy code. Do not create another local “old uncommitted files” archive.

## Recommended Interpretation To Review

- `待确认` should support:
  - store filter: `全部` plus each visible store.
  - `批量执行` scoped to the selected store or all stores.
  - `批量重来` scoped to the selected store or all stores.
- `等待重查` should support:
  - store filter: `全部` plus each visible store.
  - `批量重来` scoped to the selected store or all stores.
  - no `批量执行` by default, because `waiting` means “do not execute yet; recheck first”.
- This interpretation should be challenged during review. If GPT believes `等待重查` should expose `批量执行`, it must explain the business semantics and safety guard needed.

## Current Code Facts

- `public/app.js` already sorts all live queue items by `deadlineAt` fallback `urgency`.
- `public/app.js` currently splits sorted items into:
  - pending tab: status not `waiting` and not `auto_executed/auto_executing`.
  - waiting tab: status `waiting`.
  - auto tab: status `auto_executed/auto_executing`.
- `batchExecute()` currently posts `{}` to `/api/simulations/batch-execute`.
- `batchReprocess()` currently posts `{}` to `/api/queue/batch-reprocess`.
- `/api/simulations/batch-execute` currently selects executable simulations without account/store scope.
- `/api/queue/batch-reprocess` currently selects all live queue items except `done`, `auto_executed`, and `auto_executing`; it does not respect the active tab or store filter.
- `op-queue` is FIFO. It does not reorder batch operations by store after enqueue.
- The only current account-sort logic found is in old scan finalization, not in the two restored toolbar buttons.

## Proposed Implementation Shape

### Frontend Scope

Files:
- Modify: `public/index.html`
- Modify: `public/app.js`
- Test: `test/server/live-toolbar-frontend.test.js` or a new `test/server/live-tab-filter-frontend.test.js`

Expected UI behavior:
- Add a compact store selector in the toolbar of `待确认`.
- Add a compact store selector in the toolbar of `等待重查`.
- Selector values:
  - `全部`
  - one option per `accountNum`/`accountNote` present in that tab’s current items.
- The selected option filters only that tab’s list and count display.
- Ordering inside the filtered result remains the existing urgency/deadline order.
- Counts should make scope visible, for example `3/12` when a store filter shows 3 of 12 tab items.
- Batch buttons must call APIs with an explicit body:
  - pending all: `{ "statusScope": "pending" }`
  - pending single store: `{ "statusScope": "pending", "accountNum": 14 }`
  - waiting all: `{ "statusScope": "waiting" }`
  - waiting single store: `{ "statusScope": "waiting", "accountNum": 14 }`

Review questions:
- Should selectors persist per tab across reloads, or reset to `全部`? Recommended first version: reset to `全部`.
- Should options be keyed by `accountNum` or `accountNote`? Recommended: key by `accountNum`, display `accountNote || 账号<num>`.
- If `accountNum` is missing, should those items appear under `未知店铺`? Recommended: keep them under `全部` only and exclude them from single-store scoped actions until data is fixed.

### Backend Scope

Files:
- Modify: `lib/server/routes.js`
- Test: add `test/server/live-batch-scope.test.js` or extend an existing route-level test file.

Expected route behavior:
- `/api/simulations/batch-execute` accepts optional:
  - `accountNum`: positive integer account id.
  - `statusScope`: only `pending` for the new UI path.
- It must filter executable candidates by the queue item’s `accountNum` when provided.
- It must not execute `waiting` queue items.
- It should enqueue in the same urgency/deadline order as the page, not simulation creation order, when a UI scoped batch request is used.
- Response should include scope metadata:
  - `count`
  - `approveCount`
  - `rejectCount`
  - `scopeAccountNum`
  - `statusScope`
- `/api/queue/batch-reprocess` accepts optional:
  - `accountNum`: positive integer account id.
  - `statusScope`: `pending`, `waiting`, or `all`.
- `statusScope: "pending"` means pending tab items only: live items not `waiting`, not `done`, not `auto_executed`, not `auto_executing`.
- `statusScope: "waiting"` means live items with status `waiting` only.
- `statusScope: "all"` means current legacy broad behavior, but this should not be the default button behavior.
- Both routes should reject invalid `accountNum` and invalid `statusScope` with HTTP 400.

Review questions:
- Should no-body calls preserve old broad behavior for backward compatibility? Recommended: yes for now, but frontend must always send explicit `statusScope`.
- Should backend require explicit `statusScope` for all future calls? Recommended follow-up after old caller audit.

### Tests

Minimum expected tests:
- Frontend source test: pending toolbar contains store filter and sends scoped body for `batchExecute` / `batchReprocess`.
- Frontend source test: waiting toolbar contains store filter and scoped `批量重来`, but not `批量执行`.
- Frontend pure-function test if helpers are extracted: filtering by `accountNum` keeps deadline order.
- Backend test: `batch-execute` with `accountNum:14` enqueues only executable simulations whose queue item belongs to account 14.
- Backend test: `batch-reprocess` with `statusScope:"waiting", accountNum:14` enqueues only waiting account 14 items.
- Backend test: invalid `accountNum` or `statusScope` returns 400 and does not enqueue.

Allowed verification commands after implementation:

```bash
node --test test/server/live-toolbar-frontend.test.js test/server/live-batch-scope.test.js
node --check public/app.js
node --check lib/server/routes.js
npm test
```

Do not run real-browser or business commands as part of this task.

## Legacy Cleanup And Classification Requirement

The first pass should be a review, not deletion. Classify code into one of four buckets:

1. **New A1 entry path**
   - `lib/server/a1-fixed-batch-entry.js`
   - `lib/server/op-queue.js` type `a1-fixed-batch`
   - `scripts/jl-steps/14-process-single-account-fixed-batch.js`
   - target-aware collectors used by step 14

2. **Original system semantics still reused**
   - queue/simulation data model
   - `public/app.js` live tabs, archive, feedback, and history flows
   - `lib/infer.js` and rule helpers
   - auto-execution confidence and journal logic when explicitly authorized

3. **Transitional legacy code requiring strict scope**
   - `lib/server/pipeline.js`
   - `collect.js`
   - `cli.js` collect/read helpers
   - current manual `batch-reprocess` and `batch-execute` routes until they are replaced or scoped

4. **Old unsafe entry points not to reuse for A1**
   - `scan-all.js`
   - old `/api/scan`
   - `server.js` `runAutoScan` / `scheduleNextScan` framework
   - any route or button that can start multi-account scan or old pipeline without an explicit account/store scope

Recommended cleanup policy:
- Do not create a local archive folder.
- If old code is deleted, git history is the archive.
- If old code is retained, add clear comments/docs saying whether it is active, transitional, or forbidden as an A1 entry.
- Do not remove `pipeline.js` or `collect.js` in the first pass if restored batch buttons still depend on them. Instead, scope and document them.
- Consider returning 410 or hiding UI for old unsafe entry points only after a caller audit proves they are not needed.

## GPT Review Prompt

Use this exact prompt for the first GPT/CodexPro review:

```text
你在 /Users/chat/claude/aftersales-automation。请只做审查，不改代码，不运行真实浏览器或业务脚本。

请审查 docs/superpowers/plans/2026-06-27-live-tab-store-filter-and-legacy-cleanup.md，并结合当前源码判断：

1. 需求是否描述完整：待确认/等待重查店铺筛选、全部视角、仍按时效排序、筛选后批量操作只作用于当前店铺。
2. 推荐解释是否合理：等待重查默认只允许批量重来，不允许批量执行。若你不同意，请说明业务和安全理由。
3. 前端方案是否会造成“看起来筛选了，实际后端全量执行”的风险；如有，指出必须补的后端门禁。
4. 后端 `batch-execute` / `batch-reprocess` 的 `accountNum` 和 `statusScope` 设计是否足够 fail-closed。
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

## Acceptance Criteria For Final Implementation

- `待确认` and `等待重查` both have an `全部` plus store selector.
- Filtering does not change status classification.
- Filtering does not change deadline/urgency order.
- Scoped batch actions cannot operate on hidden stores.
- Backend validates `accountNum` and `statusScope`.
- Old unsafe scan/multi-account paths are not reused as the new A1 entry.
- No local archive folder is created; cleanup decisions are represented by git commits and docs.
