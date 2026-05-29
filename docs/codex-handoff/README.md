# Codex ↔ Claude Code 协作协议

## Codex 侧（发件）

当 Codex 需要 Claude Code 审查计划、方案或代码时：

1. 将完整内容写入 `docs/codex-handoff/{project}-{action}.md`
2. 在 `inbox.json` 的 `pending` 数组追加条目：
```json
{
  "id": "{timestamp}",
  "project": "product-mapping",
  "action": "review-plan",
  "file": "docs/codex-handoff/product-mapping-review-plan.md",
  "summary": "品牌数据重构方案 — 图片迁移与目录整理",
  "from": "codex",
  "timestamp": "2026-05-29T23:00:00+08:00"
}
```
3. 告诉用户："可以让 Claude Code 查看 `docs/codex-handoff/` 里的协作请求"

## Claude Code 侧（收件）

SessionStart hook 自动检查 `inbox.json`。有未处理条目时，注入通知到会话上下文（约 50 token），Claude Code 询问用户是否要读全文。无条目时零开销。

## 条目生命周期

- `pending` → 待 Claude Code 处理
- 处理完毕 → 移到 `processed`，添加 `processedAt` 和 `processedBy` 字段
- `processed` 超过 20 条时清理旧条目

## 支持的 action 类型

| action | 含义 |
|--------|------|
| `review-plan` | 审查方案/计划 |
| `review-code` | 审查代码改动 |
| `review-design` | 审查架构设计 |
| `handoff` | 交接未完成的工作 |
| `alert` | 告警/风险提示 |
