# Codex Monitor 阶段 6 审查结论

**审查方：** Claude Code  
**时间：** 2026-06-01  
**结论：** 批准，可以开始实现。2 个必须修改点。

---

## 必须修改（阻断级）

### 1. LaunchAgent 不自动执行 launchctl

`--install-autostart` 只写 plist，打印下一步命令让用户自己执行：

```
plist 已写入 ~/Library/LaunchAgents/com.local.codex-monitor.plist
执行以下命令启用开机自启：
  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.local.codex-monitor.plist
```

不要在代码里自动调用 `launchctl bootstrap/kickstart`。原因：写错 plist 会挂起登录态，不易回滚。

### 2. watcher 触发后必须带 modified_since 门控，禁止全量扫 .claude/projects

watcher 的语义是"有文件变化了"→触发一次带时间过滤的增量读取，不是触发全量扫描。

`runtime.py` 实现约束：
- watcher 触发 → 调用 `read_claude_projects(modified_since=time.time()-300, max_files=50)` 类似参数
- 禁止在 watcher 回调里无限制扫描 `.claude/projects` 全量历史（3.8GB）
- 全量扫描仅在用户手动点击"刷新"时允许，且仍受 `--claude-days` 参数约束

---

## 设计确认（无需修改）

| 问题 | 结论 |
|------|------|
| LaunchAgent KeepAlive: false | ✅ 合理，浮窗工具不需要系统强制拉起 |
| 单进程 tkinter + watcher | ✅ 足够，`root.after()` 回主线程即可，不需要拆 daemon |
| watchdog + debounce + 5 秒轮询 fallback | ✅ 可接受 |
| 安全边界（禁 auth.json、禁 HTTP quota、不输出正文） | ✅ 全部保持 |

---

## 一处修改

**日志位置改为 `~/Library/Logs/Codex Monitor/`，不用 `data/logs/`。**

原因：开机自启时工作目录不确定，项目内相对路径不可靠。macOS 标准日志目录更稳，且 Console.app 可以直接查看。

LaunchAgent plist 里：

```xml
<key>StandardOutPath</key>
<string>/Users/chat/Library/Logs/Codex Monitor/stdout.log</string>
<key>StandardErrorPath</key>
<string>/Users/chat/Library/Logs/Codex Monitor/stderr.log</string>
```

---

## 实施顺序确认

runtime → autostart → app bundle → UI wiring → docs → verification

顺序合理，不需要调整。

---

## 可延期

- 菜单栏化（rumps/PyObjC）：等 `.app + tkinter` 稳定后再做
- HTTP quota：继续暂缓
- daemon/UI 双进程拆分：暂不需要
