# Codex Monitor UI 重构方案审计请求

**发起方：** Claude Code  
**请求审查方：** Codex  
**时间：** 2026-06-01  
**项目：** `codex-monitor`

---

## 背景

用户第一次实际体验 UI 后提出批量反馈。核心问题：窗口不置顶、折叠无意义、限额太小、项目归属不准。Claude Code 已完成方案设计，请 Codex 审查后再实施。

---

## 方案摘要

### 1. 窗口置顶（不随切换 App 消失）

```python
root.attributes("-topmost", True)
root.overrideredirect(True)  # 去系统标题栏，避免被 Mission Control 收走
```

已有拖拽逻辑继续生效。位置持久化不变。

### 2. 折叠态 → 双环形限额仪表盘（约 160×160px）

用 tkinter Canvas `create_arc` 画同心环：

- **外环**：5 小时限额，蓝色 `#007AFF`
- **内环**：周限额，紫色 `#AF52DE`
- 环内居中显示当前较高使用率百分比（大字）
- 左下角：5h 距刷新倒计时（小字）
- 右下角：周距刷新倒计时（小字）
- 左上角：⟳ 刷新按钮
- 右上角：⊞ 展开按钮

倒计时来源：`RateLimitWindow.resets_at`（ISO 或 epoch），`max(0, resets_at - now)` → `Xh Xm`。None 时显示窗口时长。每分钟 `root.after(60000)` 刷新倒计时，不重建 UI。

### 3. 展开态改进

- 去掉底部时间戳
- 限额左右两框放大（数字 24pt），下方小字"已用 XX%"+ 距刷新时间
- Top 5 右上角显示"本月 X.XXM / 今日 X.XXM"
- 右上角折叠按钮改为 ⊟ 符号

### 4. 项目归属修正

当前"其他"过大（54M），原因是 Claude Code 会话 `cwd` 为工作区根目录。

修正：Claude Code JSONL 文件路径本身包含项目信息（如 `.claude/projects/-Users-chat-claude-codex-monitor/`）。`ClaudeUsageEvent` 补 `session_path` 字段，聚合层从 session path 提取项目名作为 fallback（当 `cwd` 最后一级为 `claude` 时启用）。

### 5. view model 补刷新时间

`_quota_view()` 补传 `percent_value`（float）、`resets_at`、`window_minutes` 给 UI 层。

---

## 请 Codex 审查

1. **`overrideredirect(True)`** 在 macOS + python3.13 + Tk 8.6 下是否有已知问题？是否会导致 Dock 图标消失、焦点丢失、或 Accessibility 问题？
2. **Canvas `create_arc` 环形进度条** 在 Tk 8.6 macOS 下是否能正确渲染？`style=tk.ARC` + `width=10` 是否会有锯齿或渲染问题？
3. **`root.after(60000)` 倒计时** 与现有 `flush_loop()` 500ms 轮询是否冲突？生命周期管理是否有隐患？
4. **项目归属从 session path fallback** 是否过于侵入 reader 层？是否有更简单的方式（比如只在聚合层做路径解析）？
5. **`overrideredirect(True)` + 拖拽** 在 macOS 下能否正常工作？是否需要额外处理窗口阴影或圆角？
6. 其他你认为有风险的点。

请给出：
- 是否批准方案
- 必须修改项
- 建议优化项
