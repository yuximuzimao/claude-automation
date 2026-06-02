# Codex Monitor 项目规则索引

## 1. 项目目标

Codex Monitor 用本地 JSONL 日志展示 Codex 与 Claude Code 的限额和 token 消耗估算。第一版优先保证数据准确、安全边界清楚、可验证，再做菜单栏、实时监听和复杂 UI。

## 2. 数据源

| 来源 | 路径 | 阶段 | 规则 |
|------|------|------|------|
| Codex sessions | `/Users/chat/.codex/sessions/` | 阶段 1 | 只读 `event_msg + payload.type == "token_count"` |
| Claude Code projects | `/Users/chat/.claude/projects/` | 阶段 2 | 只读 assistant `message.usage`，按 `message.model` 动态分桶 |
| Codex auth | `/Users/chat/.codex/auth.json` | 暂缓 | 不读取 |
| HTTP quota | `wham/usage` | 暂缓 | 不请求；继续使用本地 `payload.rate_limits` |

## 3. Codex Reader 口径

- `rate_limits` 当前真实路径是 `event["payload"]["rate_limits"]`。
- `last_token_usage` 和 `total_token_usage` 必须保留五字段：
  - `input_tokens`
  - `cached_input_tokens`
  - `output_tokens`
  - `reasoning_output_tokens`
  - `total_tokens`
- 同一 session 内增量统计使用 `last_token_usage` 求和，不对 `total_token_usage` 求和。
- 限额状态使用最新含 `payload.rate_limits` 的 token_count 事件，并保留该事件 timestamp。
- 真实 `resets_at` 可为 epoch 数字；UI 层负责格式化，不在 reader 中改写原始值。

## 4. Claude Reader 口径

- 按 `message.model` 动态分桶，不硬编码模型白名单。
- `<synthetic>` 独立保留为一个模型桶。
- `cwd` 来自记录顶层字段。
- `.claude/projects` 当前体量约 3.8GB，UI 主线程不得全量同步扫描。
- `read_claude_projects()` 支持 `modified_since` 和 `max_files`，用于 smoke check 和后续 UI 调用前的性能边界。
- `main.py --smoke-claude` 默认使用 1 天 mtime 窗口且最多读取 200 个 JSONL 文件。
- `cache_creation.ephemeral_5m_input_tokens` 和 `cache_creation.ephemeral_1h_input_tokens` 必须保留，UI 可暂不展示。
- UI watcher 触发的 Claude 刷新必须保持近 30 天视图口径，使用近 30 天 `modified_since` 和 `--claude-max-files` 上限重算；禁止因文件变化触发无边界 `.claude/projects` 扫描。
- 手动刷新可以使用 CLI 参数 `--claude-days` / `--claude-max-files` 指定的范围，但仍不得无边界扫描。

## 5. UI 方向

- 第一版采用浅色 macOS 简洁风格。
- 第一版不展示”事件类型/近 30 天用途”区块；用途分类与项目名信息重叠，优先展示更精确的项目 Top 10。
- Claude Code 数字展示时使用”结合 Claude Code 和 Codex 本地日志估算”口径。
- tkinter UI 命令：
  - `python3.13 main.py --demo` 打开假数据 UI。
  - `python3.13 main.py --ui` 打开真实本地聚合数据 UI。
  - 当前 `python3` 可能指向无 `_tkinter` 的 3.14；UI 运行需用带 Tk 的 `python3.13`。
- Top 项目名称 hover tooltip 展示 `sample_cwds` 完整路径。
- 项目名称在 UI 中显示中文描述，原始项目名和完整 cwd 只作为 tooltip/详情上下文。
- UI 必须展示 5小时限额和周限额百分比，来自 Codex 本地 `payload.rate_limits.primary/secondary`。
- 项目 Top 10 同时展示今日、近 30 天、近 30 天占比。
- `python3.13 main.py --install-app` 创建 `~/Applications/Codex Monitor.app`。
- `python3.13 main.py --install-autostart` 只写入 LaunchAgent plist 并打印 `launchctl bootstrap` 命令；禁止自动执行 `launchctl`。
- LaunchAgent 路径：`~/Library/LaunchAgents/com.local.codex-monitor.plist`。
- LaunchAgent 日志路径：`~/Library/Logs/Codex Monitor/stdout.log` 和 `~/Library/Logs/Codex Monitor/stderr.log`。
- 实时刷新优先使用 `watchdog`；不可用时使用 5 秒轮询 fallback。

## 6. 聚合层口径

- 聚合层只消费 reader 输出的结构化 usage event，不读取原始 JSONL。
- 今日/近 30 天归属按事件 `timestamp` 转为 `Asia/Shanghai` 后判断。
- Codex token 使用 `TokenUsage.total_tokens`。
- Claude token 使用 `ClaudeUsage.total_estimated_tokens`，即 `input + output + cache_creation + cache_read`。
- Top 10 项目按近 30 天 token 排序；0 token 项目不展示。
- 项目身份按三级 fallback 解析：(1) `cwd` 向上遍历，找到含 `项目中文名：` 的 `CLAUDE.md`；(2) 从 `session_path`（`.claude/projects/` 编码目录名）中解码出项目子目录名；(3) 从 session 内容前 100 行的 `/claude/{project}/` 路径模式中推断（需该项目存在 `CLAUDE.md`）。
- 未识别项目统一合并为 `其他`，token 求和后参与 Top 10 排序。
- Top 项目保留最多 3 个 `sample_cwds`，供 UI tooltip/详情展示完整路径。
- 项目中文名的维护边界在项目自身说明文件，不在监控软件内维护中心映射表。

## 7. 已知坑位

- Codex `rate_limits` 不在事件顶层；早期临时判断已被真实扫描推翻。
- 文件路径只能用于扫描优化，今日/近 30 天归属仍以事件 timestamp 为准。
- 测试 fixture 必须脱敏，只保留结构和 token 数字。
- 开机自启只生成 plist，不自动 bootstrap；写错 plist 后由用户手动启用/回滚，避免挂起登录态。
