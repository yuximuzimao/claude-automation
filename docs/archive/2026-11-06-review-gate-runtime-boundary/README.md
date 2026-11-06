# Review Gate 触发边界调整

日期：2026-11-06

本档案记录 Review Gate V2 完成后的触发时点修正。它保存本次决策、实现范围和验证结果；**不是第二份操作手册**。现役唯一操作规则见 [`docs/review-gate/README.md`](../../review-gate/README.md)。

## 调整原因

V2 原有说明把普通开发任务的收尾也纳入 Delivery 判断。对于仍在开发、试做和调试的自动化项目，这会导致每次增量修改都可能提前启动完整 Review，打断正常的开发与自测节奏。

用户确认 Review Gate 的目标是保护真实无人监管运行，而不是给每一轮开发修改增加交付门槛。因此，触发条件改为项目的实际运行阶段，以及本轮变更是否影响下一次真实执行。

## 最终触发规则

1. **开发、试做、调试阶段：不触发 Review。** 项目尚未准备真实无人监管运行时，不创建 Review Work / Delivery；即使代码已经包含桌面操作、浏览器操作、队列、重试、账号切换或停止机制，也按正常开发流程自测。
2. **首次无人监管运行前：完整 Review。** 必须登记并审查完整的实际运行代码、配置、规则和必要依赖；即使没有代码差异，也不能跳过。
3. **已经实际运行的项目：审查影响下一次真实执行的变更。** 只有本轮修改可能改变下一次无人监管执行行为时，才进入 Review。确认不影响执行的展示、文案、文档示例等修改不强制启动完整 Reviewer。
4. **NEAT 与 Review 分离。** 纯整理、历史归档、坐标核对和历史 dirty 文件本身不触发 Review。

## 实现调整

- `review_required()` 将 `development`、旧标签 `auto`、`neat`、`inspection`、`display` 归为非 Review 阶段；只有 `unattended_change` 和 `unattended_first_run` 进入运行检查点。
- `capture_work()` 拒绝在开发阶段创建 Work，并给出首次运行与已运行项目修改的正确入口。
- `_risk_floor()` 中的桌面/浏览器操作、队列、重试、账号和业务动作代码模式，只在 `unattended_change` 阶段作为强制 Review 底线；开发阶段不会仅因命中代码模式升级为 Review。
- 独立分类器提示词和工作区 `policy.json` 均按实际运行阶段判断；不能从自动化代码模式推断项目已经投入运行。
- CLI `route` 明确区分开发阶段、已运行项目变更和首次运行：开发阶段返回 `review_not_required`；已运行项目变更进入实际差异分类；首次运行返回 `review_required`。
- 新增回归覆盖：开发阶段即使出现 `pyautogui.click()` 也不触发代码风险底线；同一模式在已运行项目变更阶段仍会触发。路由测试覆盖四种运行阶段。

## 验证结果

以下均在本地隔离测试夹具中执行，没有启动真实业务自动化或执行无人监管运行。

| 检查 | 结果 |
| --- | --- |
| `test_review_gate.py` | 25/25 通过 |
| `test_delivery.py` | 40/40 通过 |
| `python3 -m json.tool docs/review-gate/policy.json` | 通过 |
| `python3 -m py_compile docs/review-gate/review_gate.py` | 通过 |
| `git diff --check` | 通过 |

本次记录的是回归测试结果，不将其表述为真实无人监管运行验收，也不替代后续首次运行前的完整 Review。

## 现役入口与维护边界

- 唯一操作说明：[`docs/review-gate/README.md`](../../review-gate/README.md)。
- 全局简要约束：根目录 `CLAUDE.md` 与 `AGENTS.md`，只保留触发边界和入口指针。
- V2 阶段交接档案：[`2026-11-06-review-gate-v2-handoff`](../2026-11-06-review-gate-v2-handoff/README.md) 已补充后续口径调整说明，避免旧规则被误认为现行规则。
- Review Gate 继续作为工作区共享能力，独立于 Codex Monitor / Status Island；仍由 Agent 在真实运行检查点显式调用，不安装自动 Hook。
- 本次未修改农场、魔兽、售后等项目业务代码或运行数据，未修改用户级配置。
