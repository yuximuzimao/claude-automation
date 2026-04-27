# 工作区规则

## 目录结构

| 目录 | 用途 |
|------|------|
| `aftersales-automation/` | 鲸灵售后自动化系统 |
| `product-mapping/` | 快麦商品对应表匹配核查（与售后同系统） |
| `sessions/` | 鲸灵多账号 Session 管理 |
| `reviews/` | 周/月回顾报告 |
| `_exports/` | 对话导出 `.txt`，按需归档 |
| `_sandbox/` | 临时落盘产出（一次性脚本、测试数据、评估报告），超过30天清理 |

## 跨项目共享知识

`aftersales-automation/` 和 `product-mapping/` 操作同一套系统：
- **鲸灵 SCRM**：`scrm.jlsupp.com`（工单/商品管理）
- **快麦 ERP**：`viperp.superboss.cc`（对应表/档案V2/订单/售后）

共性操作经验（任一项目发现均可参考对方）：
- ERP 完整页面导航（含登录恢复）→ `aftersales-automation/lib/erp/navigate.js`
- ERP 对应表/档案V2 读取规范 → `product-mapping/docs/INDEX.md §5`
- Element UI 弹窗/下拉/表格操作坑位 → 两个项目的 `docs/INDEX.md §6`
- 浏览器自动化通用规范 → memory: `feedback_browser_automation.md`

## 约束

- 根目录只放子项目文件夹，`.txt` / 截图 / 临时脚本一律归属对应目录
- 新子项目建立时，第一步先写 `CLAUDE.md`

## 何时用 _sandbox/

**需要落盘的临时产出**放 `_sandbox/`，例如：一次性脚本、测试截图、评估 HTML、临时数据文件。

**不需要放 _sandbox/ 的情况**：
- 方法论、操作经验、核查结论 → 写进 **memory**（跨 session 复用）
- 长期有效的规则、流程 → 写进项目 **docs/**
- 纯对话过程中的中间结果 → 不落盘

判断标准：「这个文件30天后还有用吗？」没用 → _sandbox，有用 → memory 或 docs。

## 命名约定

- 子项目目录：小写中划线（如 `aftersales-automation`）
- 下划线前缀目录（`_exports/`、`_sandbox/`）表示非核心/可清理内容
- 导出文件：`_exports/YYYY-MM-DD-<描述>.txt`

## Git 版本管理

### 仓库信息
- 远程仓库：`git@github.com:yuximuzimao/claude-automation.git`（私有）
- 主分支：`main`
- 所有 git 操作由 Claude 执行，用户无需手动操作

### 提交时机（触发条件）

| 场景 | 是否提交 | 说明 |
|------|---------|------|
| 功能验证通过（脚本跑通、页面操作成功） | **立即提交** | 验证完成是提交的前提，不提前提交未验证代码 |
| 做较大改动前 | **先提交当前状态** | 作为安全检查点，出问题可快速回滚 |
| Session 结束前有未提交改动 | **提交** | 防止进度丢失 |
| 修复了一个 bug | **提交** | 独立记录，方便日后定位 |
| 仅修改了文档/规则文件 | **提交** | docs 也需要版本追踪 |
| 临时探索、未验证代码 | **不提交** | 等验证通过再提交 |
| _sandbox/ 里的临时脚本 | **不提交** | 已在 .gitignore 中排除 |

### 提交信息格式

```
<类型>(<范围>): <描述>
```

| 类型 | 用途 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `refactor` | 重构（不影响功能） |
| `docs` | 文档/规则更新 |
| `data` | 数据文件变更（cases.jsonl 等） |
| `chore` | 配置、依赖等杂项 |

示例：
- `feat(aftersales): 新增拦截快递行动Tab`
- `fix(erp): 修复拒绝原因下拉未选中bug`
- `docs(product-mapping): 更新档案V2操作规范`

### 操作规范（Claude 执行）

**提交前必做：**
```bash
git status          # 确认改动范围
git diff --stat     # 核查文件列表无敏感数据
```

**标准提交流程：**
```bash
git add -A
git commit -m "<类型>(<范围>): <描述>"
git push
```

**提交后必说：** 告知用户提交了什么、commit id 前7位，方便日后回滚定位。

### 回滚手册

```bash
# 查看历史（找目标版本）
git log --oneline -20

# 恢复单个文件到指定版本（最常用，不影响其他文件）
git checkout <commit-id> -- 文件路径

# 查看某次提交改了什么
git show <commit-id> --stat

# 完全回滚到某版本（危险，会丢失之后所有改动）
git reset --hard <commit-id>
git push --force   # 需用户确认后执行
```

> **回滚原则**：优先用单文件恢复，避免 `reset --hard`；如需全量回滚，必须先向用户说明影响范围并等待确认。

---

## 新项目开工规范

### 标准目录结构

```
project/
  CLAUDE.md           # Session 启动 + 目录说明 + 相关项目引用 + 教训沉淀流程
  cli.js              # 主命令入口
  lib/                # 核心模块（从其他项目移植时，文件头注明来源）
  docs/
    INDEX.md          # §分节规则文档，§6 为已知坑位（格式见售后/商品匹配项目）
  data/               # 结构化持久数据（禁止放日志/临时文件）
  tasks/
    todo.md           # 当前待办（每次 session 启动必读）
    lessons.md        # 临时教训（稳定后迁入 docs/INDEX.md §6）
  package.json
```

### 文件存放铁律

- **试错/原型脚本** → 工作区 `_sandbox/`，不在项目内建 _sandbox/
- **运行日志** → console 输出，不落盘；调试需要时放 `_sandbox/`
- **data/ 只放**：结构化持久数据（JSON/图片/报告），禁止放日志、临时文件
- **每次新建文件必问**：30天后还有用吗？没用 → _sandbox 或不落盘
- **移植代码**：文件头注明来源，如 `// 移植自 aftersales-automation/lib/erp/navigate.js`

### CLAUDE.md 必要段落

```markdown
# <项目名>

## Session 启动（必做，按顺序）
1. 读 `tasks/todo.md` — 确认当前待办和进度
2. <项目特有的启动命令>
3. 读 `docs/INDEX.md` — 所有操作规则的权威入口

## 规则文档（渐进式，按需加载）
| 文档 | 加载时机 |

## 教训沉淀流程
- `tasks/lessons.md` — Session 级新发现，先记这里
- `docs/INDEX.md §6` — 稳定后迁入，不在两处重复维护

## 相关项目
- `../other-project/` — 说明共享的系统/操作，及关键文档位置

## 目录说明
| 目录 | 用途 |（只列实际存在的目录）
```
