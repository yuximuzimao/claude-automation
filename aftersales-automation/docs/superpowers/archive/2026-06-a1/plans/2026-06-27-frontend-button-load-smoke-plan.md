# Frontend Button Load/Smoke Plan — 2026-06-27

> 2026-07 状态覆盖：本文件是前端按钮加载/只读冒烟阶段的历史计划。当前前端按钮已成为正式“处理工单”入口，点击后二次确认并调用 `POST /api/accounts/:num/a1-fixed-batch`；当前状态请看 README.md / SKILL.md。

> Status: Plan complete. Do not implement a second button. Do not restart server from this plan. Do not click the real button during planning.

## Scope

This plan covers how to safely load and smoke-test the already implemented single-account no-auto `A1固定清单` button after the user separately authorizes a server restart.

This is not an implementation task. The button already exists in code. The goal is to verify safe loading and define a non-destructive smoke procedure.

## Current Implementation To Preserve

Existing frontend implementation:

- `public/account-relogin-state.js`
  - `shouldShowA1FixedBatchButton(account)` returns true only when `account.hasFile === true && account.status === 'ok'`.
  - `renderA1FixedBatchButton(num)` renders one button: `A1固定清单`.
- `public/app.js`
  - account cards call `AccountReloginState.shouldShowA1FixedBatchButton(a)`.
  - clicking the rendered button calls `runA1FixedBatch(num, this)`.
  - `runA1FixedBatch()` shows a confirmation dialog before posting.
  - if confirmed, it calls only `POST /api/accounts/${num}/a1-fixed-batch`.
  - frontend does not pass `thresholdHours`, `disableAutoExecute`, or an accounts array.

Existing backend implementation to rely on:

- `lib/server/a1-fixed-batch-entry.js`
  - route accepts only explicit single account number.
  - account guard reads account status and rejects non-ok states.
  - session file is validated by account number, realpath, JSON, auth cookies, and identity localStorage.
  - enqueued op is `a1-fixed-batch` with `thresholdHours:48` and `disableAutoExecute:true`.
- `lib/server/routes.js`
  - route is `POST /api/accounts/:num/a1-fixed-batch`.
- `lib/server/op-queue.js`
  - op type `a1-fixed-batch` is serialized through the existing op queue.

Existing tests already cover:

- button only shows for ok saved accounts,
- expired/error/unknown/no-file accounts do not show the button,
- frontend calls only the selected account endpoint,
- frontend does not pass mutable scope or auto-execute parameters,
- backend entry builds an `a1-fixed-batch` op with no-auto defaults.

## Non-Goals

Do not do any of these in this task:

- do not create another button,
- do not rename or rewrite the current button,
- do not change frontend or backend code,
- do not restart the server,
- do not click the real `A1固定清单` button,
- do not call `POST /api/accounts/:num/a1-fixed-batch`,
- do not run fixed-batch,
- do not open JL/ERP tabs,
- do not approve/reject,
- do not scan or collect.

## Pre-Restart Static Verification

Before the user authorizes a restart, a safe reviewer may only do static checks and local unit tests.

Recommended static checks:

1. Confirm exactly one frontend render function for the A1 button exists:
   - `public/account-relogin-state.js: renderA1FixedBatchButton`.
2. Confirm visibility remains restricted:
   - `hasFile === true` and `status === 'ok'` only.
3. Confirm account card uses the helper and does not duplicate button HTML elsewhere.
4. Confirm click handler is still `runA1FixedBatch(num, this)`.
5. Confirm `runA1FixedBatch()` still shows `confirm()` before any POST.
6. Confirm POST target is only `/api/accounts/${num}/a1-fixed-batch`.
7. Confirm frontend still sends no body containing `thresholdHours`, `disableAutoExecute`, or multiple accounts.
8. Confirm no references were added from this button to `/api/scan`, `/queue/batch-reprocess`, or `/simulations/batch-execute`.
9. Confirm backend still forces `thresholdHours:48` and `disableAutoExecute:true`.
10. Confirm tests still include the frontend and backend guard cases.

Allowed local checks if implementation is later touched:

```bash
npm test
node --test test/server/a1-fixed-batch-frontend.test.js
node --test test/server/relogin-session.test.js
node --test test/server/a1-fixed-batch-entry.test.js
```

For this planning-only task, no command is required.

## Restart Preconditions

Server restart is a separate operator action and must not be done by this plan.

Before restart, confirm:

- user explicitly authorized restart,
- no real fixed-batch run is being authorized implicitly,
- current uncommitted changes are known,
- no one expects the old frontend bundle to remain loaded,
- operator knows this restart only loads UI/backend changes.

The correct restart outcome is only: new code is loaded and visible. It must not enqueue an A1 op by itself.

## Post-Restart Read-Only UI Smoke Plan

These steps are for after a separately authorized restart. They are designed to avoid clicking the real button.

### 1. Page load check

Open the aftersales web UI and confirm the app loads normally.

Expected:

- no blank page,
- no obvious JavaScript error toast,
- existing tabs still render,
- account management page can be opened.

### 2. Account list visibility check

Open the account management page.

Expected:

- accounts render as before,
- existing `打开店铺后台` and relogin actions are still present according to prior logic,
- no duplicate `A1固定清单` buttons appear in one account card.

### 3. Button visibility check without clicking

Inspect visible accounts by status.

Expected:

- accounts with `status=ok` and a saved session file show exactly one `A1固定清单` button,
- `expired`, `error`, `unknown`, and no-file accounts do not show the button,
- the button is not shown as a global or all-account batch action.

### 4. Copy/text check

Read the button and any nearby context.

Expected:

- button text remains `A1固定清单`,
- confirm copy, if inspected from source or browser devtools without clicking, explains: single account, 48-hour fixed list, queueing, no automatic approve/reject, may write pending review.

Current confirm copy is safe but minimal:

```text
确认将账号${num}的48小时固定清单加入队列吗？

本入口只采集、推理并写回待确认，不会自动同意或拒绝退款。
```

Patch suggestion only if user wants clearer wording later:

```text
确认将账号${num}的48小时固定清单加入队列吗？

范围：仅此单账号、48小时内首次冻结清单、串行处理。
结果：只采集、推理并写回原售后系统的待确认/等待重查/已自动执行语义。
安全：默认关闭真实自动同意/拒绝退款；这不是全店铺扫描，也不是批量执行。
```

Do not patch wording during this planning task.

### 5. Network negative check without clicking

Do not click the button.

Use browser network panel only to observe passive page-load requests.

Expected:

- loading account page may call `GET /api/accounts`,
- no `POST /api/accounts/:num/a1-fixed-batch` occurs during page load,
- no `/api/scan`, `/queue/batch-reprocess`, or `/simulations/batch-execute` occurs because of button rendering.

### 6. Optional non-production/stubbed confirm check

Only in a local dev/stub context, not against the real server/session, a developer may stub `window.confirm` to return false and call `runA1FixedBatch(num, fakeButton)` from console to verify that no POST happens when cancelled.

This must not be done against the real running production-like UI unless the user explicitly authorizes dev console testing.

Expected:

- confirm false exits before POST,
- button text is not left as `入队中...`,
- no op appears in `/op-queue`.

## Do Not Click Real Button During Smoke

The real button enqueues a real `a1-fixed-batch` op after confirmation. Even though backend forces no-auto, the op can still open accounts, touch JL, collect, infer, and write queue/simulation.

Therefore smoke test must stop before any positive confirmation or real POST.

If a real click happens accidentally and the confirm dialog appears:

- click cancel,
- verify no network POST was sent,
- verify `/op-queue` did not receive an `a1-fixed-batch` op.

If a POST was accidentally sent:

- stop immediately,
- do not click anything else,
- inspect op queue state,
- do not try to repair by running additional browser/JL commands without explicit user instruction.

## Acceptance Criteria

The load/smoke plan is satisfied when all are true:

- current implementation is recognized as already existing; no duplicate button is proposed,
- button visibility is restricted to ok + saved-session accounts,
- expired/error/unknown/no-file accounts cannot enqueue fixed-batch from UI,
- page load does not enqueue fixed-batch,
- button rendering does not call old scan/batch endpoints,
- any later restart is treated as separate user-authorized action,
- smoke steps avoid clicking the real button,
- risk if accidentally clicked is documented,
- no real automatic approve/reject is enabled or implied.

## Patch Suggestions If Future Review Finds Drift

Only if future static review finds drift, patch narrowly:

1. If duplicate button exists, remove the duplicate and keep `AccountReloginState.renderA1FixedBatchButton` as the single render point.
2. If visibility expands beyond ok + hasFile, restore `shouldShowA1FixedBatchButton()` to `hasFile === true && status === 'ok'`.
3. If frontend passes mutable body params, remove body entirely.
4. If endpoint changes away from `/api/accounts/:num/a1-fixed-batch`, stop and review before patching.
5. If confirm copy is ambiguous, update copy only; do not touch route or queue logic.

## Next Step

After this plan, the next real operator action would be a user-authorized server restart followed by read-only UI smoke. That action is outside this planning task.
