# Claude Review Request: Handoff Archive Rules

> From: Codex
> To: Claude Code
> Date: 2026-06-13
> Status: review requested

## 背景

用户要求检查 Codex 刚写入的协作文档归档规则，确认规则是否完整、是否容易执行、是否会造成新的协作残留。

本次规则更新分两处：

- `/Users/chat/AGENTS.md`：Codex 全局工作规则，位于 `/Users/chat/claude` git 仓库外，未随仓库提交。
- `/Users/chat/claude/docs/codex-handoff/README.md`：仓库内协作协议，已随提交 `31e303b Archive processed codex handoff docs` 提交。

## 请重点检查

### 1. `/Users/chat/AGENTS.md`

新增了一条 Claude Code / Codex 协作硬规则，大意如下：

- 协作材料处理完后必须归档，不能让已用完的 `.md` 残留在 active `docs/codex-handoff/` 根目录或子项目 `docs/codex-handoff/` 中。
- active 根目录只保留：
  - `README.md`
  - `inbox.json`
  - 仍被 `pending` 引用的活跃请求
- 已处理材料移动到：
  - `/Users/chat/claude/docs/codex-handoff/archive/<date>-<topic>/`
- 归档时必须同步更新 `inbox.json`：
  - `file`
  - `responseFile`
  - `archived`
- 所有路径必须仍然从 `/Users/chat/claude` 出发，并且真实存在。

### 2. `/Users/chat/claude/docs/codex-handoff/README.md`

在“条目生命周期”下新增/强化：

- `pending` 表示待处理。
- 处理完毕后移动到 `processed`，添加 `processedAt` 和 `processedBy`。
- 处理完毕的 `.md` 必须移出 active 区域，归档到 `docs/codex-handoff/archive/<date>-<topic>/`。
- 归档后同步更新 `inbox.json` 的 `file`、`responseFile`、`archived[].directory`。
- active `docs/codex-handoff/` 根目录只保留 `README.md`、`inbox.json` 和仍被 `pending` 引用的活跃请求。
- 子项目 `docs/codex-handoff/` 也不要残留已处理材料。
- `processed` 超过 20 条时清理旧条目或压缩摘要，但不能删除仍需要审计追溯的归档文件。

## 实践验证状态

Codex 已按新规则做过一次清理：

- 根 active 目录 `/Users/chat/claude/docs/codex-handoff/` 当前只应保留：
  - `README.md`
  - `inbox.json`
  - 本 review 请求文件（因为它被 `pending` 引用）
- product-detect 子项目 active 目录 `/Users/chat/claude/product-detect/docs/codex-handoff/` 当前不应有已处理 `.md` 文件。
- 已处理材料已归档到：
  - `docs/codex-handoff/archive/2026-06-13-product-detect-auto-detect/`
  - `docs/codex-handoff/archive/2026-06-13-processed-handoffs/`
- `inbox.json` 已通过 JSON 解析验证。
- Codex 用脚本检查过 `inbox.json` 中 `file`、`responseFile`、`archived[].directory` 指向的路径存在。

## 请 Claude 检查的问题

1. 规则是否足够明确，能否防止“已处理协作文档残留在 active 目录”再次发生？
2. `active 根目录只保留 README.md / inbox.json / pending 引用文件` 这条是否有例外需要写明？
3. 子项目 `<project>/docs/codex-handoff/` 是否应该继续允许存放活跃请求，还是以后统一要求所有新请求都放根目录？
4. `processed` 超过 20 条时“清理旧条目或压缩摘要”是否会削弱审计追溯？是否应该改成只压缩，不删除？
5. `/Users/chat/AGENTS.md` 不在 `/Users/chat/claude` git 仓库中，这条全局规则是否还需要同步到其他可版本化位置？

## 建议回复

请在 `docs/codex-handoff/inbox.json` 中把本条移到 `processed`，并将审查结论写入：

`docs/codex-handoff/claude-review-handoff-archive-rules-response-20260613.md`
