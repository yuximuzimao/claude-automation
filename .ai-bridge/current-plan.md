# Aftersales A1 live tab store filter handoff

Updated: 2026-06-27T08:35:35.317Z
Workspace: /Users/chat/claude
Target agent: Codex (codex)

## Plan

# Aftersales A1 — Live tab store filter and scoped batch handoff

## Current state

The live tab store filter and scoped batch-action task is complete. Do not re-implement it.

Completed scope:

- `待确认` has `全部` + store selector.
- `等待重查` has `全部` + store selector.
- Filtering is per-tab view only; it does not create a new status or change original three-tab classification.
- Filtering keeps the existing deadline/urgency order.
- `待确认` batch execute posts explicit `{ statusScope:'pending', accountNum? }`.
- `待确认` batch reprocess posts explicit `{ statusScope:'pending', accountNum? }`.
- `等待重查` batch reprocess posts explicit `{ statusScope:'waiting', accountNum? }`.
- `等待重查` has no batch execute button.
- Backend validates `accountNum` and `statusScope` through `lib/server/live-batch-scope.js`.
- Scoped batch operations cannot silently operate on hidden stores.

## Important files changed

- `aftersales-automation/public/index.html`
- `aftersales-automation/public/app.js`
- `aftersales-automation/public/style.css`
- `aftersales-automation/lib/server/routes.js`
- `aftersales-automation/lib/server/live-batch-scope.js`
- `aftersales-automation/test/server/live-batch-scope.test.js`
- `aftersales-automation/test/server/live-toolbar-frontend.test.js`
- `aftersales-automation/SKILL.md`
- `aftersales-automation/README.md`
- `aftersales-automation/tasks/todo.md`
- `aftersales-automation/docs/superpowers/plans/2026-06-19-a1-fixed-batch-user-confirmation.md`
- `aftersales-automation/docs/superpowers/plans/2026-06-27-a1-codexpro-parallel-tasks.md`
- `aftersales-automation/docs/superpowers/plans/2026-06-27-live-tab-store-filter-and-legacy-cleanup.md`
- `aftersales-automation/docs/superpowers/handovers/2026-06-27-live-tab-store-filter-neat-handoff.md`
- `docs/HANDOFF.md`

## Archive / neat status

Do not create another local archive directory. The plan is archived in place:

- `aftersales-automation/docs/superpowers/plans/2026-06-27-live-tab-store-filter-and-legacy-cleanup.md`

Neat handoff:

- `aftersales-automation/docs/superpowers/handovers/2026-06-27-live-tab-store-filter-neat-handoff.md`

Main progress plan updated:

- `aftersales-automation/docs/superpowers/plans/2026-06-27-a1-codexpro-parallel-tasks.md`

## Verification

`npm test` was run from `aftersales-automation` and passed 228/228 tests, 0 failed.

No real browser, JL, ERP, scan, collect, fixed-batch, account opening, approve/reject, or server restart was performed.

## Remaining risk boundary

Backend intentionally preserves empty-body legacy broad behavior for compatibility. New frontend sends explicit scope. Treat empty-body broad behavior as transitional legacy until caller audit allows requiring `statusScope` for all callers.

Old `/api/scan`, `scan-all.js`, `collect.js`, and old `pipeline.js` paths are still not safe A1 entry paths.

Server has not been restarted. Do not assume production UI/server has loaded the new code until the user explicitly authorizes restart.

## Suggested next Codex task

Use `aftersales-automation/docs/superpowers/plans/2026-06-27-a1-codexpro-parallel-tasks.md` Task 6: Auto-Execution Journal Recovery Design.

Task 6 should be design-only unless user explicitly requests implementation. Do not enable true automatic approve/reject. Do not run real fixed-batch. Do not restart server without explicit user authorization.

## Implementation contract

- Work from this plan in small, reviewable steps.
- Keep edits scoped to the requested task and existing project conventions.
- Run focused verification before handing work back.
- Update .ai-bridge/agent-status.md with files touched, checks run, results, blockers, and review notes.
- Save the final review diff to .ai-bridge/implementation-diff.patch when practical.
- Append notable execution events to .ai-bridge/execution-log.jsonl when the implementation agent supports logging.
