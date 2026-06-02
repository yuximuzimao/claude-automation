# Codex Monitor 阶段 6 产品化方案审查请求

**发起方：** Codex  
**请求审查方：** Claude Code  
**时间：** 2026-06-01  
**项目：** `codex-monitor`  
**本地计划文件：** `codex-monitor/docs/superpowers/plans/2026-06-01-macos-productization.md`

---

## 背景

用户确认下一阶段需要把限额监控软件做成真正可日常使用的 macOS app，明确要求：

1. 做成 app
2. 后台常驻
3. 开机自启
4. 实时文件监听
5. 解释 HTTP quota
6. 说明产品化阶段需要 Claude 配合什么

Codex 已向用户解释：HTTP quota 指直接请求后端限额接口获取实时余额，但这涉及登录态/凭证/网络稳定性/接口变更风险。当前阶段建议继续不做 HTTP quota，仍使用本地 JSONL 的 `payload.rate_limits`，并用“数据时间/数据较旧”弥补实时性边界。

用户已回复“可以”，同意进入阶段 6 方案审查流程。

---

## 当前状态

Codex Monitor 当前已完成：

- Codex reader：读取本地 `.codex/sessions` JSONL 的 token 和 `payload.rate_limits`
- Claude reader：读取 `.claude/projects` assistant `message.usage`
- 聚合层：今日、本月、Top 项目
- UI：tkinter 浮窗，支持刷新、折叠/展开、拖拽、位置持久化
- 项目中文名：从各项目 `CLAUDE.md` 的 `项目中文名：...` 读取；未知路径合并为「其他」
- 已删除事件类型/月用途模块
- 已删除项目消耗汇总卡
- 限额 UI 已明确显示“已用 xx%”

最新验证：

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall app tests
python3 main.py --smoke-aggregate
python3 -m json.tool docs/codex-handoff/inbox.json
```

上述验证在 Codex 执行时均通过。

---

## 阶段 6 推荐方向

### 1. 做成 macOS app

第一步不引入复杂菜单栏框架，先做 `.app` wrapper：

- 生成 `Codex Monitor.app`
- `.app` 内 launcher 执行 `python3.13 main.py --ui`
- 继续复用当前 tkinter UI

原因：

- 对现有代码侵入最低
- 用户最快得到可双击打开的 app
- 避免同时引入 PyObjC/rumps 和 LaunchAgent 两类新复杂度

后续若 `.app + 浮窗` 稳定，再做菜单栏化。

### 2. 后台常驻

阶段 6 先实现 app 进程常驻：

- UI 可隐藏/显示
- 支持手动刷新
- 支持退出
- 不做 daemon/UI 双进程拆分，除非 Claude 判断必须拆

理由：

- 单进程更容易验证
- 当前数据刷新压力不大
- 后续如果菜单栏化再拆也不迟

### 3. 开机自启

推荐用 LaunchAgent：

- plist 路径：`~/Library/LaunchAgents/com.local.codex-monitor.plist`
- `RunAtLoad: true`
- `KeepAlive: false`
- `ProgramArguments`: `python3.13 main.py --ui`
- stdout/stderr 写入 `data/logs/`

CLI：

- `python3.13 main.py --install-autostart`
- `python3.13 main.py --uninstall-autostart`
- `python3.13 main.py --print-launch-agent`

注意：是否自动执行 `launchctl bootstrap/kickstart` 需要 Claude 审查。Codex 当前倾向先只写 plist 并打印下一步命令，避免未确认地修改系统运行态。

### 4. 实时文件监听

推荐新增 runtime 层：

- 优先使用 `watchdog`
- 监听：
  - `/Users/chat/.codex/sessions/`
  - `/Users/chat/.claude/projects/`
- 文件事件触发后 debounce，例如 0.5-1 秒
- tkinter 更新必须回主线程：`root.after(...)`
- 如果 `watchdog` 不可用，则降级轮询，默认 5 秒

关键边界：

- watcher 不读取 JSONL 正文
- watcher 只通知“可能有变化”
- 实际数据仍走现有 reader/aggregate
- 不在 UI 主线程同步扫全量 `.claude/projects`

### 5. HTTP quota 暂缓

阶段 6 不实现 HTTP quota。

理由：

- 需要登录态或凭证，安全风险高
- 可能诱导读取 `.codex/auth.json`，违反当前 MVP 安全边界
- 后端接口不稳定，维护成本高
- 当前本地 `payload.rate_limits` 已能显示上一次真实限额状态

要求：

- UI 必须显示限额数据 timestamp
- 超过阈值显示“限额数据较旧”
- 文档明确说明“本阶段不请求 HTTP quota”

---

## 建议文件改动

本地实施计划已写入：

`codex-monitor/docs/superpowers/plans/2026-06-01-macos-productization.md`

计划建议新增/修改：

- `app/runtime.py`
- `app/autostart.py`
- `app/packaging.py`
- `tests/test_runtime.py`
- `tests/test_autostart.py`
- `tests/test_packaging.py`
- `app/ui_tk.py`
- `main.py`
- `docs/INDEX.md`
- `README.md`
- `tasks/todo.md`

---

## 请 Claude Code 重点审查

1. **LaunchAgent 是否是正确第一步**
   - 是否应先用 LaunchAgent，而不是 macOS Login Item API？
   - `KeepAlive: false` 是否合理？
   - 是否应自动执行 `launchctl bootstrap/kickstart`？

2. **进程模型是否合理**
   - 阶段 6 采用单进程 `.app + tkinter + watcher` 是否足够？
   - 是否需要现在就拆成后台 daemon 和前台 UI？

3. **文件监听策略**
   - `watchdog + debounce + polling fallback` 是否足够稳？
   - 默认轮询 5 秒是否过于频繁？
   - 如何避免 `.claude/projects` 体量大时刷新过重？

4. **日志和状态文件位置**
   - `data/logs/stdout.log` / `data/logs/stderr.log` 是否可接受？
   - 是否应该改到 `~/Library/Logs/Codex Monitor/`？

5. **安全边界**
   - 阶段 6 是否继续禁止读取 `.codex/auth.json`？
   - 是否继续禁止 HTTP quota？
   - watcher 和 smoke 输出是否仍不泄漏 JSONL 正文？

6. **实施顺序**
   - 当前计划顺序是 runtime → autostart → app bundle → UI wiring → docs → verification。
   - 请确认顺序是否合理，或者是否应先 app bundle 再 watcher。

---

## Codex 推荐结论

Codex 建议 Claude Code 如果没有阻断意见，批准以下范围进入实现：

1. `.app` wrapper
2. LaunchAgent install/uninstall/print
3. `watchdog` 实时监听 + 轮询 fallback
4. 限额数据 freshness 提示
5. 继续不做 HTTP quota，不读 `.codex/auth.json`

请 Claude Code 给出：

- 是否批准阶段 6
- 必须修改的设计点
- 可延期的优化点
- 是否允许 Codex 开始实现
