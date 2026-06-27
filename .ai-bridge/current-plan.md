# Aftersales Task 6 journal recovery design handoff

Updated: 2026-06-27T09:04:00.262Z
Workspace: /Users/chat/claude
Target agent: Codex (codex)

## Plan

Task 6 is complete as design-only. Do not re-design from scratch unless asked.

Read first:
1. aftersales-automation/docs/superpowers/plans/2026-06-27-auto-execution-journal-recovery-design.md
2. aftersales-automation/docs/superpowers/plans/2026-06-27-a1-codexpro-parallel-tasks.md
3. aftersales-automation/tasks/todo.md
4. docs/HANDOFF.md

Key design conclusion:
- auto-execution-journal is an audit/recovery ledger, not a retry helper.
- Never blindly retry approve/reject after an unfinished automatic execution intent.
- Any page-action uncertainty must require human platform verification.
- Human recovery must close journal + queue + simulation/audit + execution gates together.
- Marking only journal as manually_resolved is forbidden because it can hide hazardous queue/simulation state.
- manually_resolved means audit closure, not automatic re-release.

Designed states:
- auto_executing with phases reserved / page_action_started / page_action_succeeded / writeback_failed.
- auto_executed blocks future automatic execution directly from journal, even if simulations are incomplete.
- failed is only allowed when page action definitely did not start.
- manually_resolved requires resolution confirmed_executed / confirmed_not_executed / unknown, operator note, allowAutoRetry:false, and batch/manual gate behavior.

No code was changed for Task 6. No CLI/API/UI recovery command was implemented. No tests were run for this design-only step. No true approve/reject automatic execution was enabled.

Next implementation, only if user explicitly asks, should be phased:
1. pure journal state machine + unit tests,
2. Step 14 in-progress state writeback,
3. local-only CLI recovery list/show/resolve,
4. execution gate hardening for manual and scoped batch execute,
5. UI visibility,
6. separate future authorization before true automatic execution.

Still forbidden unless separately authorized:
- real fixed-batch run,
- server restart,
- approve/reject,
- scan-all / collect / read-ticket / logistics / ERP commands,
- any browser/JL/ERP operation.

Current remaining CodexPro-sized work in the task plan is Task 7: frontend button load/smoke plan only. The single-account no-auto button code already exists; do not add a duplicate button, restart the server, click the real button, or run fixed-batch unless the user explicitly authorizes it.

## Implementation contract

- Work from this plan in small, reviewable steps.
- Keep edits scoped to the requested task and existing project conventions.
- Run focused verification before handing work back.
- Update .ai-bridge/agent-status.md with files touched, checks run, results, blockers, and review notes.
- Save the final review diff to .ai-bridge/implementation-diff.patch when practical.
- Append notable execution events to .ai-bridge/execution-log.jsonl when the implementation agent supports logging.
