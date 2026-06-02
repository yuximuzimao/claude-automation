# Codex Monitor 阶段 2 复审请求

**项目：** `codex-monitor`  
**动作：** `phase-review`  
**发起方：** Codex  
**时间：** 2026-05-31T23:56:10+08:00

## 范围

本次只实现阶段 2：Claude Code 本地 JSONL reader。

未实现：

- 聚合层
- tkinter UI
- HTTP quota
- rumps/watchdog/开机自启

## 已新增或修改文件

关键文件：

- `app/reader_claude.py`：Claude Code JSONL reader
- `app/models.py`：新增 `ClaudeUsage`、`ClaudeSessionResult`、`ClaudeScanResult`
- `main.py`：新增 `--smoke-claude`
- `tests/test_reader_claude.py`：阶段 2 单元测试
- `tests/fixtures/claude_session.jsonl`：脱敏 fixture，只含结构和 token 数字
- `docs/INDEX.md`：补充 Claude reader 口径和性能边界
- `tasks/todo.md`：阶段 2 状态
- `README.md`：补充 smoke check 命令

## 实现要点

### Claude reader

- 只读取 `type == "assistant"` 且存在 `message.usage` 的记录。
- `cwd` 从记录顶层字段读取。
- `model` 从 `message.model` 读取，不硬编码模型白名单。
- 缺失 model 时归入 `<missing>`。
- `<synthetic>` 保留为独立模型桶。
- 递归扫描 `**/*.jsonl`，自然覆盖 `<session-uuid>/subagents/*.jsonl`。
- 坏 JSON 行只计入 `parse_errors`，不输出整行内容。

### Token 口径

`ClaudeUsage` 保留：

- `input_tokens`
- `output_tokens`
- `cache_creation_input_tokens`
- `cache_read_input_tokens`
- `cache_creation_ephemeral_5m_input_tokens`
- `cache_creation_ephemeral_1h_input_tokens`

`total_estimated_tokens` 当前为：

```text
input_tokens + output_tokens + cache_creation_input_tokens + cache_read_input_tokens
```

ephemeral 字段保留为拆分信息，不重复计入 total，避免和 `cache_creation_input_tokens` 双算。

### 性能边界

`read_claude_projects()` 支持：

- `modified_since`
- `max_files`

`python3 main.py --smoke-claude` 默认：

- 只读取最近 1 天 mtime 的 JSONL
- 最多读取 200 个文件

这样避免 smoke check 或后续 UI 路径直接同步扫描 `.claude/projects` 全量历史。

## 验证结果

在 `/Users/chat/claude/codex-monitor` 执行：

```bash
python3 -m unittest discover -s tests -v
```

结果：

- 8 个测试通过
- 0 failure
- 0 error

执行：

```bash
python3 main.py --smoke-claude
```

结果：

- `file_count: 28`
- `assistant_events: 540`
- `parse_errors: 0`
- 按动态模型分桶输出结构摘要
- 无对话正文输出

执行：

```bash
python3 main.py --smoke-codex
```

结果：

- `session_count: 24`
- `token_count_events: 627`
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

1. `reader_claude.py` 是否满足“只读 assistant usage、不输出正文”的边界。
2. model 分桶是否足够开放，是否正确保留 `<synthetic>` 和 `<missing>`。
3. `cache_creation.ephemeral_*` 的保留和不重复计入 total 是否符合预期。
4. `modified_since` / `max_files` 是否足够作为阶段 2 的性能边界。
5. 阶段 3 是否可以进入聚合层：合并 Codex 和 Claude 的今日/月度统计、Top 5 项目。

若无阻塞意见，再进入阶段 3：聚合层。
