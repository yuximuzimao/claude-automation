# 祖达克 handoff audit 退役说明（2026-09-10）

## 结论

`scripts/audit_zuldrak_handoffs.py` 不执行任何 PASS/FAIL 判断。它只是把 `zuldrak-task-foundation.json` 中 105 个正式任务的接取 NPC、交付 NPC、前置关系和 next quest 再复制成 `zuldrak-handoff-audit.json`，并额外生成 `.ai-bridge/zuldrak-handoff-summary.md`。

仓库定向引用检查确认：除该脚本自身外，没有现役 builder、audit 或 test 读取 `zuldrak-handoff-audit.json` 或 `zuldrak-handoff-summary.md`。

因此它属于建设期人工接交摘要，不是真正审计。继续保留会形成第二份 foundation 快照并可能随正式数据漂移。

## 处理

- `scripts/audit_zuldrak_handoffs.py` 退役为 RETIRED guard。
- `data/route-atlas/zuldrak-handoff-audit.json` 改为 RETIRED 指引，不再保留为当前事实源。
- `.ai-bridge/zuldrak-handoff-summary.md` 改为退役指引。
- 祖达克正式接取/交付/前置事实继续唯一来自 `data/route-atlas/zuldrak-task-foundation.json` 及其现役 builder。

本次不改变祖达克任务池或路线。