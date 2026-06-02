# Codex Monitor 阶段 3 复审结论

**审计方：** Claude Code  
**时间：** 2026-06-01  
**结论：** 阶段 3 通过，放行阶段 4

---

## 5 个审计项

### 1. usage event 不输出正文 ✅

`CodexUsageEvent` 和 `ClaudeUsageEvent` 只含 `timestamp`、`cwd`、`usage`（数字字段）。无任何对话文本字段。安全边界保持。

### 2. 今日/月度时间口径 ✅

`Z` 时间先转 UTC 再 `astimezone(Asia/Shanghai)`，无 timezone 的 timestamp 直接附加本地时区。今日比较用 `.date().isoformat()`，月度用 `%Y-%m`。逻辑正确，无边界问题。

### 3. Top 5 项目口径 ✅

按本月 token 排序、过滤 0 token 项目、取前 5，排序稳定（同分按项目名字典序）。适合阶段 4 UI 直接使用。

### 4. ephemeral cache 不双算 ✅

继承阶段 2 口径，`total_estimated_tokens` 仍为 `input + output + cache_creation + cache_read`，ephemeral 字段保留但不加入 total。

### 5. 阶段 4 就绪 ✅

`UsageAggregate.to_summary()` 结构完整，UI 层可直接消费。

---

## `chat` 归属问题的决定

**方案 C：UI 显示 `chat`，tooltip/详情展示完整 cwd。**

原因：
- 方案 B（反推 workspace）代价高，Codex 在 `cwd=/Users/chat` 跑是真实场景，强行猜反而出错
- 方案 A 静默显示 `chat` 用户没有上下文，体验差
- 方案 C 成本极低，聚合层不需要改，在 UI 层 tooltip 展示完整 cwd 即可

**聚合层结构已够用，不需要改。阶段 4 UI 实现时在 `chat` 行加 tooltip 显示 `/Users/chat` 即可。**

---

## 验证输出

```
10/10 tests OK (0 failures, 0 errors)
--smoke-aggregate:
  today.total_tokens: 16,472,254
  month.total_tokens: 16,472,254
  top_projects: chat(12.1M), product-detect(2.5M), claude(1.2M), codex-monitor(0.66M)
```

---

## 阶段 4 进入条件

无阻塞意见。可进入阶段 4 tkinter MVP UI：

- 窗口展示今日/本月 Codex + Claude token 总量
- Top 5 项目列表，`chat` 行 tooltip 显示完整 cwd
- 数据来源：`--smoke-aggregate` 输出结构直接复用
