# Codex Monitor 网页版 Claude 建议与 Codex 临时判断

**项目：** `codex-monitor`  
**原请求：** `docs/codex-handoff/codex-monitor-review-plan.md`  
**建议来源：** 网页版 Claude（非 Claude Code 正式审计）  
**整理方：** Codex  
**时间：** 2026-05-31T15:03:32+08:00

> 这份文件只记录网页版 Claude 的建议和 Codex 的临时技术判断，不能视为 Claude Code 已经正式审计或批准该计划。下一步应由 Claude Code 基于本文件和 `codex-monitor-review-plan.md` 重新调整计划。

## Codex 二次判断

这份审计建议整体可采纳，尤其是三个判断：

- MVP 优先解析本地 JSONL，而不是读取凭证或请求 `wham/usage`。
- 第一版暂缓 `rumps/watchdog/动画/开机自启`，先验证统计口径和浮窗体验。
- 前端规格走 macOS 原生监控工具方向，宽度固定、深色、信息密度克制。

但需要在执行计划里修正和细化以下点：

1. **Codex `rate_limits` 路径必须修正。** 本机实测 JSONL 结构中，`rate_limits` 位于 `token_count` 事件顶层，而不是 `payload.rate_limits`。实现应优先读 `event["rate_limits"]`，并兼容 `event["payload"]["rate_limits"]` 作为未来变体。
2. **限额时间戳必须显示。** 由于本地 JSONL 只在出现新 `token_count` 时更新限额，UI 必须显示该条限额数据的事件时间；超过 30 分钟显示“数据较旧”。
3. **Claude token 口径要分层保存。** 数据模型必须分开保存 `input_tokens`、`cache_read_input_tokens`、`cache_creation_input_tokens`、`output_tokens`。UI 可以显示合计，但不能丢失拆分字段。
4. **“事件类型”不进入第一版硬要求。** Claude 的视觉稿保留了事件类型区块，但它依赖工具调用/路径推断，准确性弱于 token 统计。MVP 可显示“暂未分类”或直接隐藏该区块；等 reader 和聚合层稳定后再加。
5. **字体规格要有 tkinter fallback。** `SF Pro Text`、`SF Pro Mono` 不一定能被 tkinter 直接按名称加载；实现应优先尝试，失败时用 `System` 和 `Menlo`。

## 建议结论

### 问题 1：MVP 是否改用本地 `rate_limits`，不打 `wham/usage`

该方向可采纳，但字段路径需修正为：优先读取 `event.rate_limits`，兼容 `event.payload.rate_limits`。

理由：限额数据已在本地 Codex JSONL 中出现，离线可用，不碰凭证，比 HTTP 端点稳定。`wham/usage` 留作阶段 6 可选增强。

注意：`rate_limits` 只在有 `token_count` 事件时更新。如果用户长时间没有新对话，浮窗会显示上一次会话结束时的限额状态。UI 必须显示数据时间戳，让用户知道这个数据来自什么时候。

### 问题 2：第一版暂缓 rumps / watchdog / 动画 / 开机自启

该取舍可采纳。`rumps` 在 Python 3.13 下兼容性不明确，第一版用普通 `python3 main.py` 启动 tkinter 浮窗即可。数据准确性优先于菜单栏体验。

### 问题 3：项目结构

结构方向可采纳。`app/reader_*` 只读不写的边界正确，符合 `/Users/chat/claude` 新项目规范。

### 问题 4：Python 3.13 + tkinter 是否是最稳妥方案

保持 Python + tkinter，不建议现在切换技术栈。数据层是纯文件解析，没有性能瓶颈；SwiftUI 或 PyObjC 对 Codex CLI 的构建摩擦更高。MVP 稳定后，如果 tkinter 原生感不足，再考虑用 PyObjC 包一层 NSPanel。

### 问题 5：Claude Code token 统计口径

应该计入 cache read/create，但分开保存和展示。

推荐数据口径：

- `input_tokens`
- `cache_read_input_tokens`
- `cache_creation_input_tokens`
- `output_tokens`
- `total_estimated_tokens = input + cache_read + cache_creation + output`

UI 文案使用“本地日志估算”，数字旁边加 `~` 前缀。避免出现“账单”“计费”等词，防止误认为是精确账单数据。

### 问题 6：前端样式规格

整体采纳 Claude 的规格，补充两点：

- 第一版只做深色模式。
- “事件类型”区块不是 MVP 必需项；如果没有可靠分类数据，显示“暂未分类”或隐藏该区块。

## 前端样式规格

**整体风格：** macOS 原生监控工具风格。不用渐变、不用卡片阴影叠加、不用 emoji 做图标。字体用系统字体，颜色克制。参考 Activity Monitor 和 Stats.app 的审美，而不是 Notion 或 AI 产品。

### 尺寸

| 状态 | 宽 | 高 |
|------|----|----|
| 折叠 | 300px | 88px |
| 展开 | 300px | 480px，内容自适应 |

宽度固定 300px，不随展开变化，保持位置稳定。

### 颜色

```python
BG_WINDOW = "#1E1E1E"
BG_SECTION = "#2A2A2A"
BORDER = "#3A3A3A"

TEXT_PRIMARY = "#E8E8E8"
TEXT_SECONDARY = "#888888"
TEXT_MONO = "#CCCCCC"

BAR_OK = "#4D9E6F"
BAR_WARN = "#C8872A"
BAR_DANGER = "#C04040"

TAG_CODEX = "#4A7FA5"
TAG_CLAUDE = "#7A6FAA"

ACCENT = "#5A8FA8"
```

### 字体与字号

```python
FONT_LABEL = ("SF Pro Text", 11, "normal")
FONT_VALUE = ("SF Pro Mono", 13, "normal")
FONT_LARGE = ("SF Pro Mono", 18, "bold")
FONT_CAPTION = ("SF Pro Text", 10, "normal")
FONT_TITLE = ("SF Pro Text", 12, "normal")

FONT_FALLBACK_SANS = "System"
FONT_FALLBACK_MONO = "Menlo"
```

### 折叠态布局

```text
┌─ 300px ──────────────────────────────┐
│  ● Codex 限额              [▼] 14:32 │
│  5h  ████████████░░░░  72%  还剩 1h │
│  7d  █████░░░░░░░░░░░  38%  还剩 4d │
└──────────────────────────────────────┘
```

- 内边距：水平 12px，垂直 8px。
- 状态点颜色跟随最高风险等级的限额。
- `[▼]` 按钮用文字按钮，不加边框。
- 时间戳右对齐，`HH:MM` 格式。

### 展开态布局

```text
┌─ 300px ──────────────────────────────┐
│  ● Codex 限额              [▲] 14:32 │
│  5h  ████████████░░░░  72%  还剩 1h │
│  7d  █████░░░░░░░░░░░  38%  还剩 4d │
├──────────────────────────────────────┤
│  Token 估算              今日    本月│
│  [Codex]    1.24M      8.40M        │
│  [Claude]  ~0.31M     ~2.10M        │
│  合计        1.55M     10.50M        │
├──────────────────────────────────────┤
│  项目  (Top 5)                       │
│  lkwj          ██████████  42%       │
│  hermes        ███████     28%       │
│  codex-monitor ████        15%       │
│  kgos          ███         10%       │
│  其他          █            5%       │
├──────────────────────────────────────┤
│  事件类型 / 暂未分类                 │
├──────────────────────────────────────┤
│  本地日志估算  [手动刷新]  14:32:05 │
└──────────────────────────────────────┘
```

### 数字格式

- token 数字统一用 M（百万）单位，保留两位小数。
- `1,240,000 -> "1.24M"`。
- `< 100,000 -> "0.09M"`，不换单位，保持对齐。
- Claude Code 数字加 `~` 前缀。
- 限额百分比显示整数，例如 `72%`。
- 重置时间显示 `还剩 Xh` 或 `还剩 Xd Xh`。

### 状态与错误文案

| 场景 | 文案 | 颜色 |
|------|------|------|
| 无今日数据 | `暂无今日数据` | `TEXT_SECONDARY` |
| JSONL 解析错误 | `读取出错 (X 个文件跳过)` | `BAR_WARN` |
| rate_limits 缺失 | `限额数据待更新` | `TEXT_SECONDARY` |
| 数据超过 30 分钟未刷新 | `● 数据较旧` | `BAR_WARN` |

避免使用“离线”这个词。该工具本身主要读取本地日志，“离线”容易误导用户以为网络失败。

### 交互规格

- 拖拽：按住窗口任意非按钮区域可拖拽，位置写入 `data/state.json`。
- 折叠/展开：点击 `[▼/▲]`，MVP 无动画，直接切换高度。
- 手动刷新：点击底部“手动刷新”，立即重扫 JSONL。
- 右键菜单：MVP 暂不实现。
- 窗口透明度：`0.92`。

## 临时状态

不把这份网页版反馈视为正式执行许可。后续需要 Claude Code 重新调整或审计计划；正式进入实现前，再把确认后的约束同步到项目 `CLAUDE.md` / `docs/INDEX.md` / `tasks/todo.md`。
