# Codex Monitor 阶段 1 复审请求

**项目：** `codex-monitor`  
**动作：** `phase-review`  
**发起方：** Codex  
**时间：** 2026-05-31T23:46:29+08:00

## 范围

本次只实现 Claude Code 已放行的阶段：

- 阶段 0：项目初始化
- 阶段 1：Codex 本地 JSONL reader

未实现：

- Claude Code reader
- 聚合层
- tkinter UI
- HTTP quota
- rumps/watchdog/开机自启

## 已新增文件

项目目录：`/Users/chat/claude/codex-monitor/`

关键文件：

- `CLAUDE.md`：Session 启动规则、安全边界、目录说明
- `SKILL.md`：项目专用上下文和硬规则
- `docs/INDEX.md`：数据源、Codex reader 口径、Claude reader 后续约束
- `tasks/todo.md`：阶段 0/1 状态与暂缓项
- `app/models.py`：共享数据模型
- `app/reader_codex.py`：Codex JSONL reader
- `main.py`：`--smoke-codex` 结构摘要入口
- `tests/test_reader_codex.py`：阶段 1 单元测试
- `tests/fixtures/codex_session.jsonl`：脱敏 fixture，只含结构和 token 数字

## 实现要点

### Codex reader

- 只读取 `event_msg + payload.type == "token_count"`。
- `rate_limits` 从 `event["payload"]["rate_limits"]` 读取。
- `last_token_usage` 用于同 session 增量求和。
- `total_token_usage` 只保存最新累计值，不参与求和。
- 保留五个 Codex token 字段：
  - `input_tokens`
  - `cached_input_tokens`
  - `output_tokens`
  - `reasoning_output_tokens`
  - `total_tokens`
- 坏 JSON 行只计入 `parse_errors`，不输出整行内容。
- 真实日志中 `resets_at` 为 epoch 数字，模型已允许 `str | int | float | None`，UI 后续负责格式化。

### Smoke check

`python3 main.py --smoke-codex` 只输出结构摘要：

- session 数
- token_count 事件数
- parse_errors
- token 五字段汇总
- latest_quota 的 primary/secondary 摘要

不会输出对话正文。

## 验证结果

在 `/Users/chat/claude/codex-monitor` 执行：

```bash
python3 -m unittest discover -s tests -v
```

结果：

- 4 个测试通过
- 0 failure
- 0 error

执行：

```bash
python3 main.py --smoke-codex
```

结果：

- 读取真实 Codex sessions
- `session_count: 24`
- `token_count_events: 591`
- `parse_errors: 0`
- 输出为结构摘要，无对话正文

执行：

```bash
python3 -m compileall app tests
```

结果：

- 退出码 0
- `app` 和 `tests` 编译通过

## 请 Claude Code 复审

请重点审计：

1. `reader_codex.py` 是否严格使用 `payload.rate_limits`，没有回退到错误顶层路径。
2. `TokenUsage` 五字段是否完整保留。
3. `last_token_usage` 求和与 `total_token_usage` 保存最新值的口径是否合理。
4. `--smoke-codex` 是否满足“结构摘要、禁止对话正文”的要求。
5. 阶段 0 文档是否足够约束后续阶段 2，尤其是 `.claude/projects` 3.8GB 扫描性能边界。

若无阻塞意见，再进入阶段 2：Claude Code reader。
