# Codex Monitor 阶段 2 复审结论

**审计方：** Claude Code  
**时间：** 2026-06-01  
**结论：** 阶段 2 通过，放行阶段 3

---

## 5 个审计项

### 1. reader_claude.py 边界 ✅

只处理 `type == "assistant"` 且 `message.usage` 存在的行，其他类型（user、system、tool）完全跳过。坏 JSON 只计入 `parse_errors`，不输出行内容。边界严格，无泄漏风险。

### 2. 模型分桶 ✅

动态读取 `message.model`，无硬编码白名单。`<missing>` 覆盖 model 字段为空/None 的情况。`<synthetic>` 是实际 model 字符串，自然落入正常分桶，无需特殊处理——测试 fixture 和 smoke check 输出均已验证。

### 3. ephemeral cache 不重复计入 total ✅

`total_estimated_tokens` = `input_tokens + output_tokens + cache_creation_input_tokens + cache_read_input_tokens`。`cache_creation_ephemeral_5m/1h` 作为拆分字段保留在 `to_summary()` 中，不加入 total。逻辑正确，无双算。

### 4. 性能边界 ✅（附一个小备注）

`modified_since` + `max_files` 组合足够作为阶段 2 边界。smoke check 默认 1 天 + 200 文件，实测 `file_count: 30`，远低于上限，无性能风险。

**小备注**（非阻塞）：`_iter_claude_files` 按路径字典序排序后取前 N 个文件，如果未来文件数接近 200，可能因路径排序而非时间排序导致截断不一致。阶段 3 建议在聚合层的增量索引路径上，改为按 mtime 排序后截断，smoke check 路径不需要改。

### 5. 阶段 3 就绪 ✅

`ClaudeScanResult.by_model` + `ClaudeScanResult.total_usage` 与 `CodexScanResult.last_usage_total` 结构对称，都有 `plus()` 方法支持合并。聚合层实现直接，无障碍。

---

## 验证输出

```
8/8 tests OK (0 failures, 0 errors)
--smoke-claude: file_count=30, assistant_events=583, parse_errors=0
models: <synthetic>, claude-haiku-4-5, claude-opus-4-6, claude-sonnet-4-6, deepseek-v4-flash, deepseek-v4-pro
```

---

## 阶段 3 进入条件

无阻塞意见。可进入阶段 3：

- 聚合层：合并 Codex + Claude 今日/月度 token 统计
- Top 5 项目：按 `cwd` 归组，取用量最高的 5 个
- 输出结构对齐阶段 4 UI 所需

对 `max_files` 排序问题的处理时机由 Codex 判断，建议放在聚合层增量索引设计时一并解决，不需要阻塞阶段 3。
