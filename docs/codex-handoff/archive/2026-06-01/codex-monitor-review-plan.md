# Codex Monitor 优化计划与 Claude Code 复审请求

**来源计划：** `/Users/chat/Downloads/codex_monitor_plan.md`  
**项目目录目标：** `/Users/chat/claude/codex-monitor/`  
**动作：** `review-plan`  
**发起方：** Codex  
**时间：** 2026-05-31T01:48:58+08:00

> 当前状态：等待 Claude Code 正式复审。`docs/codex-handoff/codex-monitor-web-claude-feedback.md` 只记录网页版 Claude 的临时建议，不能视为 Claude Code 已批准实现。

## 结论

原计划方向可用，但执行顺序和数据源需要调整。最重要的优化是：MVP 不应先访问 `chatgpt.com/backend-api/wham/usage`，也不应优先读取 `.codex/auth.json` 里的凭证字段；本机 Codex JSONL 已经在 `event_msg -> payload.type == "token_count"` 中写入了 `payload.info.last_token_usage`、`payload.info.total_token_usage` 和顶层 `rate_limits`。这足够支撑第一版限额和 token 统计。

这样做的原因：

- 安全性更高：第一版无需读取或传递 access token / refresh token。
- 稳定性更高：避免依赖非官方内部 HTTP 端点字段。
- 本机适配更准：已验证当前 Codex session JSONL 的真实字段结构。
- 用户体验更好：离线也能显示上一次限额状态，网络失败不会导致核心界面失效。

## 本机事实核对

已验证：

- `/Users/chat/claude` 是项目工作区，新项目应放在该目录下。
- 新项目规范见 `/Users/chat/claude/docs/new-project-template.md`。
- 当前 Python 是 `Python 3.13.5`，不是原计划写的 Python 3.11。
- `tkinter` 可用，版本为 Tk 8.6。
- `requests` 已安装。
- `rumps` 和 `watchdog` 当前未安装。
- `.codex/auth.json` 顶层字段是 `OPENAI_API_KEY`、`auth_mode`、`last_refresh`、`tokens`；`access_token/account_id` 在 `tokens` 下，不是顶层。
- Codex JSONL 中 token 事件真实结构为：
  - `type == "event_msg"`
  - `payload.type == "token_count"`
  - `payload.info.total_token_usage`
  - `payload.info.last_token_usage`
  - `rate_limits.primary`（实测为事件顶层字段）
  - `rate_limits.secondary`（实测为事件顶层字段）
- Claude Code JSONL 中 assistant usage 真实结构为：
  - `type == "assistant"`
  - `cwd`
  - `message.usage.input_tokens`
  - `message.usage.output_tokens`
  - `message.usage.cache_creation_input_tokens`
  - `message.usage.cache_read_input_tokens`

未验证或需谨慎：

- `rumps` 在当前 Python 3.13 + macOS 环境下是否可安装、是否稳定。
- `tkinter` 置顶、不抢焦点、透明、拖拽在 macOS 上的最终体验。
- `wham/usage` 端点当前是否可用、字段是否仍如原计划描述。

## 对原计划的主要调整

### 1. 数据源优先级调整

原计划：

1. 先做 `quota.py`，读取 `.codex/auth.json` 并请求 `wham/usage`。
2. 再解析 Codex/Claude JSONL。

建议改为：

1. 先做 `codex_reader.py`：解析本地 `.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`。
2. 从最新 `token_count` 事件读取：
   - 5h 限额：优先 `rate_limits.primary.used_percent / resets_at / window_minutes`，兼容 `payload.rate_limits.primary`
   - 7d 限额：优先 `rate_limits.secondary.used_percent / resets_at / window_minutes`，兼容 `payload.rate_limits.secondary`
   - 本轮消耗：`payload.info.last_token_usage`
   - 会话累计：`payload.info.total_token_usage`
3. 再做 `claude_reader.py`：解析本地 `.claude/projects/**.jsonl`。
4. 最后才考虑 `quota_http.py`，作为可选增强，不进入 MVP 必需路径。

对用户的影响：第一版可以更快跑起来，而且不会碰敏感凭证。

### 2. 项目结构调整为本工作区规范

建议目录：

```text
/Users/chat/claude/codex-monitor/
  CLAUDE.md
  SKILL.md
  README.md
  requirements.txt
  main.py
  app/
    __init__.py
    config.py
    state.py
    models.py
    reader_codex.py
    reader_claude.py
    aggregate.py
    ui_tk.py
    ui_theme.py
    tray.py
  tests/
    fixtures/
    test_reader_codex.py
    test_reader_claude.py
    test_aggregate.py
  docs/
    INDEX.md
    frontend-style-spec.md
  tasks/
    todo.md
    lessons.md
```

说明：

- `CLAUDE.md`、`SKILL.md`、`docs/INDEX.md`、`tasks/todo.md` 是本工作区新项目的启动地图。
- `app/reader_*` 只读本地 JSONL，不写 `.codex` 或 `.claude`。
- `app/ui_theme.py` 暂放正式确认后的样式方案。
- `state.json` 不建议放源码目录根部混在代码里。若必须持久化窗口位置，建议默认放：
  - `/Users/chat/claude/codex-monitor/data/state.json`
  - 或 macOS 标准应用支持目录
- `data/` 只放结构化持久状态，不放日志。

### 3. MVP 范围收窄

建议第一版只做：

- tkinter 常驻小浮窗。
- 显示 Codex 5h / 7d 限额百分比和重置时间。
- 显示限额数据时间戳；超过 30 分钟未刷新时提示“数据较旧”。
- 显示 Codex 今日、本月 token 估算。
- 显示 Claude Code 今日、本月 token 估算。
- 显示 Top 5 项目。
- 手动刷新按钮。
- 窗口拖拽和位置持久化。

第一版暂缓：

- `rumps` 菜单栏驻留。
- `watchdog` 实时监听。
- 展开/折叠动画。
- 开机自启。
- `wham/usage` HTTP 查询。
- 复杂事件类型推断（如果 UI 保留该区块，MVP 显示“暂未分类”或隐藏）。

原因：用户真正要先解决的是“看限额和消耗”，不是先做一个完整 macOS 菜单栏产品。MVP 缩小后更容易验证数据准确性和 GUI 体验。

### 4. token 统计口径修正

Codex：

- 优先使用每条 `token_count` 的 `payload.info.last_token_usage` 做增量统计。
- 同一 session 文件内不建议对 `total_token_usage` 简单求和，因为它是累计值。
- 月统计只扫当月目录：`.codex/sessions/YYYY/MM/**`。
- 今日统计按 JSONL 事件 timestamp，而不是只按文件路径，因为文件路径可能受时区或会话跨日影响。

Claude Code：

- 使用 `message.usage` 直接求和。
- 字段包括：
  - `input_tokens`
  - `output_tokens`
  - `cache_creation_input_tokens`
  - `cache_read_input_tokens`
- UI 应标注“本地日志估算”，因为实际计费和日志记录口径可能不完全一致。
- 子代理路径如 `subagents/*.jsonl` 要纳入统计，但项目归属优先用记录内 `cwd`，不是只从目录名反推。
- 数据模型必须分开保存 `input_tokens`、`cache_read_input_tokens`、`cache_creation_input_tokens`、`output_tokens`，UI 可以显示合计，但不能丢失拆分口径。

### 5. 隐私与安全边界

实现时必须遵守：

- 只读 `.codex/sessions`、`.claude/projects`、`.codex/auth.json`。
- MVP 不读取 `.codex/auth.json` 的 token 值。
- 不把历史对话正文写入 UI、日志、测试快照或调试输出。
- 测试 fixture 必须脱敏，只保留 JSON 结构和 token 数字。
- 错误日志只输出文件路径、行号、错误类型，不输出整行 JSONL 内容。

## 推荐开发顺序

### 阶段 0：项目初始化

- 创建 `/Users/chat/claude/codex-monitor/`。
- 创建 `CLAUDE.md`、`SKILL.md`、`docs/INDEX.md`、`tasks/todo.md`。
- 创建 Python 项目结构。
- 写明安全边界：只读本地会话文件，不复述 token，不输出对话正文。

验证：

- `python3 -m compileall app tests`
- `git status --short` 确认只新增项目文件。

### 阶段 1：Codex 本地 reader

- 写 `app/reader_codex.py`。
- 从 fixture 解析 `session_meta.payload.cwd`。
- 从 `event_msg + payload.type == "token_count"` 读取 `last_token_usage` 和 `rate_limits`。
- `rate_limits` 优先读取事件顶层字段，兼容 `payload.rate_limits`。
- 输出结构化对象，不让 UI 直接读 JSON。

测试：

- 单文件 session 统计正确。
- 多条 `token_count` 使用 `last_token_usage` 求和。
- 缺失 `rate_limits` 时返回 `None`，不崩溃。
- 限额数据带上来源事件 `timestamp`，UI 可判断数据新旧。
- JSONL 某一行损坏时跳过并记录错误计数。

### 阶段 2：Claude Code 本地 reader

- 写 `app/reader_claude.py`。
- 递归扫描 `.claude/projects/**/*.jsonl`，包含 subagents。
- 从 assistant message usage 求和。
- 项目名优先来自 `cwd` 最后一级。
- 保存拆分 token 字段和估算合计，不把 cache read/create 混成一个不可追溯数字。

测试：

- 普通 session 统计正确。
- subagent 文件纳入统计。
- usage 缺失或全 0 不崩溃。
- 不读取或输出 `message.content`。

### 阶段 3：聚合层

- 写 `app/aggregate.py`。
- 合并 Codex 和 Claude 的今日/月度统计。
- 输出：
  - quota 状态
  - daily/monthly token
  - by_project Top 5
  - last_updated
  - error/warning 列表

测试：

- 空数据返回 0。
- 多项目排序稳定。
- 项目名过长时由 UI 截断，aggregate 保留原名。

### 阶段 4：tkinter MVP UI

- 写 `app/ui_tk.py`。
- 用假数据先跑 UI。
- 接入 aggregate 输出。
- 支持手动刷新和拖拽。
- 支持折叠/展开，但动画可暂缓。

验证：

- `python3 main.py --demo` 可在不读真实日志时打开 UI。
- `python3 main.py` 可读真实本地数据。
- 窗口关闭不留下后台线程。

### 阶段 5：Claude 前端审美方案落地

本阶段建议由 Claude 先出方案，Codex 再按方案实现。

需要 Claude 明确：

- 浮窗视觉风格：偏 macOS 原生、Claude/Codex 工作台风格，还是极简运维监控风格。
- 折叠态最小信息密度：只显示限额，还是同时显示今日 token。
- 展开态信息优先级：限额、今日消耗、项目榜、更新时间如何排序。
- 颜色阈值和语义：60/85 是否合适；危险色是否只用于限额，不用于 token 消耗。
- 字体、字号、圆角、阴影、透明度和间距。
- 深色/浅色模式是否第一版支持。
- 数字格式：`1.2M`、`120万`、还是完整数字。
- 错误/离线状态文案：怎样既不吓人又能指导行动。

### 阶段 6：菜单栏与增强

只有在 tkinter MVP 数据正确、UI 方案确认后再做：

- 评估 `rumps` 是否适配 Python 3.13。
- 如 `rumps` 安装或体验不好，考虑保持 tkinter 浮窗 + 普通进程，菜单栏延后。
- `watchdog` 作为性能优化，不是必需功能。
- `wham/usage` 作为后续可选增强，必须单独审计安全边界。

## 网页版 Claude 建议后的临时修正

网页版 Claude 给出支持性建议，但这不是 Claude Code 正式审计。Codex 二次核对后，先记录以下临时执行约束，等待 Claude Code 复审或重新调整计划：

1. 本机 Codex JSONL 的 `rate_limits` 是事件顶层字段，不是 `payload.rate_limits`；实现必须优先读顶层，并兼容 payload 内字段作为未来变体。
2. UI 必须展示限额数据时间戳；超过 30 分钟提示“数据较旧”。
3. Claude Code token 统计必须分开保存 input/cache read/cache write/output，并显示“本地日志估算”，避免“账单/计费”类文案。
4. Claude 给出的 macOS 原生深色浮窗规格进入阶段 5，但“事件类型”区块不作为 MVP 阻塞项。
5. 网页版反馈详见 `docs/codex-handoff/codex-monitor-web-claude-feedback.md`。

## Claude 审计重点

请 Claude Code 审计以下问题：

1. 是否同意 MVP 不读取 `.codex/auth.json` token、不打 `wham/usage`，改用本地 Codex JSONL 的 `rate_limits`。
2. 是否同意第一版暂缓 `rumps/watchdog/开机自启/动画`，先确保统计准确和浮窗可用。
3. 新项目结构是否符合 `/Users/chat/claude/docs/new-project-template.md` 和当前工作区习惯。
4. Python 3.13 + tkinter 是否是当前本机最稳妥方案；是否建议改用 Node/Electron、SwiftUI、PyObjC 或其他方案。
5. Claude Code JSONL 的统计口径是否应计入 cache read/create；UI 文案该如何避免用户误读为账单精确值。
6. 前端样式和美观方案请 Claude 给出具体设计稿/规格，Codex 后续按规格实现。

## 给 Claude 的建议输出

请 Claude 回复时尽量给出：

- 是否批准、修改或推翻该优化方向。
- 必须修改的计划点。
- 前端样式规格：布局、色彩、字体、状态、信息层级。
- 是否允许 Codex 进入项目初始化和阶段 1 reader 实现。
- 如果不建议 Python/tkinter，请给出替代技术栈和迁移原因。
