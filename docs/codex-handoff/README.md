# Codex ↔ Claude Code 协作协议

## Codex 侧（发件）

当 Codex 需要 Claude Code 审查计划、方案或代码时：

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
4. 告诉用户："可以让 Claude Code 查看 `docs/codex-handoff/` 里的协作请求"

## Claude Code 侧（收件）

SessionStart hook 自动检查 `inbox.json`。有未处理条目时，注入通知到会话上下文（约 50 token），Claude Code 询问用户是否要读全文。无条目时零开销。

## 条目生命周期

- `pending` → 待 Claude Code 处理
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
