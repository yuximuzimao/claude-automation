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
- 项目归属按 `user_message` 分轮，不再给整段 session 强行套一个项目。一个从 `/Users/chat` 启动的长会话可以按实际操作分到多个项目；同一轮中先产生、后确认项目的 token 在轮次结束时回填。
- 归属证据优先使用正式项目 `cwd`、用户明确给出的正式项目路径和工具调用的真实 `workdir`。工具输出、普通助手示例文字和不存在 `CLAUDE.md` 的占位目录不作为 Codex 轮次归属依据。
- 新版 `exec` 可能把真实调用包在 `custom_tool_call.input` 中。只对 `exec`、`exec_command`、`apply_patch`、`view_image` 等本地文件操作读取已验证的正式项目路径；`update_plan`、代理调度、等待等协调工具不提供项目证据。实际 `workdir` 权重始终高于普通工具参数路径。
- 项目迁移后可在新项目自身的 `CLAUDE.md` 声明 `项目历史路径：/绝对/旧路径`。reader 动态读取该元数据，把旧日志归到当前项目；禁止在监控代码中维护个人项目硬编码映射。冲突声明不得启用。
- Superpowers/CodexPro 历史工作树形如 `.../worktrees/claude/<临时任务>/<正式项目>/...`。reader 可从日志建立唯一的临时名到正式项目映射；映射冲突或正式项目元数据不存在时不得猜测。
- 子代理在自身没有更强证据时，继承父会话在启动时刻已确认的项目；自身明确的正式项目 `workdir` 可以覆盖继承值。
- 明确的 `/neat`、`/sync`、`整理一下`、`收尾` 等收尾轮次可作为单项目会话总结：只纠正未知或单纯沿用的弱归属。若会话已经确认过多个项目，不得用最后一次 neat 覆盖已有分段。
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
- Claude Code 可能在同一 JSONL 中重复写入同一个 assistant `message.id` 和相同 `message.usage`；有 `message.id` 时必须按 id 去重后再累计 token。缺少 id 的旧格式保持逐条统计。
- Claude 的 `Bash`、`Read`、`Edit`、`Write`、`Glob`、`Grep` 等本地文件工具输入若只出现一个已验证项目路径，可作为该 assistant usage event 的直接证据；tool result、Skill/Agent 调度和多项目输入不参与。
- Claude 会话若通过真实事件 `cwd` 只确认一个项目，只回填首次与末次确认事件之间、且 `cwd` 仍是 `/Users/chat` 或 `/Users/chat/claude` 的根目录事件。确认区间外和确认过多个项目的会话保持原归属，避免把工作区讨论整段强塞给最后一个项目。
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
- 当前材质实现是 Tkinter 前景 + 独立 AppKit `NSVisualEffectView` backing window，两条渲染链路无法完全复现原生 vibrancy、字体合成和动态材质。现阶段保持当前稳定实现；只有触发长期迁移条件时才按 `docs/FUTURE.md` 评估 `NSPanel + SwiftUI/AppKit` 原生前端，不把该方向当作当前待办。

## 6. 聚合层口径

- 聚合层只消费 reader 输出的结构化 usage event，不读取原始 JSONL。
- 今日/近 30 天归属按事件 `timestamp` 转为 `Asia/Shanghai` 后判断。`--ui` 首次启动、手动刷新、watcher 刷新和 `--smoke-aggregate` 必须全部显式传入同一个滚动 30 天起点；不得让首次启动省略 `month_start` 而退回自然月口径。
- Codex token 使用 `TokenUsage.total_tokens`。
- Claude token 使用 `ClaudeUsage.total_estimated_tokens`，即 `input + output + cache_creation + cache_read`。
- Top 10 项目按近 30 天 token 排序；0 token 项目不展示。
- Codex reader 已按轮次产出 `inferred_project`，聚合层依次使用事件 `cwd` 和该轮推断值。Claude 项目身份继续按三级 fallback 解析：(1) `cwd` 向上遍历，找到含 `项目中文名：` 的 `CLAUDE.md`；(2) 从 `session_path`（`.claude/projects/` 编码目录名）中解码项目；(3) 从人类文本中的 `/claude/{project}/` 路径做有界加权推断。Claude tool result、hook、attachment 和共享目录不参与投票；打平时归入 `其他`。
- 未识别项目统一合并为 `其他`，token 求和后参与 Top 10 排序。
- Top 项目保留最多 3 个 `sample_cwds`，供 UI tooltip/详情展示完整路径。
- 项目中文名的维护边界在项目自身说明文件，不在监控软件内维护中心映射表。
- 项目历史路径也由当前项目自身的 `CLAUDE.md` 维护；例如目录迁移后，旧日志仍可跟随当前项目名称显示。

## 7. 已知坑位

- Codex `rate_limits` 不在事件顶层；早期临时判断已被真实扫描推翻。
- Codex 在 5 小时限额耗尽或临时无法返回完整 quota 时，可能写出较新的空 `rate_limits` 或缺少 `used_percent` 的窗口。未知值不能伪装成真实 `0%`：reader 必须跳过不可显示 quota，折叠态 UI 中心文本用 `—` 表示未知，只有真实 `0.0` 才显示 `0%`。回归测试覆盖 `tests/test_reader_codex.py`、`tests/test_models.py`、`tests/test_ui_tk.py`。
- 文件路径只能用于扫描优化，今日/近 30 天归属仍以事件 timestamp 为准。
- Codex `function_call_output` 常包含目录列表，一条记录可能有 50+ 条无关 `/claude/{project}` 路径，若参与投票会完全淹没真实信号（已验证：单条 `function_call_output` 59票 vs `message` 4票）。修复方案见 `app/reader_common.py`：事件类型加权 + 扫描窗口 200 行。回归测试在 `tests/test_reader_common.py`。
- Claude Code 的 `type:"user"` 也可能只是 `tool_result`，例如工具输出列出其他项目的 `CLAUDE.md` / `SKILL.md`。这些路径不是用户意图，不能按 5x 高权重投票；只扫描 Claude message content 里的 `text` 段。回归测试：`tests/test_reader_common.py::test_claude_tool_results_do_not_count_as_user_intent`、`tests/test_reader_claude.py::test_tool_result_project_list_does_not_infer_workspace_root_session`。
- Claude Code SessionStart hook 或 attachment 可能注入多项目上下文，只能作为提示给 agent，不能参与项目归因。回归测试：`tests/test_reader_common.py::test_claude_session_hooks_do_not_count_as_project_signal`。
- Claude Code 同一 assistant `message.id` 可能重复写入 2-5 次；若不去重，30 天 Claude token 会被重复累计。回归测试：`tests/test_reader_claude.py::test_duplicate_assistant_message_id_counts_usage_once`。
- 多项目摘要型 Codex 会话可能在普通 `message` / `agent_message` / `task_complete` 中弱引用多个项目。若弱信号打平，不能把今日用量挂到先出现的项目（例如误挂到 `product-detect`）；应返回 `None` 并让聚合归入 `其他`。回归测试：`tests/test_reader_common.py::test_tied_weak_project_signals_return_none`。
- 工作区根目录启动的长会话可能在前 200 行把任务名识别成唯一候选，但该名称并不是实际项目目录。Codex reader 必须先验证候选对应的 `CLAUDE.md`；无效候选不得触发早返回，应继续扫描到 1000 行。真实案例中 `aftersales-confidence-safety-v1` 抢占了后段才出现的 `aftersales-automation`，导致约 43M token 落入“其他”。回归测试：`tests/test_reader_common.py::test_invalid_early_candidate_extends_to_late_valid_project`、`tests/test_reader_codex.py::test_invalid_early_candidate_uses_late_known_project`。
- `某项目` 不是实际项目。它来自 WorkBuddy 文档中的示例路径 `/Users/chat/claude/某项目`；不存在对应项目元数据时必须忽略，不能因中文字符满足路径正则就当作项目。
- 实际工作树路径可能是 `~/.config/superpowers/worktrees/claude/aftersales-confidence-safety-v1/aftersales-automation`。第一段是临时任务名，最后一段才是正式项目。不得按名称前缀猜测；只使用日志中完整路径建立唯一映射。
- neat 是收尾确认而不是逐轮证据替代品。它可以纠正未知和过期继承值，但真实跨项目工具操作必须保留分段；讨论 neat 本身不算总结标记，只有明确的收尾指令才触发。
- 新版 Codex `exec` 是外层 JavaScript 调度器，真实 `workdir` 可能使用未加引号的 `workdir:`，项目路径也可能只存在于内层本地文件工具参数。解析这类输入时只接受存在 `CLAUDE.md` 的项目，并排除协调工具；否则会把诊断脚本里提到的其他项目误当成当前项目。
- Claude 根会话不能因为“后来只出现过一个项目”就无边界回填。安全范围只能是首次与末次真实项目 `cwd` 之间；这能覆盖项目执行期间的根调度开销，同时保留开始前、结束后及跨项目讨论。
- 代码修改后必须重启 app 进程才能生效（`python3.13 main.py --ui` 是长驻进程，不热重载）。
- `.app` 与 LaunchAgent 共享单实例锁。调试“双击没打开”时先查 `~/Library/Application Support/Codex Monitor/codex-monitor.lock` 中的 PID，再用 `ps -p <pid>` 判断是否仍有旧 UI 进程占锁。
- tkinter `create_arc` 的 `extent` 取到 ±360 时整段弧渲染为空白。配额圆环 100% 时 `extent = -100 × 3.6 = -360`，会让满载圆环显示为空（看起来"归零"）。灰色轨道一直用 `-359.99` 规避，但进度弧早期漏了。修复：`app/ui_tk.py::_ring_extent()` 统一把进度弧 clamp 到 `-359.99`，并抽成纯函数以便脱离 tkinter 单测。回归测试 `tests/test_ui_tk.py::test_ring_extent_*`。新增任何 `create_arc` 都不得让 extent 触到 ±360。
- 测试经验：若用户明确要求 Tk 浮层“移开即隐藏、立刻可再次展开”，反复 create/destroy `Toplevel` 可能触发 macOS/Tk 窗口层事件延迟，表现为快速再点击无响应。同类体验问题可优先验证 `withdraw()` / `deiconify()` 复用窗口；普通模态弹窗或一次性设置窗口不套用此经验。
- 磨砂 UI 不要用反复调 `WINDOW_ALPHA` / Canvas `stipple` 当主方案：前者会把文字和圆环一起变淡，后者不是真 alpha。原生 blur backing window 必须保持 `NSColor.clearColor()`，禁止叠半透明白色背景或强制 `Aqua + inactive`，否则壁纸采样会变成均匀灰板。当前基线使用 `NSVisualEffectMaterialPopover + behindWindow + active`，主胶囊、展开态、项目弹层只通过 blur window alpha 区分，Tk 前景保持 `alpha=1.0`。
- 当前 Tk 前端的视觉基线以用户提供的 macOS 桌面组件截图为准：收起态、展开态和项目弹层统一使用无描边的白色/白灰色文字；不要添加 halo、阴影字或深色字边。配额圆环只绘制一层灰色轨道和一层白灰色进度弧，不额外绘制起点/终点圆形端帽。磨砂材质与前景样式分开调试，字体修正时不要顺带改动 blur 参数。
- 原生 `NSVisualEffectView` 使用独立 backing `NSWindow` 时，必须和 Tk `Toplevel` 生命周期绑定：撤回状态不得安装；`deiconify()` 后再安装/恢复；临时隐藏调用 `orderOut_()` 且保留实例；彻底销毁时才 `close()` 并清空引用。禁止在 `withdraw()` 后排队异步 `orderFront`，否则会出现无内容的磨砂残影。
- `watchdog` 不是标准库；未安装时会走 polling fallback。polling 只能做轻量 mtime 检测，不能直接触发主线程聚合或高频后台聚合。
- 测试 fixture 必须脱敏，只保留结构和 token 数字。
- 开机自启只生成 plist，不自动 bootstrap；写错 plist 后由用户手动启用/回滚，避免挂起登录态。
