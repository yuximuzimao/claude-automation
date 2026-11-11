# Git 版本管理操作手册

仓库：`git@github.com:yuximuzimao/claude-automation.git`（私有，主分支 `main`）

## 适用范围与 Agent 分工

- 本手册适用于所有在此工作区执行任务的 Agent；**Git 操作没有固定的 Claude / GPT / Codex 执行者**。
- 独立执行时，由当前承担任务的 Agent 在用户授权范围内自行检查、暂存、提交和推送，不需要等待或转交给另一个 Agent。
- 跨 Agent 协作时，任务发起方可以请另一方审查、补测、接手 Git 操作或推送；反向同样成立。交接协议见 [`docs/codex-handoff/README.md`](codex-handoff/README.md)。
- 只有确实需要另一个 Agent 接手时，才使用 `docs/HANDOFF.md` / `docs/codex-handoff/`；单 Agent 独立完成时，不必创建交接材料，也不必等待另一方。
- 提交时机、运行时数据边界及其他工作区红线，以根目录 `CLAUDE.md`「Git 版本管理」为准；本手册提供具体操作方法。

## 提交时机

- 默认保留在当前工作区，不自动 commit / push。
- 只有用户明确要求按 NEAT 归档、提交或推送时，才执行对应操作；只要求 commit 时不擅自 push。
- 临时探索、未验证代码不提交。
- 不因大改动、Session 结束或修复 bug 本身而自动创建检查点提交。

## 提交信息格式

```
<类型>(<范围>): <描述>
```

类型：`feat` 新功能 / `fix` 修复 / `refactor` 重构 / `docs` 文档 / `chore` 必要杂项。

示例：
- `feat(aftersales): 新增拦截快递行动Tab`
- `fix(erp): 修复拒绝原因下拉未选中bug`

## 标准提交流程

```bash
git status --short                  # 确认当前工作区状态
git diff --stat                     # 查看未暂存改动
git diff --cached --stat            # 查看已暂存改动
git add <具体文件或目录>             # 只暂存本次授权范围
git diff --cached --check           # 检查暂存差异格式
git diff --cached                   # 逐项确认实际提交内容
git commit -m "<类型>(<范围>): <描述>"
git push                            # 仅在用户要求推送时执行
```

- 禁止用 `git add -A` 或无范围的批量暂存；必须指定具体文件，避免误加其他项目修改、`data/`、日志和临时文件。
- 如果暂存区原本已有用户改动，先识别并保留，不得覆盖、重置或混入本次提交。
- 提交后告知用户：改了什么、commit id 前 7 位，以及是否已 push。

## 不提交的内容

除非根目录规则和用户明确授权另有规定，以下内容不得进入提交：

- `data/` 下的运行时 JSON / JSONL 和业务运行数据
- `*.log`
- `_sandbox/`、`_exports/`
- `.server.lock`

运行时数据归档必须作为单独范围处理，并在 commit message 中明确说明；不能顺手混入代码提交。

## 回滚与合并安全

- 优先检查历史并恢复单个文件；覆盖用户当前修改前，必须确认影响范围。
- 禁止 force push，禁止擅自改写已经 push 的提交。
- `reset --hard`、批量回滚、删除远程分支等破坏性操作必须先向用户说明影响并取得明确确认。
- **merge 前必须运行 `git diff --diff-filter=D <old> <new>`**，确认不会删除任何运行时数据文件（`data/`、日志、状态文件）。删除列表非空时先备份并确认，不能直接合并。
