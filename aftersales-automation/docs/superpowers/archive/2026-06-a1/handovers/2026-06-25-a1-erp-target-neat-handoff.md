# A1 ERP Target Handoff — 2026-06-25

## Scope

Small A1 fixed batch correction for ERP target acquisition.

## Code changes

- `aftersales-automation/lib/jl/target-aware-collector.js`
  - Kept `resolveUniqueErpTargetId` as the exported compatibility name.
  - Multiple ERP page targets no longer cause a hard stop.
  - If ERP targets exist, the first ERP page target returned by Chrome is selected and locked.
  - Explicit `erpTargetId` input is still verified against existing ERP page targets.
  - If no ERP target exists, `https://viperp.superboss.cc` is created and activated when possible.
  - The resolver accepts both `id` and `targetId` shapes.

- `aftersales-automation/test/jl/target-aware-collector.test.js`
  - Updated the old multi-ERP test from reject to select-and-lock.
  - Added missing-ERP coverage for create, activate, and return created target id.

## Docs / handoff updates

- `.ai-bridge/agent-status.md` updated with this pass.
- `aftersales-automation/tasks/todo.md` updated to mark the ERP target policy as implemented and tested.
- `.ai-bridge/current-plan.md` already contains the clarified policy and minimal browser regression scope.

## Verification

`npm test` from `aftersales-automation` passed: 199/199, 0 failed.

## Not done

- No real browser action.
- No JL page action.
- No ERP page action.
- No server restart.
- No UI/routes/op-queue integration.

## Next step

Run only the user-authorized minimal A1 browser regression with one account and one work order: open account, prepare list, locate order, click the row action, confirm a new detail tab is locked, close it, and verify the list tab remains correct. Do not run full collection in that regression.
