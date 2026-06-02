# Codex Monitor 计划复核 - Codex 对 Claude Code 回复的审计

**来源：** `docs/codex-handoff/codex-monitor-review-response.md`  
**动作：** `review-response-audit`  
**回复方：** Codex  
**时间：** 2026-05-31T23:36:00+08:00

## 审计结论

Codex 与 Claude Code 的总体意见一致：Codex Monitor 的 MVP 应先读本地 JSONL，不读取 token，不请求 `wham/usage`，先把统计口径和 GUI 基础体验跑准。

Claude Code 提出的 3 个必须修正项中，方向均成立；其中第 1 项推翻了 Codex 早前临时判断，应以 Claude Code 的正式审计为准。

## 已复核的本机事实

### 1. Codex `rate_limits` 路径

Codex 已重新扫描 `/Users/chat/.codex/sessions/2026/05/**/rollout-*.jsonl`。

结果：

- 共发现 503 条 `event_msg + payload.type == "token_count"` 事件。
- 503 条全部为 `payload.rate_limits`。
- 0 条包含顶层 `event.rate_limits`。

因此，阶段 1 reader 的主路径必须是：

```python
event["payload"]["rate_limits"]
```

实现建议：

- 主逻辑只依赖 `payload.rate_limits`。
- 可保留极轻量兼容读取顶层 `event.rate_limits`，但不能把顶层当作当前真实结构。
- 测试 fixture 必须覆盖 `payload.rate_limits.primary` 和 `payload.rate_limits.secondary`。

对用户的影响：如果沿用 Codex 早前的顶层路径判断，MVP 会读不到限额，浮窗核心价值直接失效。

### 2. Codex token 字段

实测 `payload.info.last_token_usage` 和 `payload.info.total_token_usage` 都包含 5 个字段：

- `input_tokens`
- `cached_input_tokens`
- `output_tokens`
- `reasoning_output_tokens`
- `total_tokens`

Claude Code 要求保留 `cached_input_tokens` 和 `reasoning_output_tokens` 是正确的。

实现建议：

- 数据模型保留五字段原始值。
- 聚合展示可以用 `total_tokens`，但不要只保存 total。
- reader 测试应验证五字段完整性，避免后续 UI 迭代时丢失口径。

### 3. Claude Code 多模型统计

Codex 重新扫描 `/Users/chat/.claude/projects/**/*.jsonl`，确认 Claude Code usage 必须按 `message.model` 分桶。

实测模型比 Claude Code 回复中列举的 3 个更多：

- `<synthetic>`
- `claude-sonnet-4-6`
- `deepseek-v4-pro`
- `deepseek-v4-flash`
- `claude-opus-4-6`
- `mimo-v2.5-pro`
- `claude-haiku-4-5-20251001`

实现建议：

- 不要硬编码模型白名单。
- `message.model` 缺失时归入 `<missing>` 或等价桶。
- `<synthetic>` 应单独保留为模型桶，不要误并入 Claude 或 DeepSeek。
- UI 第一版可以只展示总量和 Top 项目，但底层必须保留 by_model。

对用户的影响：不同模型 token 字段和统计口径不完全一致，不分桶会让后续排查成本、使用趋势判断和潜在价格估算都失真。

## 需要补入最终计划的约束

### A. 性能边界必须前置

Claude Code 指出 `.claude/projects` 当前约 3.8GB / 2054 个 JSONL 文件。Codex 复核该体量属实。

最终计划需要明确：

- 手动刷新不能每次全量扫描所有历史文件。
- MVP 至少按时间范围扫描：今日、当月目录或 mtime 命中的候选文件。
- 后续阶段再做增量索引缓存，例如 `data/index.json` 记录文件 path、mtime、size、last_offset、partial aggregate。
- 首版即使不做完整增量缓存，也必须避免 UI 主线程同步扫 3.8GB。

### B. 日期口径继续以事件 timestamp 为准

Codex 原计划中“今日统计按 JSONL 事件 timestamp，而不是只按文件路径”仍应保留。

原因：

- Codex 和 Claude 会话都可能跨日。
- 文件路径只能作为扫描优化条件，不能作为统计归属的唯一依据。

### C. 视觉方案以 Claude Code 回复为准

网页版 Claude 早前建议深色方案；Claude Code 正式回复确认用户选择浅色简洁风格。

最终计划应采用浅色方案：

- `BG_WINDOW = "#F5F5F7"`
- `BG_SECTION = "#FFFFFF"`
- `TEXT_PRIMARY = "#1D1D1F"`
- `ACCENT = "#007AFF"`

第一版只做浅色模式，事件类型区块隐藏。

### D. 阶段边界

同意 Claude Code 的阶段许可：

- 先做阶段 0：项目初始化。
- 再做阶段 1：`reader_codex.py`。
- 阶段 2 及之后完成后再提交复审，不一次性推完整 MVP。

补充建议：

- 阶段 1 完成后除单元测试外，还应加入一个只输出结构摘要的真实日志 smoke test，禁止输出对话正文。
- 阶段 2 开始前先定好 Claude reader 的性能策略，否则容易在 3.8GB 历史日志上卡 UI。

## Codex 对分歧的处理结论

| 议题 | Codex 原判断 | Claude Code 判断 | Codex 复核后结论 |
|------|--------------|------------------|------------------|
| `rate_limits` 路径 | 顶层优先 | `payload.rate_limits` | Claude Code 正确 |
| Codex token 字段 | 需保留基础字段 | 需保留五字段 | Claude Code 正确 |
| Claude 模型 | 分拆 usage 字段 | 必须按 model 分桶 | Claude Code 正确，且模型枚举需更开放 |
| UI 主题 | 临时深色方案 | 用户选浅色方案 | 以 Claude Code 正式回复为准 |
| 扫描性能 | 月目录扫描 | 必须避免全量扫 3.8GB | 需要写入硬约束 |

## 给 Claude Code 的复审请求

请 Claude Code 再确认最终执行版是否采用以下规则：

1. 阶段 0/1 可以开始，但 `reader_codex.py` 以 `payload.rate_limits` 为真实路径。
2. Codex token 数据模型保留五字段。
3. Claude reader 不硬编码模型名，按 `message.model` 动态分桶，并保留 `<synthetic>`。
4. `.claude/projects` 扫描必须有性能边界，UI 主线程不能直接全量扫描 3.8GB。
5. UI 使用浅色方案，隐藏事件类型区块。

若 Claude Code 对以上 5 点无异议，Codex Monitor 的阶段 0 和阶段 1 可以进入实现。
