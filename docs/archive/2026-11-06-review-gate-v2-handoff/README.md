# Review Gate V2 阶段交接与最终收尾

日期：2026-11-06。此文记录 V2 从初始未完成交接到最终验收的过程与证据，不是现役规则或第二份待办；初始阶段的临时未完成项曾登记于 [`codex-monitor/tasks/todo.md`](../../../codex-monitor/tasks/todo.md)，最终收尾时已移除。当前流程入口是 [`docs/review-gate/README.md`](../../review-gate/README.md)。

## 现场与范围

- 用户要求在既有 V1 基础上引入显式 Delivery、结合真实差异的三态风险判断、项目附加策略和可验证的 Codex App Hook；不修改农场、售后等业务代码/运行数据，不改用户级配置，不提交或推送。
- 已在现役目录实现待验收的 `deliver`、风险分类、工作区 `policy.json`、项目正向附加规则、Work 范围外 Git 指纹检查和本地签名记录，并保留 NEAT 与 Review 分离。**这些改动尚未通过最终独立审查，不可视为可用的交付门禁。**
- 本任务开始时 HEAD 为 `bec22eca129c009d890da31fc79860b55b2f548f`；并行任务随后将 HEAD 推进至 `6e651c284ee98276aca7f0e23e0081d4638744d9`，且存在范围外修改。真实工作区的原 Work 已失效，应保持阻断，不能用当前 HEAD 冒充任务起始基线。
- `docs/HANDOFF.md` 的农场段落也被并行任务修改。本轮第一次隔离候选误把该段并行内容包含在发送给只读 Reviewer 的材料中，发现后中止；随后重建隔离候选，仅在该文件中应用本轮自己的“当前焦点”行变更。没有回退或覆盖并行段落。隔离结果不等于真实工作区已通过 Delivery。
- 本次交接又更新了 Review Gate 入口提示、Todo、Handoff 和归档索引；它们发生在上述隔离 Review 之后，因此旧 Candidate 不能作为最终版本的通过记录。交接没有修改 Review Gate 代码或测试。
- 本轮 Git 起始状态和完整 diff 曾记录在 `/tmp/review-gate-v2-baseline.dtWCvy/`；原始用户需求及任务开始时文件状态保存在 `_sandbox/review-gate/v2-20261105.R6XSSP/requirements.txt`、`work.json` 和 `work-v3.json`。这些是本地证据，可能被系统清理；其中旧格式 Work 并非可直接用于 V2 放行的签名记录，不能补造起始基线。

## 已确认的审查结果

对排除并行 Handoff 新段落的隔离候选，独立 Reviewer 返回两项 Important；随后均在临时仓库复现，尚未修复：

1. **风险范围未确认却可能交付。** `classify_candidate()` 将有效的 `review_required` 判为 `assessment_complete=true`，即使分类理由表明可达执行风险的影响范围不明；Reviewer 返回空 finding 后，可继续验证并出现 `delivered`。需要将风险等级与范围完整性分别表达，范围未确认时允许先审查但不得交付。
2. **免审证据可引用非变更内容。** 当前只检查 `evidence.quote` 是否出现在整个 unified diff 中，文件头或未修改上下文行也能满足，从而产生 `review_not_required`。需要只接受实际新增或删除行作为变更证据，不接受文件头、hunk 标记或未修改上下文。

隔离复现输出分别为 `assessment_complete: True` 且最终 `delivered`，以及仅引用 `+++ worktree/farm/worker.py` 即得到 `review_not_required`。审查记录曾保存于 `/private/var/folders/75/6x6659rj7qg0wwzmhcygdp780000gn/T/review-gate-v2-scoped-w9vdw2w6/prepared.json`；该临时路径不应是唯一事实来源。

## 已验证与未验证的边界

- 现有 55 项隔离测试曾通过，但未覆盖上述两条失败路径；通过数字不能代替修复、重新 Review 和最终验证。
- App 内置 CLI `0.166.0-alpha.6` 的**会话级** `SessionStart`、`UserPromptSubmit`、`PreToolUse`、`PostToolUse`、`Stop` 在临时仓库测试中触发；Stop 的 block 产生继续执行信号。多次临时项目级 Hook 加载试验未触发，未安装新的工作区 Hook。不能声称 App 已自动拦截交付或自动响应暂停。
- 真实独立分类器曾在临时样例中识别农场循环间隔、售后重试、共享调度风险及静态展示文案；自动 Reviewer 调用路径也有 Mock 测试。分类器的判断仍有误判可能，实际依赖范围和真实测试证据不能由文本声明证明。
- 上游参考版本固定为 [`8f8e2eef3cfaa8f7a418818adc442450fe6bd884`](https://github.com/KKKKhazix/agent-autoloop/tree/8f8e2eef3cfaa8f7a418818adc442450fe6bd884)。该版本仓库根目录没有实际的 `ops/delivery.json`；格式参考其 Skill 示例和 `plugins/delivery/project.ts`。

本次仅做 Review Gate 范围内的阶段交接；未执行全工作区完整 NEAT、真实业务操作、用户级配置修改、commit 或 push。

## 后续修复与隔离验收（2026-11-06）

本轮继续修复 V2 的两项 Important，并在独立复审中处理 Reviewer 发现的第三个 Important。所有结果均来自临时合成 Git 仓库；由于原 Work 基线已被并行任务推进、`docs/HANDOFF.md` 有同文件并行修改，**这些隔离记录不能作为真实工作区 Delivery 的放行凭证**。

### 修复内容

1. **风险影响范围与审查路由分离。** 分类器结构化结果新增必需字段 `impact_scope_complete`。已确认存在可达执行风险但影响范围不明时，仍可路由到 Reviewer，但 `assessment_complete=false`；即使 Reviewer 无 finding，也停留在 `needs_classification`，不得交付。`review_not_required` 必须明确确认影响范围完整。
2. **免审证据只接受真实变更内容。** 新增 unified diff 解析，只从 hunk 内实际新增/删除源代码行提取证据片段；文件头、hunk 标记、未修改上下文不再构成有效 evidence。解析器也正确处理源代码本身以 `++` / `--` 开头的行。
3. **风险规则不能抹掉原始未完成状态。** 独立 Reviewer 发现确定性风险规则将最终路由提升为 `review_required` 后，代码可能据此错误地把原始 `needs_classification` 覆盖成完成。修复后，`assessment_complete` 同时要求原始分类器结果不是 `needs_classification`、最终分类不是 `needs_classification`、影响范围完整且没有待补运行清单。

### 回归与独立复审

- 新增 8 项回归，覆盖未知影响范围、免审证据误引、真实新增/删除行、缺少范围字段、风险路由覆盖原始未完成状态、最终记录一致性及 diff-like 源行。
- `python3 -m unittest discover -s docs/review-gate -v`：**63/63 通过**。
- 第一轮独立 Reviewer 对隔离 Candidate 发现第三项 Important；修复后第二轮独立 Reviewer 对 `review_gate.py` 和 `test_delivery.py` 复审，**0 finding**，快照与审查记录校验通过。
- 随后在另一临时仓库完整执行 `prepare_delivery → 独立 Reviewer → Verification → complete_delivery / Final Check`，最终状态为 `delivered`。隔离证据保存在 `_sandbox/review-gate/delivery-20261105.jR0NiI/bugfix-independent-review.json`、`bugfix-rereview.json` 和 `bugfix-final-check.json`。

### 阶段交接时尚未完成的边界

- 真实工作区 Delivery 继续阻断：不能用并行推进后的 HEAD 冒充原始 Work 基线，也不能把其他项目的 dirty 文件纳入本次 Candidate。
- Codex App 项目级 Hook 尚未成功加载，任务自动识别、自动调用和硬性阻止漏掉 Delivery 的能力仍未实现；不得宣称自动硬门禁已生效。
- 本轮只修改 Review Gate 的 `review_gate.py`、`test_delivery.py`、`README.md`，未修改农场/售后业务代码、运行数据或用户级配置；未 commit / push。

## 最终收尾与验收（2026-11-06）

### 最终验收结论

- Review Gate V2 核心实现按用户决定收尾。三项 Important 均已修复：影响范围未确认却可能放行、免审证据可引用非变更内容、确定性风险路由覆盖原始 `needs_classification`。
- 完整回归 `python3 -m unittest discover -v` 在 `docs/review-gate/` 执行，**63/63 通过**。
- 第二轮独立只读 Reviewer 对修复后的 `review_gate.py` 与 `test_delivery.py` 返回 **0 finding**；Candidate 快照与 Review receipt 校验通过。
- 临时合成仓库完整执行 `prepare_delivery → 独立 Reviewer → Verification → Final Check`，状态为 `delivered`。证据文件位于 `_sandbox/review-gate/delivery-20261105.jR0NiI/`：`bugfix-independent-review.json`、`bugfix-rereview.json`、`bugfix-final-check.json`。
- 本次另尝试在真实工作区建立新的最终 Work 基线（HEAD `6e651c284ee98276aca7f0e23e0081d4638744d9`，登记 5 个 Review Gate 文件、记录 222 个基线条目）。由于这 5 个文件在新 Work 开始前已经全部存在且未发生本轮差异，`deliver` 正确拒绝空 Candidate（`Candidate 应只包含本轮有变化的文件`）。没有伪造差异、没有把首次无人运行标签用于不相符场景，也没有用当前 HEAD 冒充 2026-11-05 的原始基线。
- 用户确认现有隔离验收结果足以作为本次核心修复的完成依据；因此保留“隔离 Final Check 已通过、未生成真实工作区 Delivery receipt”这一准确边界，不再为了生成 `delivered` 字样制造无意义代码变更。

### 用户决定与现役规则

- **不实现自动 Hook。** 用户认为目前的人工工作习惯已足以控制交付风险，自动 Hook 带来的维护和误拦截成本没有明显收益。此项不进入任何项目 Todo，也不新建工作区总 Todo。
- Review Gate 继续作为工作区共用能力，独立于 Codex Monitor / Status Island；V2 阶段当时约定由 Agent 在开发交付或首次无人运行时显式调用 `deliver`。该触发口径已于 2026-11-06 后续调整：开发阶段不触发 Review，已运行项目仅审查影响下一次真实执行的变更；现行规则以 [`docs/review-gate/README.md`](../../review-gate/README.md) 为准。
- **NEAT 与 Review 分开。** 纯文档/知识整理、坐标核对和历史 dirty 文件不触发 Review；开发阶段不因实现自动化逻辑而触发 Review。项目已实际运行后，只有本轮变更影响下一次无人监管执行时才触发。
- Codex Monitor Todo 中原“工作区无人监管自动 Review Gate”条目已移除；Status Island 原有设计待办保留。Review Gate 不归属 Codex Monitor。

### 收尾边界

- 本次未修改农场、售后等业务代码或运行数据，未修改用户级配置，未安装依赖，未执行真实业务操作。
- 真实工作区仍存在其他项目的并行修改。本次不纳入、不回滚、不提交这些范围外改动。
- 本归档记录的是本次验收依据和用户决定；Review Gate 当前唯一操作规则仍以 `docs/review-gate/README.md` 为准。
