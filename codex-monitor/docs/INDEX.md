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
- 限额状态使用最新可显示 `used_percent` 的 `payload.rate_limits`；如果较新的 `rate_limits` 缺少 `primary/secondary.used_percent`，不得覆盖上一条可显示 quota。
- `used_percent` 在模型层只接受有限数值；字符串数字可转为 `float`，空值、非数值、`NaN`、`inf` 统一视为未知 `None`。
- 真实 `resets_at` 可为 epoch 数字；UI 层负责格式化，不在 reader 中改写原始值。

## 4. Claude Reader 口径

- 按 `message.model` 动态分桶，不硬编码模型白名单。
- `<synthetic>` 独立保留为一个模型桶。
- `cwd` 来自记录顶层字段。
- `.claude/projects` 当前体量约 3.9GB，UI 主线程不得全量同步扫描。
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
- `.app` launcher 使用 `--ui --visible-app`，启动前若 `com.local.codex-monitor` LaunchAgent 正在运行，会先 `bootout` 让可见 App 获取单实例锁；可见 App 退出后只在启动前后台服务确实运行时恢复 LaunchAgent。
- `.app` launcher 必须使用带 `_tkinter` 的绝对 Python 路径；本机默认优先 `/Users/chat/miniconda3/bin/python3.13`。不要依赖 GUI 环境里的 `PATH`。
- 可见 App 模式会尽力通过 AppKit 设置 `Codex Monitor` 名称和 `CodexMonitor.icns`，但当前仍是 Python/Tk wrapper，不保证所有 macOS 状态下都不会显示 Python/Python3。
- `python3.13 main.py --install-autostart` 只写入 LaunchAgent plist 并打印 `launchctl bootstrap` 命令；禁止自动执行 `launchctl`。
- LaunchAgent 路径：`~/Library/LaunchAgents/com.local.codex-monitor.plist`。
- LaunchAgent 日志路径：`~/Library/Logs/Codex Monitor/stdout.log` 和 `~/Library/Logs/Codex Monitor/stderr.log`。
- 实时刷新优先使用 `watchdog`；不可用时使用 5 秒轮询 fallback。
- 文件变化检测、聚合读取和 JSONL 解析不得在 tkinter 主线程执行；主线程只负责旧数据展示、交互和应用后台结果。
- 自动刷新必须 debounce，并设置 60 秒最小间隔；文件持续写入时宁可数据延迟，也不能连续占满 CPU 或阻塞 UI。
- 刷新中再次触发自动刷新时只合并为下一次请求，不并发堆叠多个 reader/aggregate worker。
- 折叠态倒计时文本必须使用 Canvas text item，并由 `itemconfigure(text=...)` 更新；不要在胶囊 Canvas 中嵌入 `tk.Label`，否则点击/hover 后 macOS/Tk 可能短暂绘制灰色 Label 背景。
- UI 入口必须持有 `SingleInstance` 文件锁。后台 LaunchAgent 获取锁失败应立即退出；可见 App 可短暂等待锁释放，避免刚切换后台实例时静默打不开。

## 6. 聚合层口径

- 聚合层只消费 reader 输出的结构化 usage event，不读取原始 JSONL。
- 今日/近 30 天归属按事件 `timestamp` 转为 `Asia/Shanghai` 后判断。
- Codex token 使用 `TokenUsage.total_tokens`。
- Claude token 使用 `ClaudeUsage.total_estimated_tokens`，即 `input + output + cache_creation + cache_read`。
- Top 10 项目按近 30 天 token 排序；0 token 项目不展示。
- 项目身份按三级 fallback 解析：(1) `cwd` 向上遍历，找到含 `项目中文名：` 的 `CLAUDE.md`；(2) 从 `session_path`（`.claude/projects/` 编码目录名）中解码出项目子目录名；(3) 从 session 内容前 200 行的 `/claude/{project}/` 路径模式中推断（需该项目存在 `CLAUDE.md`）。第 3 层按事件类型加权（`app/reader_common.py::infer_project_from_handle`）：Codex `user_message` 和 Claude `user` 事件 5x，普通 `message`/`session_meta`/`reasoning` 等 1x，`function_call_output` / `function_call` / `token_count` 不参与投票（weight=0）。若最高票项目打平，必须返回未知并归入 `其他`，不能按插入顺序任意选择项目。
- 未识别项目统一合并为 `其他`，token 求和后参与 Top 10 排序。
- Top 项目保留最多 3 个 `sample_cwds`，供 UI tooltip/详情展示完整路径。
- 项目中文名的维护边界在项目自身说明文件，不在监控软件内维护中心映射表。

## 7. 已知坑位

- Codex `rate_limits` 不在事件顶层；早期临时判断已被真实扫描推翻。
- Codex 在 5 小时限额耗尽或临时无法返回完整 quota 时，可能写出较新的空 `rate_limits` 或缺少 `used_percent` 的窗口。未知值不能伪装成真实 `0%`：reader 必须跳过不可显示 quota，折叠态 UI 中心文本用 `—` 表示未知，只有真实 `0.0` 才显示 `0%`。回归测试覆盖 `tests/test_reader_codex.py`、`tests/test_models.py`、`tests/test_ui_tk.py`。
- 文件路径只能用于扫描优化，今日/近 30 天归属仍以事件 timestamp 为准。
- Codex `function_call_output` 常包含目录列表，一条记录可能有 50+ 条无关 `/claude/{project}` 路径，若参与投票会完全淹没真实信号（已验证：单条 `function_call_output` 59票 vs `message` 4票）。修复方案见 `app/reader_common.py`：事件类型加权 + 扫描窗口 200 行。回归测试在 `tests/test_reader_common.py`。
- 多项目摘要型 Codex 会话可能在普通 `message` / `agent_message` / `task_complete` 中弱引用多个项目。若弱信号打平，不能把今日用量挂到先出现的项目（例如误挂到 `product-detect`）；应返回 `None` 并让聚合归入 `其他`。回归测试：`tests/test_reader_common.py::test_tied_weak_project_signals_return_none`。
- 代码修改后必须重启 app 进程才能生效（`python3.13 main.py --ui` 是长驻进程，不热重载）。
- `.app` 与 LaunchAgent 共享单实例锁。调试“双击没打开”时先查 `~/Library/Application Support/Codex Monitor/codex-monitor.lock` 中的 PID，再用 `ps -p <pid>` 判断是否仍有旧 UI 进程占锁。
- tkinter `create_arc` 的 `extent` 取到 ±360 时整段弧渲染为空白。配额圆环 100% 时 `extent = -100 × 3.6 = -360`，会让满载圆环显示为空（看起来"归零"）。灰色轨道一直用 `-359.99` 规避，但进度弧早期漏了。修复：`app/ui_tk.py::_ring_extent()` 统一把进度弧 clamp 到 `-359.99`，并抽成纯函数以便脱离 tkinter 单测。回归测试 `tests/test_ui_tk.py::test_ring_extent_*`。新增任何 `create_arc` 都不得让 extent 触到 ±360。
- `watchdog` 不是标准库；未安装时会走 polling fallback。polling 只能做轻量 mtime 检测，不能直接触发主线程聚合或高频后台聚合。
- 测试 fixture 必须脱敏，只保留结构和 token 数字。
- 开机自启只生成 plist，不自动 bootstrap；写错 plist 后由用户手动启用/回滚，避免挂起登录态。
