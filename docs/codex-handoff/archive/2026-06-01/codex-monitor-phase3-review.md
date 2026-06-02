# Codex Monitor 阶段 3 复审请求

**项目：** `codex-monitor`  
**动作：** `phase-review`  
**发起方：** Codex  
**时间：** 2026-06-01T00:35:26+08:00

## 范围

本次只实现阶段 3：聚合层。

未实现：

- tkinter UI
- HTTP quota
- rumps/watchdog/开机自启
- 增量索引缓存

## 已新增或修改文件

关键文件：

- `app/aggregate.py`：聚合层
- `app/models.py`：新增 `CodexUsageEvent`、`ClaudeUsageEvent`
- `app/reader_codex.py`：为 token_count 事件输出结构化 usage event
- `app/reader_claude.py`：为 assistant usage 输出结构化 usage event
- `main.py`：新增 `--smoke-aggregate`
- `tests/test_aggregate.py`：阶段 3 单元测试
- `docs/INDEX.md`：补充聚合口径
- `tasks/todo.md`：阶段 3 状态
- `README.md`：补充聚合 smoke 命令

## 实现要点

### Usage event

reader 继续只读 token/usage 结构，不输出对话正文。

新增结构化事件：

- `CodexUsageEvent(timestamp, cwd, usage)`
- `ClaudeUsageEvent(timestamp, cwd, model, usage)`

这样聚合层可以基于事件 timestamp 做今日/月度归属，不再用文件路径猜日期。

### 聚合口径

`aggregate_usage(codex, claude, now=..., timezone="Asia/Shanghai")` 输出：

- `today`
  - `codex_tokens`
  - `claude_tokens`
  - `total_tokens`
- `month`
  - `codex_tokens`
  - `claude_tokens`
  - `total_tokens`
- `top_projects`
  - 本月 token 排序
  - 项目名取 `cwd` 最后一级
  - 0 token 项目过滤
- `last_updated`

Codex 使用 `TokenUsage.total_tokens`。

Claude 使用 `ClaudeUsage.total_estimated_tokens`：

```text
input_tokens + output_tokens + cache_creation_input_tokens + cache_read_input_tokens
```

### 时间口径

- 默认按 `Asia/Shanghai` 计算今日和本月。
- ISO `Z` 时间会先解析为 UTC，再转为本地时区。
- 无 timezone 的 timestamp 按本地时区处理。

## 验证结果

在 `/Users/chat/claude/codex-monitor` 执行：

```bash
python3 -m unittest discover -s tests -v
```

结果：

- 10 个测试通过
- 0 failure
- 0 error

执行：

```bash
python3 main.py --smoke-aggregate
```

结果：

- 输出今日、本月、Top 项目结构摘要
- 无对话正文输出
- 示例结果包含：
  - `today.total_tokens: 7913956`
  - `month.total_tokens: 7913956`
  - Top 项目：`chat`、`claude`、`codex-monitor`

执行：

```bash
python3 main.py --smoke-claude
```

结果：

- `file_count: 30`
- `assistant_events: 587`
- `parse_errors: 0`

执行：

```bash
python3 main.py --smoke-codex
```

结果：

- `session_count: 24`
- `token_count_events: 698`
- `parse_errors: 0`

执行：

```bash
python3 -m compileall app tests
```

结果：

- 退出码 0
- `app` 和 `tests` 编译通过

## 请 Claude Code 复审

请重点审计：

1. usage event 扩展是否仍满足“不输出正文”的安全边界。
2. 今日/月度按事件 timestamp + Asia/Shanghai 归属是否符合预期。
3. Top 5 项目按本月 token 排序、过滤 0 token 项目是否适合阶段 4 UI。
4. `ClaudeUsage.total_estimated_tokens` 是否继续保持不双算 ephemeral cache。
5. 阶段 4 是否可以进入 tkinter MVP UI。

## 需要 Claude 判断的非阻塞问题

当前真实 Codex smoke 中，部分 Codex session 的 `cwd` 是 `/Users/chat`，所以 Top 项目会显示 `chat`。这符合“项目名取 cwd 最后一级”的当前规则，但对用户体验不一定足够精确。

建议 Claude 审计阶段 4 前是否需要增加项目归属增强：

- 方案 A：保持现状，UI 第一版显示 `chat`，后续再优化。
- 方案 B：对 Codex session 结合 session 文件路径或最近工作区上下文做更细归属。
- 方案 C：阶段 4 UI 显示 `chat`，但 tooltip/详情保留完整 cwd。

Codex 暂不自行扩大范围，等待复审意见。

若无阻塞意见，再进入阶段 4：tkinter MVP UI。
