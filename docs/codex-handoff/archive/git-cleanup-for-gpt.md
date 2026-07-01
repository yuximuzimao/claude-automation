# Git 仓库整理计划（修订版）

> **已完成** 2026-07-01。main 现为唯一主干。⚠️ merge 过程发生数据丢失事故（211 个 data 文件），已恢复。详见 [[feedback-git-merge-data-loss]]。

## 背景

当前仓库实际情况：

```text
默认远程分支：main
当前长期开发分支：data-model-restructure

main                     cd555ae
data-model-restructure   bb27741
```

GitHub 默认分支已经是 `main`。

问题不在于仓库结构，而在于长期开发工作一直发生在 `data-model-restructure` 上，导致：

- 分支名称与实际职责不一致
- `main` 长期落后
- 新成员（包括 AI Agent）容易误判主干分支
- 后续功能开发继续堆积在历史改造分支上

仓库本质是个人 Monorepo：

```text
aftersales-automation
codex-monitor
lkwj
product-mapping
return-inbound
sku-calculator
...
```

长期主干应当是：

```text
main
```

而不是：

```text
data-model-restructure
```

作为长期主干。

## 目标

最终状态：

```text
main
└── 唯一长期主干

feature/*
└── 短生命周期功能分支
```

不再使用 `data-model-restructure` 作为长期开发分支。

## Phase 1：清理工作区

### 检查状态

```bash
git status
```

先整理并提交所有有效改动。

禁止在工作区不干净时进行主干整理。

## Phase 2：验证分支关系

执行：

```bash
git rev-list --left-right --count main...data-model-restructure
```

目标验证：

```text
main 是 data-model-restructure 的祖先
```

理想结果类似：

```text
0    N
```

如果不是该情况，停止操作并重新评估。

## Phase 3：让 main 追上真实主干

执行：

```bash
git checkout main
git merge --ff-only data-model-restructure
```

要求：

- 必须使用 --ff-only
- 禁止产生 Merge Commit
- 禁止改写历史

## Phase 4：推送主干

执行：

```bash
git push origin main
```

验证：

```bash
git remote show origin
```

确认：

```text
HEAD branch: main
```

## Phase 5：切换未来工作流

以后统一使用 main 开发。

推荐：

```text
main

feature/codex-monitor-xxx
feature/lkwj-xxx
feature/product-mapping-xxx
feature/aftersales-xxx
```

禁止继续长期开发在 data-model-restructure。

## Phase 6：观察期

观察 1~2 周。

确认：

- GitHub 正常
- 自动化脚本正常
- Claude Code 正常
- Codex 正常
- Worktree 正常

期间保留 data-model-restructure 作为保险分支。

## Phase 7：删除历史主干（可选）

确认稳定后：

```bash
git branch -d data-model-restructure
git push origin --delete data-model-restructure
```

## 不做的事情

本次整理不进行：

- Monorepo 拆分
- 仓库重构
- 历史 Commit 改写
- Rebase 全历史
- Squash 历史提交
- Force Push

原因：当前仓库结构健康，问题仅为长期主干名称与实际职责不一致，通过 Fast-Forward 即可解决。