# 龙骨荒野 breadcrumb audit 退役说明（2026-09-10）

## 结论

`scripts/audit_dragonblight_breadcrumbs.py` 不执行验证判断。它从 `dragonblight-task-foundation.json` 中筛出带 `breadcrumb_for`、`breadcrumbs` 或 `exclusive_to` 的正式任务，再把关系打印成一份人工清单；输出本身直接位于 `docs/archive/analysis/2026-08-16-dragonblight-breadcrumb-audit.md`。

该脚本没有 PASS/FAIL、没有现役 builder/audit/test 消费其输出，也不向正式路线提供输入。breadcrumb/exclusiveTo 事实已经存在于 Dragonblight foundation 中；正式任务覆盖与路线行为由现役 coverage/tests 保护。

因此它属于建设期人工关系清单，而非长期审计。历史清单继续保留在 archive 作为证据即可。

## 处理

- `scripts/audit_dragonblight_breadcrumbs.py` 退役为 RETIRED guard。
- 保留原 `docs/archive/analysis/2026-08-16-dragonblight-breadcrumb-audit.md` 历史输出，不把它当当前事实源。
- 当前 breadcrumb/exclusiveTo 事实继续由 Dragonblight foundation 维护。

本次不改变龙骨任务关系或路线。