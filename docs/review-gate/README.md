# 无人监管自动化：独立 Review

这是工作区内所有 Agent 共用的唯一流程，独立于 Codex Monitor / Status Island。**只有到达真实运行节点才进入 Delivery / Review**：首次准备投入无人监管运行，或已经实际运行的项目本轮变更可能影响下一次真实执行。开发、试做、调试且尚未准备运行时，不调用 Work / Delivery，也不因代码中出现自动化机制而提前 Review。当前采用显式调用模式，不安装自动 Hook；是否需要自动触发，留待实际工作习惯或无人监管任务规模发生变化时重新评估。没有 `delivered` 记录时不得声称通过。

## 何时审查

**首次无人监管运行：必须完整 Review。** 在自动化第一次真正交给无人监管执行前，审查完整实际运行代码、配置、规则和必要依赖；即使代码差异为空，也不能省略。

**已经实际运行的项目：只审查影响下一次真实执行的变更。** 包括定时任务、自动触发、队列和资源占用；浏览器、鼠标或键盘操作；账号、权限、操作对象和外部系统；业务数据写入、退款、入库；重试、断点续跑、超时、部分完成、异常恢复、进程生命周期和停止机制；无人监管时 AI 判断及自动执行。影响这些行为的代码、配置和操作规则需要在下一次运行前审查。

**开发阶段不触发 Review。** 新项目尚在开发、试做或调试，尚未准备真实无人监管运行时，即使代码已经包含鼠标操作、队列、重试、账号切换等机制，也只按正常开发流程自测，不提前做完整 Review。等用户明确准备首次实际运行时，再统一审查完整运行版本。

已经运行的项目中，纯展示、文案、坐标核对、文档示例等确认不影响下一次执行的改动，只做适当自检，不强制启动完整 Reviewer。纯 NEAT、文档同步、历史归档和知识整理不触发 Review；发现历史未审查的代码、配置或测试也不触发，已暂停、推翻或待重新设计的旧实现不自动纳入候选集。Review 也不触发 NEAT。不能仅凭目录名、文件扩展名、Git dirty 状态或遗留文件数量判断风险。

## Delivery 生命周期

1. **Work**：只在上述真实运行节点启动。已运行项目准备修改可能影响下一次执行的行为时，在本轮修改前登记原始需求、验收条件、计划文件和必要上下文；首次运行则登记完整运行清单。捕获任务开始时的 HEAD、索引与工作区内容，并在本地记录 Git dirty 文件指纹，以及根规则、Review Gate 规则/实现/策略和已登记项目策略的基线。开发阶段不创建 Work / Delivery，正常开发并持续自测；真实业务操作仍遵守人工确认。
2. **Delivery Candidate**：独立声明本任务每个候选文件的预期索引和工作区内容；工具对比 Work 基线，生成本任务差异。已登记文件出现未声明变化、预期与实际不一致、缺少开始基线或候选文件未在 Work 登记，均拒绝进入 Review。不得为了通过而把历史遗留文件加入 Candidate。首次无人运行须登记并审查完整实际运行代码、配置及规则，即使差异为空；运行依赖无法确认完整时停止并报告。
3. **风险判断与 Review**：`deliver` 综合原始目标、实际 Candidate 差异、完整候选代码、必要上下文和 [工作区策略](policy.json) 判断。在已运行项目的 `unattended_change` 阶段，明确的执行风险规则可以强制启动 Review，但不能覆盖分类器原始的未完成状态；即使路由被提升为 `review_required`，原始分类为 `needs_classification` 仍不得标记 `assessment_complete`。其他情况由独立只读分类器返回 `review_required`、`review_not_required` 或 `needs_classification`。免审必须逐个候选文件给出实际新增或删除行中的原文证据；diff 文件头、hunk 标记和未修改上下文不算证据。证据不足、模型不可用或影响范围未确认时不能放行。已识别执行风险但调用关系不明时，仍先启动 Review；分类器必须返回 `impact_scope_complete=false`，Review 无 finding 也不得交付，补清范围后必须重新分类。文件路径只作辅助，Markdown 等文本仍由语义分类器判断是否改变自动化规则。必审时自动启动独立 Reviewer；Reviewer 不修改文件，也不执行被审查代码、命令、配置或 Hook。
4. **Revision**：主 Agent 独立核验 finding；成立的问题修复后，以同一 Work 基线和更新后的独立声明生成新 Candidate，并重新 Review。可用代码和验证证据反驳不成立的 finding。Critical / Important 未处理时不得进入 Verification。
5. **Verification**：首次 `deliver` 成功后进入 `waiting_verification`；再按项目 SOP 执行必要测试和实际验收，记录名称、结果和可核验证据。工具检查记录的完整性，不代替执行测试，也不判断证据真假；Reviewer 不能替代真实运行验收或人工确认。
6. **Final Check → Delivered**：使用同一个 `deliver` 入口提交验证记录；工具重新检查 Work、Candidate、Policy 和 Review，并重新评估风险。任一不匹配、重要 finding 未处理、记录缺失或结果失败都不能 Delivered。最终检查与交付之间若内容变化，须重新走 Candidate、Review、Verification 和 Final Check。工具不提交、发布或执行任何业务操作。

## 操作

以下在工作区根目录执行；`_sandbox/` 是忽略提交的本地临时位置，适合保存本轮请求和记录。只创建本任务独有目录，不覆盖已有文件；请求含用户需求，请按本地敏感资料处理。确认基线必须是**任务开始时**的完整 SHA，不能为了通过而换成当前 HEAD。

```sh
umask 077
mkdir -p "$PWD/_sandbox/review-gate"
DIR=$(mktemp -d "$PWD/_sandbox/review-gate/delivery.XXXXXX")
printf '本轮目录：%s\n' "$DIR"
```

**修改前**准备该目录下的 `request.json`；完整保留用户原始需求和验收条件，不附实现者的推理。`files` 是本任务计划修改的全部文件；可能新建的文件也要预登记，首次无人运行则列全实际运行文件。`context` 是必要现役规则和上下游文件，路径均相对于仓库根目录且不得重复。若上下文本身已有未暂存或未跟踪内容，将它登记在 `files`，最终未修改时在 `claim.context` 明确列为必要依赖；不要把它当作本轮改动。任务开始后 `context` 的文件或索引变化时，流程拒绝继续。只登记所需材料，不发送认证文件、运行数据或不相关用户资产。禁止事后用当前内容冒充任务开始状态；无法证明基线或范围时停止并报告。

```json
{
  "base": "任务开始时的完整commit SHA",
  "requirements": "用户原始需求与验收条件",
  "files": ["项目/本任务修改文件.py", "项目/本任务可能新增文件.py"],
  "context": ["CLAUDE.md", "项目/SKILL.md", "项目/必要SOP.md"]
}
```

使用上一步创建的 `DIR`；另开终端时将 `DIR` 指向该唯一目录。**开发阶段不执行 Work / Delivery**。项目已经实际投入无人监管运行，且本轮改动可能影响下一次执行时，使用 `--activity unattended_change`；首次准备投入无人监管运行时，使用 `--activity unattended_first_run` 并登记完整运行文件。旧标签 `auto` 仅视为开发阶段，不再触发 Review，也不能用于创建 Work。

```sh
python3 docs/review-gate/review_gate.py work --repo "$PWD" --activity unattended_change \
  --request "$DIR/request.json" --work "$DIR/work.json"
```

`work` 同时创建仅当前用户可读写的 `work.json.key`，用于校验 Work 和 Delivery 记录；不要上传或分享密钥，丢失或权限不安全时流程阻断。当前 Work 格式为 V4，Candidate 为 V3。旧 Work（包括已签名 V3）缺少必要的规则/工具基线，只保留为历史证据，不能自动升级、重签或用于新版交付。确需重新审查时，应明确登记一个新的审查节点，保留旧记录和失败结果；不得声称新节点是原开发任务的开始，也不得借此掩盖原候选中的未声明变化。

开发中根据自己实际执行的编辑维护独立的 `claim.json`：对于每个**本任务**候选文件，`index` 和 `worktree` 写预期状态；状态为 `null` 表示不存在，否则为 `{"mode":"100644","text":"完整 UTF-8 文本"}`（可执行文件为 `100755`）。未暂存的原有内容可从 `work.json` 的 `record.start.files[路径]` 复制为起点，再只应用本任务编辑；保留原有暂存区内容。原先登记在 `files` 中、最终未修改但仍是审查必需的依赖，明确放入 `claim.context`；其他未修改文件不自动送审。首次无人运行应设置 `runtime: true` 并声明全部已登记的实际运行文件，既有修改又有未修改文件时也一样。若分类器从原始目标识别出首次运行但没有完整清单，流程阻断并要求补齐；无法确认是否需要清单时不得交付。不能把不明来源的最终状态直接当作自己做出的修改；若有人同时改了同一文件或不能核实每项变化，停止并报告。

```json
{
  "files": {
    "项目/本任务修改文件.py": {
      "index": {"mode": "100644", "text": "任务开始时的暂存内容"},
      "worktree": {"mode": "100644", "text": "在原有内容上完成本任务后的预期内容"}
    }
  },
  "context": ["项目/已登记但未修改的必要依赖.py"],
  "runtime": false
}
```

若没有这类依赖，`context` 写空数组。最初已登记在 `request.context` 的规则和依赖会自动包含，无须重复填写；不得把本任务已修改的文件伪装为上下文。

完成实现后进入 Delivery；`prepared.json` 必须是新路径。第一次调用会自动生成 Candidate、分类，并在需要时启动 Reviewer；进入 `waiting_verification` 时退出码为 2，表示**尚未交付**。`needs_classification`、`review_failed`、`revision_required` 或 `blocked` 均不得收口；核实上下文或修复后使用新文件重新进入 Delivery。

```sh
python3 docs/review-gate/review_gate.py deliver --repo "$PWD" --work "$DIR/work.json" \
  --claim "$DIR/claim.json" --delivery "$DIR/prepared.json"
```

实际完成项目要求的验证后，再创建或更新 `checks.json`，例如 `[{"name":"隔离测试","result":"passed","evidence":"命令与结果位置"}]`，再使用同一入口完成最终检查。工具要求该文件时间晚于 `prepared.json`，但时间戳和文字仍不能证明测试确实执行。`delivered` 且退出码为 0 才表示工具检查通过；这不代表真实业务已验收。

```sh
python3 docs/review-gate/review_gate.py deliver --repo "$PWD" --work "$DIR/work.json" \
  --prepared "$DIR/prepared.json" --checks "$DIR/checks.json" --delivery "$DIR/delivered.json"
```

底层 `candidate`、`review`、`verify`、`check` 仅供诊断，不是交付入口。Reviewer 发现 Critical / Important 时，先核验并修复，再以同一 Work 和更新的 claim 重新进入 `deliver`。主 Agent 若核实某项不成立，可另写反驳文件并在第二次 `deliver` 加 `--refutations <文件路径>`；下例 `index` 是 finding 的零基索引，`snapshot` 必须原样复制 `prepared.json` 的 `record.candidate.id`：

```json
[
  {"index": 0, "snapshot": "sha256:Candidate指纹", "reason": "不成立的具体原因", "evidence": "对应代码位置和验证证据"}
]
```

工具只检查反驳和验证记录的结构、索引及指纹，**不会自动证明反驳或测试证据正确**。只支持普通 UTF-8 文本；符号链接、子模块、二进制、过大材料、未解决索引冲突和不完整输入会拒绝。任务开始时文件已有未暂存或未跟踪内容、随后该文件的索引发生变化时，也会拒绝；相关 HEAD 变化、必要规则/策略变化或范围外文件依赖关系未确认时同样拒绝，具体判定见下节。不能用当前状态冒充原基线；须停止并报告。Git 忽略的普通文件不会进入清单；候选及必要上下文所属项目的 `.review-gate.json` 即使被忽略也会单独绑定指纹，包括其原先不存在、后来新增的情况。超过 64 MiB 的 dirty 文件只比较大小、时间和 inode；首次运行依赖是否完整仍需主 Agent 核实。记录使用本地密钥校验，可防止直接改状态字段；同一用户仍能读取密钥，不能作为不可伪造的安全边界。

## 并发修改与审查影响范围

审查有效性绑定本次候选内容、运行依赖、必要上下文、审查工具/策略及相关 Git 状态，不要求整个多项目仓库冻结。Work 的全仓 dirty 清单用于保留现场和发现尚未解释的变化，**不表示所有 dirty 文件都是本任务风险**。捕获时复核候选、上下文、规则与工具的一致性；其他项目在捕获瞬间继续修改，不要求全仓清单静止。

- **始终相关**：`request.files`、`request.context`、`claim.context` 中的候选及依赖；根 `AGENTS.md` / `CLAUDE.md`；本目录 README、执行中的 `review_gate.py` 和 `policy.json`；已登记文件及上下文所属项目的 `.review-gate.json`。自动绑定规则即使未列入 request，也不能绕过变化检查；审查所需的规则正文和依赖仍应显式登记提供给模型。共享模块、配置及跨项目调用依赖必须按实际关系登记，不能按目录边界忽略。
- **默认未知**：Work 后新增、删除、重命名、修改或仅暂存区变化的范围外文件。错误逐项列出路径并要求核实依赖；未知不等于已确认危险，也不等于无关。
- **有依据的无关文件**：可在 `claim.outside_scope` 按精确路径声明 `reason` 和 `evidence`。证据应说明核查的运行入口、调用/导入、共享模块、配置和上下文关系，可补充用户明确确认；仅写“目录不同”不够。允许声明的路径必须属于 Work 时已有受 Git 跟踪根 `SKILL.md` 的其他项目，且不能属于任一已登记文件/上下文所在项目。这个项目识别仅限制声明的适用边界，不能证明无关。根文件、共享区域、必要依赖、策略和当前项目文件不能排除；不支持目录通配或永久豁免。
- **独立核查**：声明会绑定 Candidate 并交给现有独立分类器和 Reviewer；首次运行只要带此声明，也必须分类核查依赖。分类器同时收到被排除文件当前 HEAD、索引和工作区的完整内容，核查反向调用、共享桌面/session/账号资源及配置耦合；Work dirty 指纹只作历史证据，不冒充历史内容。证据不足或发现可能的跨项目依赖时，分类器必须返回 `impact_scope_complete=false` 并说明具体文件和缺失关系；Review 无 finding 也不能交付。工具检查路径边界和声明结构，不能证明文字证据真实，也不声称自动构建了完整调用图。主 Agent 必须核实完整依赖。

例如，核实两个项目没有相关调用、共享配置或上下文依赖后，可在原 claim 中增加（下列证据仅演示结构，必须替换为本次实际核查结果）：

```json
{
  "outside_scope": {
    "other-project/docs/CURRENT.md": {
      "reason": "用户确认这是独立项目的状态更新，与本次运行无关",
      "evidence": "已核查本次入口及其依赖清单；逐项说明为什么该文件不参与调用、配置读取或操作规则"
    }
  }
}
```

声明不修改 Work，也不把范围外文件并入候选。新增排除路径或改变声明依据会生成新的 Candidate，必须重新审查。已声明无关的同一路径后续内容或索引变化不直接撤销主体 Review，但**必须用最新内容重新核查无关性**；出现关联或不确定时阻断。prepare 和最终交付分别保存 `outside_material` 及分类结果中的 `scope_hash`；最终记录另存 `scope_assessment`，绑定最新范围证据。Review 期间范围外内容变化时补做一次当前范围核查；核查过程中材料再次变化则报告具体文件，不沿用失效结论。`observations` 另外记录实际 HEAD、范围外变动和最终读取的逐文件内容指纹；最终指纹必须与分类器实际核查的材料一致，否则指出文件并阻断。这些观测不混入 Candidate 身份。出现新的未声明路径仍须核实。重命名同时检查源、目标路径，目标进入当前项目或共享区域时不能凭源路径的无关声明放行。

Git 状态按实际影响处理：

| 变化 | 处理 |
| --- | --- |
| 候选内容/模式/索引与 claim 不符，或已登记文件变化却未声明 | 阻断并指出文件；核实来源，更新 claim 后生成新 Candidate / Review |
| 任务开始时已有未暂存内容，后来索引改变 | 继续阻断，防止把历史内容当作本次修改 |
| 必要上下文内容或索引、未登记为候选的自动绑定规则/策略变化 | 原审查不能沿用；核实并明确登记新的审查节点，保留原 Work |
| 规则/策略/工具本身在 Work 中预登记为候选 | 只允许与 claim 一致的修改；当前指纹绑定 Candidate，后续变化使 Review 失效。工具自身审查边界见下文 |
| HEAD 前进且树差异仅涉及已声明无关文件 | 保留原 Work HEAD 作为比较锚点，在 observations 记录当前 HEAD；相关树、索引、内容不变，且最新范围核查仍确认无关时继续 |
| HEAD 涉及候选、依赖、规则或策略的树变化 | 阻断；即使工作区文本看似相同，也不能沿用旧审查 |
| HEAD 前进但包含未知路径 | 按范围外未知依赖逐项核实 |
| HEAD 不是 Work 基线的后代 | 拒绝，不能把换基或历史重写当作无关并发提交 |

这里只比较当前树与 Work 树的实际差异，不以无内容变化的提交元数据使审查失效；不提供原子文件系统冻结。最终检查后至实际运行前，相关材料仍须保持一致。

## 实现与验证入口

- [review_gate.py](review_gate.py)：Work、范围判定、Candidate、独立分类/Review 和最终交付的唯一实现。
- [policy.json](policy.json)：全局执行风险策略；项目只能补充正向触发词。
- [test_review_gate.py](test_review_gate.py)：快照、声明、索引与基础生命周期测试。
- [test_delivery.py](test_delivery.py)：交付分类、完整性校验及并发范围测试（`ConcurrentScopeTests`）。运行 `python3 -m unittest discover -s docs/review-gate -p 'test_*.py'`；测试使用隔离临时 Git 仓库和替身模型，其通过不等于真实独立 Review 通过。

修改 Review Gate 会影响下一次真实审查，必须做针对性验证和独立只读审查。不能仅让修改后的工具给自身生成 `delivered` 就宣称可信自证；应使用修改前保留的固定 Reviewer 调用器，对最终实现、差异、规则和测试材料做独立审查，并保存材料指纹与结果。该结果是工具变更的独立代码审查证据，不自动成为任何业务任务的 Delivery，也不能代替业务验证。模型不可用、审查失败或重要 finding 未解决时应明确报告，不伪造通过；特定用户授权只适用于其明确范围，不修改全局规则。

## 工作区与项目策略

全局策略只维护在 [policy.json](policy.json)；其中正向代码规则仅在 `unattended_change`（项目已实际运行）阶段作为额外审查底线，不能把候选直接判为免审，也不能让开发阶段提前触发 Review。项目确有额外要求时，可在项目根目录放 `.review-gate.json`，只接受 `{"version":1,"required_code_terms":["专用动作("]}`，同样只在 `unattended_change` 阶段增加需 Review 的代码词；不能关闭、删除或覆盖全局规则。项目现役 SOP 应作为 Work 的上下文提供，不批量修改项目 Skill。项目策略读取失败或格式不符时阻断，不默认免审。

## 隔离与实际强度

- 独立 CLI 会话使用临时目录、`--ignore-user-config`、`--ignore-rules`、`--ephemeral`、只读沙箱，禁用用户 Hook、记忆、插件、多 Agent、shell、unified exec、code-mode host、网页搜索和自动 Skill 指令；`project_doc_max_bytes=0` 避免自动装载项目指令。只向模型传入审查请求和所选文本，未检出或执行这些文本。仍需本机 Codex CLI 和可用的既有身份/模型连接；若本机参数、受管配置或网络改变导致隔离或调用不可验证，应停止并报告。
- 本机在 Codex App 会话中可调用该 CLI；这只证明当前环境的独立调用可用，不证明 App 已自动触发。App 子 Agent 继承父会话的沙箱和权限，单靠“只读”提示不能给它单独设置只读沙箱，因此当前不以子 Agent 代替 CLI 的隔离审查。能力依据见 [Codex 子 Agent 官方说明](https://learn.chatgpt.com/docs/agent-configuration/subagents)。
- Work 指纹覆盖原始需求、任务开始状态、已登记范围和本地 Git dirty 指纹；Candidate 指纹绑定 Work、声明的本轮差异、候选状态、上下文、范围外声明和当前规则/工具指纹；范围外观测单独记录。`deliver` 在分类、Review 和最终检查之间重新核对；变化使旧记录失效。无原子冻结，最终检查与实际交付之间仍须避免并发修改。
- 统一入口内的分类、必要时自动调用 Reviewer 和最终阻断是工具行为；**启动 Work / Delivery、完整登记文件、判断用户是否在暂停、核实验证及反驳证据，仍由 Agent 遵守规则。** `deliver --pause` 会立即返回暂停，但没有已验证的项目 Hook 自动中断已运行的子进程。不能把模型分类或规则提示当作绝对保证。
- 本机 App 内置 CLI 的会话级 `SessionStart`、`UserPromptSubmit`、`PreToolUse`、`PostToolUse` 和 `Stop` 已在临时仓库触发；`Stop` 的 block 要求继续一轮，并不是不可绕过的任务终止锁。多次隔离试验中项目级 Hook 未加载，因此本工作区当前不安装项目级自动 Hook，统一流程采用 Agent 显式调用 `deliver` 的方式启动。不得声称漏调用会被自动拦截。

## 参考依据

2026-11-05 重新检查 [Agent Autoloop commit `8f8e2eef3cfaa8f7a418818adc442450fe6bd884`](https://github.com/KKKKhazix/agent-autoloop/tree/8f8e2eef3cfaa8f7a418818adc442450fe6bd884)：[`review.ts`](https://github.com/KKKKhazix/agent-autoloop/blob/8f8e2eef3cfaa8f7a418818adc442450fe6bd884/plugins/delivery/review.ts)、[`delivery.ts`](https://github.com/KKKKhazix/agent-autoloop/blob/8f8e2eef3cfaa8f7a418818adc442450fe6bd884/plugins/delivery/delivery.ts)、[`project.ts`](https://github.com/KKKKhazix/agent-autoloop/blob/8f8e2eef3cfaa8f7a418818adc442450fe6bd884/plugins/delivery/project.ts)、相关测试和 [`SKILL.md`](https://github.com/KKKKhazix/agent-autoloop/blob/8f8e2eef3cfaa8f7a418818adc442450fe6bd884/skills/agent-autoloop/SKILL.md)。该版本仓库根目录没有 `ops/delivery.json`；项目配置格式来自 Skill 示例与 `project.ts` 校验。上游在 PR 交付流程中审查文本快照，并在后续步骤核对 head / main；本流程额外覆盖明确列出的未提交、暂存和未跟踪文件，不安装上游项目。

[OpenAI Codex Hook 文档](https://learn.chatgpt.com/docs/hooks)说明项目 Hook 依赖信任，Stop Hook 提供继续执行信号；其存在不代表本工作区已启用或已具备准确的任务级识别。
