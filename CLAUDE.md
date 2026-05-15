# 工作区规则

## 语义层铁律

进入任一子项目时，第一步读该项目的 `SKILL.md`。禁止先 grep/glob/smart_search 再读 SKILL.md——语义层是导航地图，先看地图再走路。

## 浏览器自动化约束（CDP + Element UI）

适用所有项目，违者必踩：

- **验证数据必须读实时源头**：从 ERP 页面/CLI 重新读取，禁止分析 jsonl 历史快照（快照是过期数据，不是真值）
- **querySelector 必须过滤可见元素**：ERP 页面常有同 selector 的隐藏 0×0 元素排在 DOM 前面。必须用 `querySelectorAll` + `getBoundingClientRect().width>0 && height>0` 取第一个可见元素，不能用 `querySelector` 直接取
- **禁止 DOM 移除 Element UI 弹窗**：`parentNode.removeChild()` 移除 `.el-dialog__wrapper` 后 Vue `dialogVisible` 仍为 true，下次触发被 Vue 跳过。必须用 `btn.click()` 走 Vue 关闭流程，再轮询等 `display:none`

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
4. commit 格式：`<type>(<scope>): <描述>`（type: fix/feat/refactor/docs, scope: aftersales/product-mapping/workspace）
5. NEVER 提交：`data/` · `*.log` · `_sandbox/` · `_exports/` · `.server.lock`

## SKILL.md 同步铁律

- 任何 commit 包含文件重命名/删除/新增/移动 → 同步更新所属项目 `SKILL.md` PATHS 区块，新文件属核心流程则补 ENTRY MAP
- 谁制造变更谁更新地图：Claude 改的文件 Claude 更新，用户改的文件 Claude 主动检查并更新。pre-commit hook 做安全网

## 目录约定

- 根目录只放子项目文件夹，`.txt` / 截图 / 临时脚本一律归属对应目录
- 新子项目第一步写 CLAUDE.md
- 临时产出放 `_sandbox/`（30 天后还有用→memory 或 docs/，没用→删）

## 新项目开工

详见 `docs/new-project-template.md`。触发：用户提到「新项目」「从零开始」「初始化项目」「scaffold」。
