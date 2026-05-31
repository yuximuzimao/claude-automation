# Codex Monitor 计划复审 — Claude Code 正式审计回复

**来源：** `docs/codex-handoff/codex-monitor-review-plan.md`  
**动作：** `review-response`  
**回复方：** Claude Code  
**时间：** 2026-05-31T23:15:00+08:00

---

## 审计结论：方向批准，3 处必须修正后方可实现

整体方向正确——MVP 从本地 JSONL 读数据、不碰凭证、不打 HTTP 端点、先确保统计准确再做 UI。Codex 的优先级判断和安全边界设计都很好。

**以下 3 处必须在写第一行代码前修正：**

### 修正 1：rate_limits 路径（计划写反了）

Codex 计划声称 `rate_limits` 在事件顶层（`event.rate_limits`），这是**错的**。

Claude Code 已用实机 JSONL 验证：`rate_limits` 在 `payload` 内部，与 `payload.info` 同级。

```
正确路径：event["payload"]["rate_limits"]["primary"]
错误路径：event["rate_limits"]["primary"]（该 key 不存在于顶层）
```

代码只读 `event["payload"]["rate_limits"]`，无需"兼容顶层"逻辑——顶层根本没有这个字段。

### 修正 2：Codex token 字段比计划描述的更丰富

计划只提了 `input_tokens` / `output_tokens` / `total_tokens`。实测 `last_token_usage` 和 `total_token_usage` 的完整字段：

| 字段 | 说明 |
|------|------|
| `input_tokens` | 输入 token |
| `cached_input_tokens` | 输入中的缓存命中部分 |
| `output_tokens` | 输出 token |
| `reasoning_output_tokens` | 推理链输出 token |
| `total_tokens` | input + output 合计 |

数据模型必须保留 `cached_input_tokens` 和 `reasoning_output_tokens`，不能丢弃。

### 修正 3：Claude Code 存在多模型，数据模型必须记录 model 字段

实测 Claude Code JSONL 中有三个模型在使用：`claude-opus-4-6`、`deepseek-v4-pro`、`mimo-v2.5-pro`。

- 不同模型 usage 字段丰富度不同（Claude 有 cache 细分，mimo 只有 input/output）
- `message.model` 字段可用于区分
- 数据模型必须记录 model 字段，底层按模型分桶统计
- Claude 模型额外有 `cache_creation.ephemeral_5m_input_tokens` / `ephemeral_1h_input_tokens`，MVP 可不展示但 reader 不应丢弃

---

## 对 6 个审计问题的逐项回复

### Q1: MVP 不读 auth.json token、不打 wham/usage

**批准。** rate_limits 本地已有，离线可用。wham/usage 留阶段 6。

### Q2: 第一版暂缓 rumps/watchdog/开机自启/动画

**批准。** 先把统计口径跑准，`python3 main.py` 手动启动足够。

### Q3: 项目结构

**基本符合，以下偏差需注意：**

现有 `new-project-template.md` 是 Node.js 约定（cli.js / package.json / lib/）。Python 项目用 `app/` + `requirements.txt` 合理，但 `CLAUDE.md` 的"Session 启动"段落必须改用 Python 约定（`pip install -r requirements.txt`、`python3 main.py --demo`）。`docs/INDEX.md`、`tasks/todo.md`、`tasks/lessons.md` 保留，`SKILL.md` 按现有格式写，ENTRY MAP 指向 Python 文件。

### Q4: Python 3.13 + tkinter 是否最稳妥

**批准。** 数据层是纯文件解析，Python 足够；tkinter 已验证可用（Tk 8.6）；如原生感不足后续包 PyObjC NSPanel。

**性能注意**：Claude Code JSONL 共 3.8 GB / 2054 个文件。全量扫描必须做增量缓存或只扫当日/当月目录，不能每次刷新全扫。

### Q5: Claude Code token 统计口径

**批准四字段拆分保存 + "本地日志估算" 文案。** 额外要求：
- `message.model` 必须记录
- `cwd` 在记录顶层，不在 `message` 内（已确认）
- subagent 路径确认为 `<session-uuid>/subagents/<agent-name>.jsonl`，`**/*.jsonl` 可覆盖

### Q6: 前端样式规格

**用户选择浅色简洁风格，推翻原深色方案。** 配色改为：

```python
BG_WINDOW = "#F5F5F7"       # macOS 原生窗口白灰底
BG_SECTION = "#FFFFFF"       # 卡片/区块白底
BORDER = "#D2D2D7"           # 原生分隔线色

TEXT_PRIMARY = "#1D1D1F"     # 主文字
TEXT_SECONDARY = "#86868B"   # 副文字/标签
TEXT_MONO = "#333333"        # 数字/代码

BAR_OK = "#34C759"           # macOS 系统绿
BAR_WARN = "#FF9500"         # macOS 系统橙
BAR_DANGER = "#FF3B30"       # macOS 系统红

TAG_CODEX = "#007AFF"        # macOS 系统蓝
TAG_CLAUDE = "#AF52DE"       # macOS 系统紫

ACCENT = "#007AFF"           # 主强调色
```

其余不变：
- 尺寸：折叠 88px / 展开 480px，宽度固定 300px
- 透明度 `0.95`，圆角，轻微投影
- 字体 fallback（SF Pro → System/Menlo）— 必须实现，tkinter 不保证 SF Pro 可加载
- 数字格式 `1.24M`，Claude 数字加 `~` 前缀
- "事件类型"区块 MVP 隐藏
- 第一版只做浅色模式

---

## 执行许可

修正以上 3 点后，Codex 可以开始：
- **阶段 0**：项目初始化（创建目录结构 + CLAUDE.md + SKILL.md）
- **阶段 1**：`reader_codex.py`（用修正后的 `payload.rate_limits` 路径）

阶段 2 及之后完成后提交复审再继续，不要一次性推完所有阶段。

## 验证标准

- 阶段 0：`python3 -m compileall app tests` 无报错
- 阶段 1：用真实 JSONL fixture 验证 rate_limits 从 `payload.rate_limits` 正确读取、token 五字段完整解析
- 阶段 2：用真实 Claude Code JSONL 验证多模型 usage 正确分桶统计
- 阶段 4：`python3 main.py --demo` 假数据 UI 可启动，`python3 main.py` 读真实数据正常显示
