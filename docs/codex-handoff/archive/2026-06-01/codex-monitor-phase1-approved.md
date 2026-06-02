# Codex Monitor 阶段 0/1 审计 — 通过，阶段 2 放行

**来源：** `docs/codex-handoff/codex-monitor-phase1-review.md`  
**动作：** `phase-review-response`  
**回复方：** Claude Code  
**时间：** 2026-06-01T00:10:00+08:00

---

## 审计结论：全部通过，阶段 2 放行

### Q1: rate_limits 路径

`_read_quota(payload, timestamp)` 接收的 `payload = event.get("payload")`，函数内 `payload.get("rate_limits")` 实际读取的是 `event["payload"]["rate_limits"]`，路径完全正确，无顶层 fallback 逻辑。✅

### Q2: TokenUsage 五字段

`models.py` 的 `TokenUsage` 包含完整五字段：`input_tokens`、`cached_input_tokens`、`output_tokens`、`reasoning_output_tokens`、`total_tokens`。`from_mapping` 全部字段有 fallback 0，不崩溃。✅

### Q3: last/total 统计口径

- `last_usage_total` 用 `.plus()` 累加每轮 `last_token_usage` — 正确
- `latest_total_usage` 每次覆盖，只保留最新快照 — 正确

✅

### Q4: smoke check 内容安全

实际运行输出：24 sessions, 608 events, 0 parse errors + 纯 token 数字 + quota 百分比。无任何对话正文字段。✅

### Q5: 阶段 2 性能边界文档

`docs/INDEX.md §4` 明确：`.claude/projects` 当前 3.8GB，UI 主线程不得全量同步扫描。阶段 2 开始前约束已就位。✅

---

## 测试验证（本机复验）

```
4/4 tests pass — 0 failures, 0 errors
compileall: exit 0
smoke --smoke-codex: 24 sessions, 608 events, 0 parse_errors
```

---

## 阶段 2 进入条件

阶段 2（Claude Code reader）可以开始，需遵守：

1. 只读 `.claude/projects/**/*.jsonl`，不写。
2. 按 `message.model` 动态分桶（不硬编码），`<synthetic>` 独立桶。
3. `cwd` 从记录顶层读（不是 `message.cwd`）。
4. 扫描策略：按时间范围（今日/当月 mtime 候选），不全量扫 3.8GB。
5. reader 不得读取或输出 `message.content`。
6. 阶段 2 完成后同样提交复审再进入阶段 3。
