# Codex ↔ Claude Code 协作协议

本协议**仅在 Codex App 与 Claude Code 实际协作时使用**。双方都可以发起任务、请求对方审查/补测/接手工作，也都可以接收请求；没有固定主驾驶或 Git 操作方。Git 由当前执行 Agent 在用户授权下完成，或由另一方受托完成，细则见 [`docs/git.md`](../git.md)。

单 Agent 独立执行时，不必读取或创建本协议的 handoff 文件与 inbox，也不必等待另一方。

## 发件方通用步骤（以下以 Codex 发起为例）

当 Codex 或 Claude Code 需要对方审查计划、方案或代码，或接手未完成工作时，均使用以下流程；Claude Code 发起时将示例中的 `from` 改为 `claude`：

1. 将完整内容写入合适的 markdown 文件：工作区级请求默认写入 `/Users/chat/claude/docs/codex-handoff/{project}-{action}.md`；子项目材料也可以放在 `<project>/docs/codex-handoff/`。
2. 只在工作区根目录的唯一 inbox 追加条目：`/Users/chat/claude/docs/codex-handoff/inbox.json`。不要在子项目下创建独立 `inbox.json`。
3. `file` 字段使用从 `/Users/chat/claude` 出发的相对路径：
```json
{
  "id": "{timestamp}",
  "project": "product-mapping",
  "action": "review-plan",
  "file": "docs/codex-handoff/product-mapping-review-plan.md",
  "summary": "品牌数据重构方案 — 图片迁移与目录整理",
  "from": "codex",
  "timestamp": "2026-05-29T23:00:00+08:00",
  "status": "unread"
}
```
4. 告诉用户可以让另一 Agent 查看 `docs/codex-handoff/` 里的协作请求。

## Claude Code 侧（收件）

Claude Code 环境配置了 SessionStart hook 时，可自动检查 `inbox.json`；有未处理条目时提示用户是否读取全文。该通知只服务于跨 Agent 协作，不要求独立会话读取或等待 inbox。

Claude Code 也可以作为发件方：使用相同文件格式，将 `from` 设为 `"claude"`；Codex 在接手协作任务时读取对应条目。

## 条目生命周期

- `pending` → 待收件 Agent 处理（Codex 或 Claude Code）
- 处理完毕 → 移到 `processed`，添加 `processedAt` 和 `processedBy` 字段
- 处理完毕的 `.md` 文件必须移出 active 区域，归档到 `docs/codex-handoff/archive/<date>-<topic>/`
- 归档后同步更新 `inbox.json` 里的 `file`、`responseFile` 和 `archived[].directory`；所有路径仍必须是从 `/Users/chat/claude` 出发的相对路径
- active `docs/codex-handoff/` 根目录只保留 `README.md`、`inbox.json` 和仍被 `pending` 引用的活跃请求；子项目 `docs/codex-handoff/` 也不要残留已处理材料
- `processed` 超过 20 条时清理旧条目或压缩摘要，但不能删除仍需要审计追溯的归档文件

## 支持的 action 类型

| action | 含义 |
|--------|------|
| `review-plan` | 审查方案/计划 |
| `review-code` | 审查代码改动 |
| `review-design` | 审查架构设计 |
| `handoff` | 交接未完成的工作 |
| `alert` | 告警/风险提示 |
