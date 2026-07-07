# Auto-Execution Journal Recovery Design — 2026-06-27

> 2026-07 说明：本文件只定义 recovery / journal 设计边界，不代表当前自动执行状态或当前人工操作方式。当前自动执行已由 Step14 + shouldAutoExecute + executionJournal 生产链路启用；recovery 外部 CLI/API/UI 入口仍未开放。实际处理中断工单通常不是通过本地 recovery 服务确认平台状态，而是重新采集推理覆盖旧状态，或由用户手动处理后归档；归档只表示系统不再处理该工单，不代表系统知道平台真实执行结果。

> Status: Design complete; Phase 1 code foundation completed on 2026-06-27. `lib/server/auto-execution-journal.js` now has state/phase/manual-resolution helpers, `lib/server/auto-execution-recovery.js` provides local-only recovery state repair, Codex review follow-up risks were patched, and `npm test` passes 242/242. Do not enable true automatic approve/reject from this document.

## Scope

This design covers the recovery semantics for `lib/server/auto-execution-journal.js` and the fixed-batch automatic execution path in `scripts/jl-steps/14-process-single-account-fixed-batch.js`.

Current production-safe posture remains unchanged:

- No real automatic approve/reject is enabled by this design.
- No JL/ERP/browser operation is required to apply this design document.
- Fixed-batch official entry remains no-auto until separately authorized by the user.
- Recovery actions must be audit-only and state-repair-only; they must not click approve/reject.

## Problem

The current journal can persist `auto_executing` before calling the real page action, then mark `auto_executed` after success. If the process crashes, the page times out, or local writeback fails between those two points, the journal may keep an unfinished `auto_executing` intent.

That unfinished intent is useful because it prevents duplicate automatic execution. However, it has no complete human-operable recovery path.

The dangerous cases are:

1. `reserve()` succeeded, then `approveTicket()` failed or became uncertain.
2. `approveTicket()` actually succeeded, but `markExecuted()` failed.
3. `markExecuted()` succeeded, but queue/simulation writeback failed.
4. The process crashed after writing a partial journal state.
5. A later manual or batch entry may accidentally pick the same work order if queue/simulation is not finalized.

## Non-Negotiable Safety Rule

Never blindly retry approve/reject after an unfinished automatic execution intent.

If the script has already started, or may have started, the real page action, the result must be treated as uncertain until a human checks the platform state.

Human recovery must close the whole local state, not just the journal. A recovery action must update:

- auto-execution journal,
- queue item,
- latest simulation or audit simulation record,
- batch/manual execution gates.

A recovered work order must not remain as a hidden `auto_executing` or unresolved abnormal state that future scripts can accidentally pick up.

## Desired Journal State Machine

### `auto_executing`

Meaning: an automatic execution attempt exists and is not fully closed.

This status must block automatic execution, manual batch execution, and any silent re-entry.

Recommended phases:

- `reserved`: intent written; page action has not started yet.
- `page_action_started`: script has entered the real page-action section.
- `page_action_succeeded`: page action returned success, but local writeback may still be incomplete.
- `writeback_failed`: page action likely succeeded, but journal/queue/simulation writeback failed.

Older records with only `status: "auto_executing"` and no phase must be treated as unresolved and page-action-uncertain.

### `auto_executed`

Meaning: the real automatic action is confirmed executed.

This status must permanently block all future automatic approve/reject attempts for the same work order.

The safety gate must check journal `auto_executed` directly, not only rely on `simulations.executedAt`. This prevents duplicate action if journal writeback succeeded but simulation writeback failed.

### `failed`

Meaning: the automatic attempt failed before the page action started.

This status is only allowed when the system can prove no real approve/reject page action was entered.

Examples:

- local dependency missing before execution,
- unsupported decision action before execution,
- reserve race before page action,
- pre-action validation failure.

Even `failed` must not imply automatic retry. It only means the work order can return to a human-visible state with an audit reason.

### `manually_resolved`

Meaning: a human has checked and closed the interrupted attempt.

This status is an audit closure, not an automatic release.

Required fields:

```json
{
  "status": "manually_resolved",
  "resolution": "confirmed_executed",
  "resolvedAt": "2026-06-27T00:00:00.000Z",
  "resolvedBy": "manual",
  "operatorNote": "已在鲸灵后台确认退款成功",
  "allowAutoRetry": false,
  "allowBatchExecute": false
}
```

`allowAutoRetry` must default to false and should normally remain false permanently.

## Manual Resolution Types

### `confirmed_executed`

Human checked the platform and confirmed the action already succeeded.

Required local updates:

- journal: `manually_resolved`, `resolution: confirmed_executed`, `allowAutoRetry:false`, `allowBatchExecute:false`.
- queue item: finalized to the executed terminal meaning used by the current system, normally `auto_executed`.
- simulation: add or update an audit record with `executedAt`, `autoExecutedAt`, `manualResolvedAt`, `manualResolution`, and `operatorNote`.
- execution gates: permanently block future approve/reject for this work order.

The recovery action must not click approve/reject.

### `confirmed_not_executed`

Human checked the platform and confirmed the action did not happen.

Required local updates:

- journal: `manually_resolved`, `resolution: confirmed_not_executed`, `allowAutoRetry:false`.
- queue item: return to a human-visible simulated/pending-review state, not `auto_executing`.
- simulation: record that automatic execution was interrupted and later confirmed not executed.
- batch gate: do not allow this work order to be silently included in batch execute by default.

The item may be manually reviewed later, but it must not re-enter automatic execution without a separate explicit future design and authorization.

### `unknown`

Human cannot confirm whether the page action happened.

Required local updates:

- journal: `manually_resolved`, `resolution: unknown`, `allowAutoRetry:false`, `allowBatchExecute:false`.
- queue item: human-visible review state with strong blocking metadata.
- simulation: audit note that execution result is unknown.
- UI/manual/batch gates: block automatic and batch execution.

This is the safest state when platform evidence is ambiguous.

## Queue And Simulation Closure Rule

Manual recovery must be transactional at the application level.

A recovery command is only successful if it closes all relevant local state together:

```text
journal resolved
+ queue state finalized
+ simulation/audit record finalized
+ execution gates can recognize the closure
```

If any part fails, the command must fail visibly and leave enough information for the operator to retry the state repair. It must never silently mark the journal resolved while leaving queue/simulation in a hazardous state.

The strongest implementation is to perform all JSON writes under the same local lock or a deterministic write sequence with rollback-safe failure behavior. Since the current data store is JSON/jsonl, the implementation should prefer fail-closed behavior over partial success claims.

## Step 14 Integration Design

Recommended future sequence:

1. Pre-gate: circuit breaker, unresolved journal, `auto_executed` journal, previous executed simulation.
2. Reserve: write `auto_executing` + `phase: reserved` + `attemptId`.
3. Queue writeback: mark queue item as `auto_executing` or equivalent in-progress state so UI does not show it as normal executable pending work.
4. Before calling `executeDecision()`: update journal to `phase: page_action_started`.
5. If page action returns success: update journal to `phase: page_action_succeeded`, then `auto_executed`.
6. Persist simulation/queue terminal state.
7. If failure happens after `page_action_started`, mark the work order as recovery-required, not ordinary simulated.

Failures after `page_action_started` must not be converted into normal pending work without a manual resolution record.

## Recovery Entry Points

Implement CLI before UI/API.

Recommended CLI:

```bash
node cli.js auto-journal list --status unresolved
node cli.js auto-journal show <workOrderNum>
node cli.js auto-journal resolve <workOrderNum> --resolution confirmed-executed --note "已在鲸灵后台核验已同意退款"
node cli.js auto-journal resolve <workOrderNum> --resolution confirmed-not-executed --note "后台核验未提交，转人工待确认"
node cli.js auto-journal resolve <workOrderNum> --resolution unknown --note "状态不明，保持人工处理"
```

The CLI must only update local audit/state files. It must not open JL/ERP, approve, reject, collect, scan, or touch browser tabs.

Later API/UI can wrap the same service functions:

- `GET /api/auto-execution-journal/unresolved`
- `GET /api/auto-execution-journal/:workOrderNum`
- `POST /api/auto-execution-journal/:workOrderNum/resolve`

The API must require explicit confirmation and operator note. It must reject empty notes for resolution actions.

## Batch And Manual Execute Gate

All execute paths must check journal state before enqueueing or executing.

This includes:

- single manual execute,
- scoped batch execute,
- any future fixed-batch automatic execute,
- any legacy route that still exposes execution semantics.

If a work order has unresolved or high-risk recovered journal state, it must be skipped or rejected with a visible reason.

For batch execute, the response should expose skipped journal blocks:

```json
{
  "count": 5,
  "journalBlockedCount": 2,
  "journalBlocked": [
    {
      "workOrderNum": "100001xxx",
      "reason": "存在未完成自动执行 intent，需人工复核"
    }
  ]
}
```

## Test Matrix

### Journal unit tests

- `reserve()` writes `auto_executing`, `phase: reserved`, `attemptId`, and history.
- second `reserve()` is rejected for `auto_executing`, `auto_executed`, and unresolved `manually_resolved` states that disallow retry.
- `markPageActionStarted()` moves `reserved` to `page_action_started`.
- failures before `page_action_started` may become `failed`.
- failures after `page_action_started` become recovery-required, not ordinary failed.
- `markExecuted()` writes `auto_executed` and blocks future reserve.
- old `auto_executing` records without phase are recognized as unresolved and page-action-uncertain.
- old `auto_executed` records block automatic execution even when simulation history is missing.
- corrupted JSON/EIO continues to fail closed and never overwrites the file.
- lock contention fails closed.

### Step 14 tests

- reserve succeeds, then pre-page-action failure returns simulated with `autoExecuteError` and journal failed.
- after `page_action_started`, `executeDecision()` timeout returns recovery-required, not normal simulated.
- `executeDecision()` success but `markExecuted()` failure creates recovery-required writeback-failed state and does not retry page action.
- `markExecuted()` success but `persistOutcome()` failure leaves enough journal evidence to block duplicate action.
- unresolved journal blocks automatic execution before reading historical simulations.
- journal `auto_executed` blocks automatic execution even if simulation has no `executedAt`.

### Recovery service tests

- `confirmed_executed` updates journal + queue + simulation/audit together.
- `confirmed_not_executed` updates journal + queue + simulation/audit together, but does not allow auto retry.
- `unknown` updates journal + queue + simulation/audit together and blocks batch/manual execution.
- if queue write fails, the recovery command must not claim successful journal-only resolution.
- if simulation append fails, the recovery command must not claim successful journal-only resolution.

### Batch/manual gate tests

- scoped batch execute excludes unresolved journal work orders.
- scoped batch execute excludes `confirmed_executed` records.
- scoped batch execute excludes `unknown` records.
- `confirmed_not_executed` records are not included in batch execute by default.
- response exposes blocked work orders and reasons.

## Recommended Phased Implementation

### Phase 1 — Pure journal logic and tests

Implement state machine helpers, phase transitions, and manual resolution validation. No UI, no API, no true automatic execution.

### Phase 2 — Step 14 in-progress state writeback

Make Step 14 write clear phases and queue/simulation recovery-required metadata. Still keep official entry no-auto.

### Phase 3 — CLI recovery command

Add local-only `auto-journal list/show/resolve` commands. Commands must only repair local state and must require operator notes.

### Phase 4 — Execution gate hardening

Connect journal checks to manual execute, scoped batch execute, and future fixed-batch automatic execution gates.

### Phase 5 — UI visibility

Expose recovery-required items in the live UI with disabled execution buttons and explicit operator instructions.

### Phase 6 — Separate future authorization for true automatic execution

Only after recovery is implemented, tested, and reviewed should true automatic execution be discussed again. This design does not authorize it.

## Acceptance Criteria For Future Implementation

- Page-action uncertainty is distinguished from local writeback failure.
- No proposal or code path blindly retries approve/reject.
- Human recovery is auditable.
- Human recovery closes journal, queue, simulation/audit, and execution gates together.
- A resolved journal record cannot hide a hazardous queue/simulation state.
- Batch/manual execution cannot bypass unresolved or high-risk recovered journal states.
- Legacy `auto_executing` records are treated fail-closed.
- True automatic execution remains disabled unless the user separately authorizes it.
