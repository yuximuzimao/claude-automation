# 工作区规则

## 语义层铁律

进入任一子项目时，**第一步读该项目的 `SKILL.md`**。禁止先 grep/glob/smart_search 再读 SKILL.md——语义层是导航地图，先看地图再走路。

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

**默认策略：IO 操作（读文件 / 查数据 / 跨模块分析）优先并行，串行需要理由。**

以下场景无需等用户提示，直接启动并行 Agent：

| 场景 | 并行方式 |
|------|---------|
| 同阶段需要读 ≥3 个无顺序依赖的文件 | 全部同时 Agent，不串行 |
| 跨项目影响面评估 | aftersales + product-mapping 同时检查 |
| bug 根因分析 | 代码路径 / 数据文件 / 相关模块 三路同时 |
| `/simplify` `/review` 类审查 | 多维度独立 Agent 并行 |

**禁止并行**（精确范围）：
- **同一浏览器 session** 的 ERP 写操作（不同 session 的只读操作可并行）
- 有数据依赖的写操作（B 需要 A 的输出才能开始）

## 约束

- 根目录只放子项目文件夹，`.txt` / 截图 / 临时脚本一律归属对应目录
- 新子项目建立时，第一步先写 `CLAUDE.md`

## 临时产出

需要落盘的临时产出放 `_sandbox/`。判断标准：30天后还有用？没用 → `_sandbox`，有用 → memory 或 `docs/`。

## Git 版本管理

所有 git 操作由 Claude 执行。**铁律**：

1. **每次代码修改验证通过后，立即 commit + push**（不能攒到 session 结束）
2. **commit 只含代码文件**，排除运行时数据（`data/` 下的 JSON/jsonl、日志文件）
3. **session 结束前**：`git status` 检查是否有未提交改动，有则 commit + push
4. **禁止 force push**，禁止修改已 push 的 commit

### commit message 规范

```
<type>(<scope>): <简短描述>

type: fix / feat / refactor / docs / data
scope: aftersales / product-mapping / workspace
```

### NEVER 提交

`data/` 运行时数据 · `*.log` · `_sandbox/` · `_exports/` · `.server.lock`

### SKILL.md 同步铁律

Claude 的导航地图必须与代码库保持同步：

1. **任何 commit 包含文件重命名/删除/新增/移动** → 同步更新所属项目的 `SKILL.md` PATHS 区块
2. **新文件属于核心流程** → 补 ENTRY MAP 条目 + DO FIRST（如需要）
3. **谁制造了变更，谁负责更新地图** — Claude 改的文件，Claude 更新 SKILL.md；用户改的文件，Claude 主动检查并更新
4. **pre-commit hook 做安全网** — 检测 PATHS 中引用的文件被删/改名时警告，不阻止 commit

---

## 新项目开工规范

详见 `docs/new-project-template.md`。

**触发加载时机**：用户提到"新项目"/"从零开始"/"初始化项目"/"scaffold"时，主动读取该文件。
