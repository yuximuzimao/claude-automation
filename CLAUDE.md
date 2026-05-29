# 工作区规则

## 语义层铁律

进入任一子项目时，第一步读该项目的 `SKILL.md`。禁止先 grep/glob/smart_search 再读 SKILL.md——语义层是导航地图，先看地图再走路。

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

### 简洁优先
只写解决问题的最少代码。不加推测性功能。不为一次性使用建抽象。自检：「staff engineer 会觉得过度设计？」→ 简化。

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
2. commit 只含代码文件，排除运行时数据（`data/` 下的 JSON/jsonl、日志文件）
3. 禁止 force push，禁止修改已 push 的 commit
4. commit 格式：`<type>(<scope>): <描述>`（type: fix/feat/refactor/docs, scope: aftersales/product-mapping/transfer/workspace）
5. NEVER 提交：`data/` · `*.log` · `_sandbox/` · `_exports/` · `.server.lock`

## SKILL.md 同步铁律

- 任何 commit 包含文件重命名/删除/新增/移动 → 同步更新所属项目 `SKILL.md` PATHS 区块，新文件属核心流程则补 ENTRY MAP
- 谁制造变更谁更新地图：Claude 改的文件 Claude 更新，用户改的文件 Claude 主动检查并更新。pre-commit hook 做安全网

## 目录约定

- 根目录：`CLAUDE.md`（Claude Code 项目规则）、`AGENTS.md`（Codex CLI 入口规则）、子项目文件夹。`.txt` / 截图 / 临时脚本一律归属对应目录
- 新子项目第一步写 CLAUDE.md
- 临时产出放 `_sandbox/`（30 天后还有用→memory 或 docs/，没用→删）
- `docs/HANDOFF.md`：跨 agent 交接文件，工作区脏或跨 session 未完成时写入；已验证完成的以 git commit 为准

## Codex 协作

- Codex CLI 与本工作区并行使用，`AGENTS.md` 为其入口规则
- 分工：Claude Code 主驾驶（业务操作+写操作），Codex 审查/救援/补测试/风险挑战
- 交接：`docs/HANDOFF.md` + git commit 双重握手，启动后先读 HANDOFF.md + git status

## 新项目开工

详见 `docs/new-project-template.md`。触发：用户提到「新项目」「从零开始」「初始化项目」「scaffold」。
