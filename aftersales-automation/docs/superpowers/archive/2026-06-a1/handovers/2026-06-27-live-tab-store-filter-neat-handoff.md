# Live Tab Store Filter And Scoped Batch Handoff — 2026-06-27

## Scope

Completed the `待确认` / `等待重查` live tab store filter and scoped batch-action task. This is a UI + backend scope hardening pass only; it does not run real accounts, JL, ERP, fixed-batch, scan, collect, approve, reject, or restart the server.

## Human conclusion

The dangerous gap was confirmed and closed: a filtered UI must not be allowed to send a broad backend batch action. The page now filters per tab by store/account, and batch operations send explicit `statusScope` plus optional `accountNum`. The backend independently validates the scope and selects candidates from queue items, so hidden stores are not silently enqueued.

`等待重查` remains recheck-only: it has scoped `批量重来`, but no `批量执行` button.

## Code changes

- `public/index.html`
  - Added store selectors to `待确认` and `等待重查` toolbars.
  - `待确认` batch reprocess now calls `batchReprocess('pending')`.
  - `等待重查` exposes only scoped `批量重来`, not `批量执行`.

- `public/app.js`
  - Added per-tab store filter state.
  - Builds selector options from current tab items by `accountNum` / `accountNote`.
  - Filters only the current tab view; does not change live status classification.
  - Keeps existing deadline/urgency order because filtering happens after the sorted list is split by status.
  - Count display shows scoped counts such as `3/12`.
  - `batchExecute()` posts `{ statusScope:'pending', accountNum? }`.
  - `batchReprocess(tabKey)` posts `{ statusScope:'pending'|'waiting', accountNum? }`.
  - API JSON errors are surfaced through toast instead of being treated as success.

- `public/style.css`
  - Added compact `.store-filter` selector styling.

- `lib/server/live-batch-scope.js`
  - New helper module for batch scope parsing and candidate selection.
  - Validates `accountNum` as positive integer.
  - Validates `statusScope`.
  - Preserves empty-body legacy broad behavior for backward compatibility, but new frontend never sends empty scope.
  - Single-store scope excludes missing-account items from scoped actions.
  - Explicit scoped batch execute chooses latest simulation per queue item, then sorts by page-like deadline/urgency order.

- `lib/server/routes.js`
  - `/api/simulations/batch-execute` now parses scope and uses `selectExecutableSimulations`.
  - `/api/queue/batch-reprocess` now parses scope and uses `selectReprocessQueueItems`.
  - Responses include `scopeAccountNum` and `statusScope`.
  - Invalid scope returns HTTP 400.

- `test/server/live-batch-scope.test.js`
  - Covers account-scoped batch execute, waiting exclusion, latest simulation selection, scoped reprocess, invalid scope fail-closed, and legacy empty body compatibility.

- `test/server/live-toolbar-frontend.test.js`
  - Updated source tests for pending/waiting selectors and explicit scoped request bodies.

- `SKILL.md`
  - Added `lib/server/live-batch-scope.js` to entry map and paths.

## Plan/archive status

No new archive directory was created.

- Original plan was archived in place with a completion record:
  - `docs/superpowers/archive/2026-06-a1/plans/2026-06-27-live-tab-store-filter-and-legacy-cleanup.md`
- Main progress plan was updated:
  - `docs/superpowers/archive/2026-06-a1/plans/2026-06-27-a1-codexpro-parallel-tasks.md`
- A1 confirmation/todo state was updated:
  - `docs/superpowers/archive/2026-06-a1/plans/2026-06-19-a1-fixed-batch-user-confirmation.md`
  - `tasks/todo.md`
- Workspace handoff was updated:
  - `docs/HANDOFF.md`
  - `.ai-bridge/current-plan.md`

## Verification

Command run from `aftersales-automation`:

```bash
npm test
```

Result: 228/228 tests passed, 0 failed.

CodexPro safe bash rejected standalone `node --check`, so syntax confidence comes from the full `node:test` run.

## Not done

- No real browser operation.
- No JL / ERP page operation.
- No `scan-all.js`.
- No `collect.js`.
- No fixed-batch run.
- No account opening.
- No approve/reject.
- No server restart.
- No local archive directory.

## Current risk boundaries

- The backend still preserves empty-body legacy broad behavior for compatibility. New frontend sends explicit scope, but any old caller that POSTs `{}` still gets broad behavior. Treat this as transitional legacy until a caller audit allows requiring `statusScope` for all callers.
- This task does not make old `/api/scan`, `scan-all.js`, `collect.js`, or `pipeline.js` safe as A1 entry paths. They remain classified separately; do not reuse them as the new fixed-batch entry.
- Server has not been restarted, so running production UI may not have loaded the new route/frontend code until explicit restart.

## Next step for Codex

The next Codex-sized task should be design-only auto-execution journal recovery, unless the user explicitly chooses a different path.

Suggested target:

- `docs/superpowers/archive/2026-06-a1/plans/2026-06-27-a1-codexpro-parallel-tasks.md` → Task 6.

Do not implement or enable true automatic approve/reject from this handoff. Do not run real fixed-batch or restart server without separate explicit user authorization.
