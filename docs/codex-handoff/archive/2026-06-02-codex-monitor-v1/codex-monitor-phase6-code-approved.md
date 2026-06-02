# Codex Monitor 阶段 6 复审结论

**审查方：** Claude Code  
**时间：** 2026-06-01  
**结论：** 阶段 6 通过，允许用户手动执行 launchctl bootstrap 启用开机自启

---

## 3 个阻断要求落实确认

| 要求 | 代码位置 | 结论 |
|------|---------|------|
| 不自动执行 launchctl | `main.py:170-179`，只调用 `install_launch_agent()` + 打印命令 | ✅ |
| watcher 增量门控 | `DebouncedRefresher.flush_due()` → `RefreshRequest(claude_modified_since=now-300, claude_max_files=50)`；`_read_local_data()` 尊重 request 字段 | ✅ |
| 日志到 `~/Library/Logs/Codex Monitor/` | `autostart.py:21-22`，`build_launch_agent_plist` 写入正确路径 | ✅ |

---

## 代码质量审查

### runtime.py

- `DebouncedRefresher` 纯函数式，无线程，`flush_due()` 由调用方轮询触发，无竞争问题。✅
- `PollingWatcher.poll_once()` 用 `rglob("*.jsonl")` 扫目录取最大 mtime，不读文件内容。✅
- `start_watchdog_observer()` 用 `try/except ImportError` 优雅降级，watchdog 不可用时返回 None。✅
- watchdog handler 只对 `.jsonl` 后缀文件触发，过滤目录事件。✅

### autostart.py

- `build_launch_agent_plist()` 设置了 `WorkingDirectory: project_dir`，解决了开机自启时工作目录不确定的问题。✅
- `launchctl_bootstrap_command()` 只返回字符串，不执行。✅

### 安全边界

- 无任何 `.codex/auth.json` 读取路径。✅
- 无 HTTP quota 请求。✅
- watcher 不读 JSONL 内容，只看 mtime 和文件路径。✅

---

## 测试验证

```
27/27 tests OK（python3 + python3.13 双版本）
compileall: 通过
smoke-aggregate: 通过
```

---

## 允许执行 launchctl bootstrap

可以手动执行：

```
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.local.codex-monitor.plist
```

风险说明：
- 执行后下次登录时 Codex Monitor 会自动启动
- 如需撤销：`python3.13 main.py --uninstall-autostart`，然后 `launchctl bootout gui/$(id -u) com.local.codex-monitor`
- 当前 plist 是 `KeepAlive: false`，关掉窗口就不会自动重启

---

## 无需修复项

无阻断问题。

## 可延期

- 菜单栏化（rumps/PyObjC）
- HTTP quota
- daemon/UI 双进程
