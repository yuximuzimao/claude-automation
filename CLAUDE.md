# 工作区规则

## 语义层铁律

用户用中文项目名、简称或业务词描述任务时，先查 `docs/project-aliases.md` 定位英文目录；命中目录后再读该项目 `SKILL.md`。进入任一子项目时，第一步读该项目的 `SKILL.md`。禁止先 grep/glob/smart_search 再读 SKILL.md——语义层是导航地图，先看地图再走路。

## 浏览器自动化约束（CDP + Element UI）

适用所有项目，违者必踩：

- **验证数据必须读实时源头**：从 ERP 页面/CLI 重新读取，禁止分析 jsonl 历史快照（快照是过期数据，不是真值）
- **querySelector 必须过滤可见元素**：ERP 页面常有同 selector 的隐藏 0×0 元素排在 DOM 前面。必须用 `querySelectorAll` + `getBoundingClientRect().width>0 && height>0` 取第一个可见元素，不能用 `querySelector` 直接取
- **禁止 DOM 移除 Element UI 弹窗**：`parentNode.removeChild()` 移除 `.el-dialog__wrapper` 后 Vue `dialogVisible` 仍为 true，下次触发被 Vue 跳过。必须用 `btn.click()` 走 Vue 关闭流程，再轮询等 `display:none`

## 鲸灵页面操作铁律（风控红线，违者必封IP）

**所有操作 scrm.jlsupp.com 的代码，报错即停，绝对不重试第二次。**

Why: 鲸灵风控将重复失败操作识别为自动化攻击。mimo 模型两次触发 IP 封禁（2026-05-28 并发创建 tab + 2026-05-29 操作报错后重试）。单次失败不封，自动重试会封。根因认知：系统默认把"失败"视为技术异常去恢复，没有识别"失败可能是安全信号"。

How to apply:
- `wait.js` 已内置域名自动识别（`FORCE_NO_RETRY_DOMAINS`），新代码传 `domain` 参数即可
- 行为操作（点击/提交/填写）：maxRetries 强制为 0（域名自动识别）
- 被动等待（导航/DOM ready）：最多重试 1 次（共执行 2 次），不传 domain
- 检测到风控信号 → 就地熔断 + 写入磁盘 `data/circuit-breaker.json`（重启不丢失），需人工 `node cli.js reset-circuit`

## 行为契约

以下规则是对操作铁律的行为层补充，每条对应一类已发生的失败模式。

### 个人本地交付原则
- 只写解决问题所需的最少代码。不加推测性功能。不为一次性使用建抽象。除非是大型或高风险任务，不套用上线标准和完整设计流程。自检：「staff engineer 会觉得过度设计？」→ 简化。
- 流程从简不等于逻辑从简；仍要弄清输入、状态、边界、失败方式和写入影响。售后、审单、ERP 写操作等高风险业务必须严格验证。

### 模型只做判断，不做决策
用 Claude 做：分类、起草、摘要、从非结构化文本中提取。
禁止用 Claude 做：路由选择、重试判断、状态码处理、确定性变换。代码能回答的问题，代码回答。
→ 本条是「报错即停绝不重试」的泛化：不限于鲸灵，所有平台一律如此。

### Token 硬止损
单任务持续无进展消耗上下文 → 总结当前状态，开新分支继续。
不能从当前状态回溯出做了什么 → 停下来，重新对齐。
超过预算不是失败，静默超支才是。

### 失败出声
「完成」= 没有任何东西被静默跳过。
「测试通过」≠ 跳过了边界用例。
不确定是否成功 → 明确说出不确定，不伪装完成。
→ 本条强化风控熔断信号传递：检测到异常不仅要停，还要显式报告不确定状态。

## 跨项目共享知识

`aftersales-automation/` 和 `product-mapping/` 操作同一套系统：
- **鲸灵 SCRM**：`scrm.jlsupp.com`（工单/商品管理）
- **快麦 ERP**：`viperp.superboss.cc`（对应表/档案V2/订单/售后）

共性操作经验（任一项目发现均可参考对方）：
- ERP 完整页面导航（含登录恢复）→ `aftersales-automation/lib/erp/navigate.js`
- ERP 对应表/档案V2 读取规范 → `product-mapping/docs/INDEX.md §5`
- Element UI 弹窗/下拉/表格操作坑位 → 两个项目的 `docs/INDEX.md §6`
- 浏览器自动化通用规范 → memory: `feedback_browser_automation.md`
- **读 JS 文件 >200行**：禁止直接 Read 全文，必须先 `smart_outline` 定位，再 `smart_unfold` 展开目标函数

## 并行执行规则

默认策略：IO 操作优先并行，串行需要理由。无需等提示直接并行：≥3 个无依赖文件、跨项目影响面评估、bug 根因三路分析、审查类多维度 Agent。
**禁止并行**：同一浏览器 session 的 ERP 写操作、有数据依赖的写操作。

## Worktree 强制触发

满足任一条件必须开 worktree，禁止在主分支直接改：
1. 修改 **≥ 3 个文件**
2. 改动包含**流程结构**（pipeline、路由注册、状态机）
3. 涉及**跨项目共享代码**

## Git 版本管理

1. 代码验证通过后立即 commit + push，不攒到 session 结束
2. commit 默认只含代码/文档文件，排除运行时数据（`data/` 下的 JSON/jsonl、日志文件）；用户明确要求归档已完成业务数据轮次时例外，必须单独提交并在 commit message 中说明范围
3. 禁止 force push，禁止修改已 push 的 commit
4. commit 格式：`<type>(<scope>): <描述>`（type: fix/feat/refactor/docs, scope: aftersales/product-mapping/transfer/workspace）
5. NEVER 提交：`*.log` · `_sandbox/` · `_exports/` · `.server.lock`；`data/` 默认不提交，除非用户明确要求归档已完成业务数据轮次
6. **merge 前必须跑 `git diff --diff-filter=D <old> <new>`**：确认不会删除任何运行时数据文件（`data/`、日志、状态文件）。如删除列表非空 → 先备份，再 merge。违反本条导致数据丢失 = 严重事故（2026-07-01 教训：fast-forward merge 删除 211 个 data 文件，实时工单数据永久丢失）

## SKILL.md 同步铁律

- 任何 commit 包含文件重命名/删除/新增/移动 → 同步更新所属项目 `SKILL.md` PATHS 区块，新文件属核心流程则补 ENTRY MAP
- 谁制造变更谁更新地图：Claude 改的文件 Claude 更新，用户改的文件 Claude 主动检查并更新。pre-commit hook 做安全网

## 项目结构与文档职责

- 根目录只维护工作区级规则与路由：`CLAUDE.md`、`AGENTS.md`、`docs/project-aliases.md` 和跨项目协作文档；业务文件必须归属具体子项目。
- 准备长期维护的子项目初始化时必须同时建立：`SKILL.md`、`CLAUDE.md`、`tasks/todo.md`、`docs/INDEX.md`；需要人类快速理解时建立 `README.md`。不能只建其中一两个入口后边做边补。
- **职责唯一，不复制当前状态**：`SKILL.md` = Agent导航；`CLAUDE.md` = 稳定Session启动/安全边界；`README.md` = 人类概览；`docs/INDEX.md` = 文档/数据导航；`tasks/todo.md` = 尚未完成事项。项目存在持续变化的当前状态时，必须单独设 `CURRENT.md`（可位于业务子目录），它是该状态的唯一真值。
- **INDEX不是规则垃圾桶**：小项目可在 `docs/INDEX.md` 放少量通用规则；一旦出现多个独立工作流/规则域，或读取INDEX会被迫加载大量与当前任务无关的规则，必须建立 `docs/rules/README.md` 做路由并按主题拆文件。不要等到单文件几百行才拆。
- **永久规则 / 当前状态 / 历史分离**：跨批次长期方法 → `docs/rules/`；当前状态 → `CURRENT.md`；单次分析/阶段证据 → `docs/archive/` 或项目既有历史目录；临时发现 → `tasks/lessons.md`，稳定后迁走并删除重复项。NEAT只是阶段归档，不承担永久规则入口。
- 新项目的历史文档默认使用 `docs/archive/`（可按 `neat/`、日期或工作流继续分层）；`sessions/` 默认保留给运行时/认证会话。旧项目若已有 `docs/**/sessions/` 文档目录可以保留，但必须明确它是可版本化文档。
- 临时产出放工作区 `_sandbox/`（30天后还有用 → 项目docs/memory，没用 → 删）；不要在项目内新增第二套临时目录。
- `docs/HANDOFF.md`：跨 agent 交接，工作区脏或跨session未完成时使用；已验证完成状态以Git commit为准。

## 项目结构变更门禁

- 新增/删除/移动/重命名入口文档或核心文件时，必须同步 `SKILL.md` PATHS/ENTRY MAP、`docs/INDEX.md` 和所有CURRENT/README中的有效链接。
- 被新结构替代的旧权威文件：先逐项确认内容已迁移，再搜索仓库内有效引用，迁完后直接删除。除非存在明确外部消费者，不保留“兼容跳转壳”；跳转壳会让权威边界继续漂移。
- 删除后允许历史NEAT描述“旧文件当时存在”，但任何当前入口、代码生成器、SOP、todo不得再要求读取旧路径。
- `.gitignore` 的目录规则必须审计作用域。只想忽略根目录时必须写根锚定形式（如 `/sessions/`），禁止用 `sessions/` 误伤子项目同名文档。新增/修改ignore后至少验证一个“应该忽略”样本和一个“绝不该忽略”样本。
- 项目文档目录默认应进入Git。任何文档目录被ignore时必须先判断这是设计意图还是规则误伤，不能长期靠 `git add -f` 维持正常流程。

## Codex 协作

- Codex CLI 与本工作区并行使用，`AGENTS.md` 为其入口规则
- 分工：Claude Code 主驾驶（业务操作+写操作），Codex 审查/救援/补测试/风险挑战
- 交接：`docs/HANDOFF.md` + git commit 双重握手，启动后先读 HANDOFF.md + git status
- **Codex 收件箱**：SessionStart hook 只检查工作区根目录 `docs/codex-handoff/inbox.json`。有未处理条目时注入通知，询问用户是否读全文。协议详见 `docs/codex-handoff/README.md`
- **向 Codex 发请求**：写入合适的 handoff markdown（工作区级默认 `docs/codex-handoff/{project}-{action}.md`，子项目材料可放 `<project>/docs/codex-handoff/`），只在根目录 `docs/codex-handoff/inbox.json` 追加 `{"from": "claude", "status": "unread"}` 条目。完成后移到 processed

## 新项目开工

触发：用户提到「新项目」「从零开始」「初始化项目」「scaffold」。必须先读并执行 `docs/new-project-template.md`，不能只创建代码目录后以后再补文档。

完成初始化前必须同时：
1. 建立模板要求的入口/状态/规则骨架；
2. 在 `docs/project-aliases.md` 注册中文名/触发词；
3. 在 `AGENTS.md` 子项目入口表登记该目录及最小必读文件；
4. 检查 `.gitignore` 是否误伤新项目的文档/数据目录；
5. 从空上下文模拟一次 `SKILL → todo/INDEX → 按需规则/CURRENT` 冷启动，确认不依赖聊天记忆才能恢复项目。

以上任一未完成，不算“项目初始化完成”。
