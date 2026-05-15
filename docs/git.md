# Git 版本管理操作手册

仓库：`git@github.com:yuximuzimao/claude-automation.git`（私有，主分支 `main`）  
所有 git 操作由 Claude 执行。

## 提交时机

| 场景 | 动作 |
|------|------|
| 功能验证通过 | 立即 commit + push |
| 做较大改动前 | 先 commit 当前状态作为检查点 |
| Session 结束前有未提交改动 | commit + push |
| 修复 bug / 更新文档 | commit + push |
| 临时探索、未验证代码 | 不提交 |

## 提交信息格式

```
<类型>(<范围>): <描述>
```

类型：`feat` 新功能 / `fix` 修复 / `refactor` 重构 / `docs` 文档
> `data` 类型已停用——运行时数据不入 git。杂项用 `chore` 仅在必要时使用。

示例：
- `feat(aftersales): 新增拦截快递行动Tab`
- `fix(erp): 修复拒绝原因下拉未选中bug`

## 标准提交流程

```bash
git status && git diff --stat          # 确认改动范围
git add <具体文件>                       # 不要 git add -A，排除 data/ *.log 等
git commit -m "<类型>(<范围>): <描述>"
git push
```

> `git add -A` 会误加 `data/`、日志等禁止提交文件，必须用 `git add <path>` 指定文件。

提交后告知用户：改了什么 + commit id 前7位。

## 回滚操作

```bash
# 查看历史
git log --oneline -20

# 恢复单个文件（最常用，不影响其他文件）
git checkout <commit-id> -- 路径/文件名

# 查看某次提交的改动
git show <commit-id> --stat

# 全量回滚（危险，需用户确认）
git reset --hard <commit-id>
git push --force
```

> 优先单文件恢复；全量回滚必须告知影响范围并等用户确认。
