# Codex Monitor 最终审查疑问点

**发起方：** Codex  
**请求方：** 用户  
**请求审查方：** Claude Code  
**时间：** 2026-06-02T10:59:51+08:00  
**项目：** `codex-monitor`

## 背景

用户说明：Claude Code 已重新对齐实际需求并修改前端，用户当前满意前端。Codex 做最终审查时提出了几个疑问点，但用户提醒其中一些可能正是用户要求的产品口径，例如“本月”改为“近 30 天”是用户认为更合理的方案。

因此本文件不是要求 Claude Code 按 Codex 的旧判断回滚，而是请 Claude Code 确认这些点分别属于：

- 用户明确要求，保持现状；
- Claude Code 有意设计，保持现状并补文档/测试；
- 非预期回归，需要修复。

## 已确认的用户口径

### 1. “本月”改为“近 30 天”

Codex 不再把这个作为问题。用户已明确说明：从自然月“本月”改为滚动“近 30 天”是用户认为更合理的方案。

建议 Claude Code 只需确认 UI 文案、README 和 `docs/INDEX.md` 是否全部统一为“近 30 天 / 30天”，避免代码是 rolling 30 days 但文档仍写“本月/月度”。

## 需要 Claude Code 确认的点

### 1. watcher 刷新范围：近 30 天重算是否是用户要求？

位置：

- `codex-monitor/main.py`
- `codex-monitor/app/runtime.py`
- `codex-monitor/README.md`
- `codex-monitor/docs/INDEX.md`

Codex 观察：

- 文档曾写 watcher 触发应类似 `modified_since=time.time()-300` 且 `max_files=50`，避免因文件变化触发大范围扫描。
- 当前 `main.py` 实际 runtime factory 使用 `incremental_window_seconds=31 * 86400`，且 `claude_max_files=args.claude_max_files`，默认 200。
- 在当前机器上实测：
  - 近 30 天/200 文件重算 `_load_aggregate` 约 2.67 秒；
  - 5 分钟/50 文件约 0.24 秒，但会导致月度/近 30 天总量只剩局部数据，不能直接替代。
- 当前 `python3.13` 环境没有 `watchdog`，实际走 5 秒轮询 fallback；轮询 mtime 本身约 0.05 秒，但发生变化后的聚合重算在 Tk 主线程执行。

请 Claude Code 判断：

- 这是用户要求“保持近 30 天视图准确”的有意取舍，接受刷新时短暂卡顿；
- 还是应该保留近 30 天口径，但把文件变化后的重算移到后台线程，避免 Tk 主线程卡顿；
- 或者应该做增量缓存/索引，既保留近 30 天口径，又避免重扫。

### 2. `data/state.json` 是否应进入 Git？

位置：

- `codex-monitor/data/state.json`
- `codex-monitor/.gitignore`

Codex 观察：

- `data/state.json` 保存本机窗口位置和折叠状态，例如当前坐标 `x=2181, y=403`。
- `.gitignore` 当前只忽略 `__pycache__`、`*.py[cod]`、`.pytest_cache/`，没有忽略 `data/state.json`。
- `data/` 当前未跟踪；如果最终执行宽泛 `git add codex-monitor`，会把本机窗口位置提交。

请 Claude Code 判断：

- 是否按用户要求要把默认窗口状态提交为初始状态；
- 如果不是，建议忽略 `data/state.json`，只保留 `data/.gitkeep` 或空目录策略。

### 3. `.app` launcher shell quoting 是否需要修？

位置：

- `codex-monitor/app/packaging.py`

Codex 观察：

- launcher 当前生成：
  - `cd {project_dir}`
  - `exec {python_executable} main.py --ui`
- 当前默认路径 `/Users/chat/claude/codex-monitor` 和 `python3.13` 不含空格，因此可运行。
- 但如果未来项目路径或 Python 可执行路径含空格，`.app` 会启动失败。

请 Claude Code 判断：

- 这是可接受的本机固定路径假设；
- 还是应该用 `shlex.quote()` 做稳健性修复，并同步更新测试。

### 4. `session_path` fallback 在 `cwd=/Users/chat` 时是否需要防误判？

位置：

- `codex-monitor/app/aggregate.py`

Codex 观察：

- `_project_from_session_path()` 会把 `.claude/projects/-Users-chat-claude-codex-monitor` 相对 `cwd=/Users/chat` 解成 `claude-codex-monitor`。
- 当前真实抽样未发现这个假项目进入 Top 结果，且 `inferred_project` fallback 通常能兜住。
- 但这是可构造边界，建议加测试或只在解出的目录存在 `CLAUDE.md` 时接受。

请 Claude Code 判断：

- 当前用户场景是否无需处理；
- 还是作为低成本防御修掉，避免未来出现 `claude-*` 假项目。

## Codex 已跑验证

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall app tests
python3 main.py --smoke-aggregate
python3.13 -m unittest discover -s tests -v
python3.13 -m compileall app tests
python3.13 main.py --smoke-aggregate
```

结果：

- 单元测试：27/27 通过；
- 编译：通过；
- smoke aggregate：输出结构化 token 摘要，未暴露对话正文。

## Codex 建议的处理优先级

1. 先由 Claude Code 确认第 1 点：近 30 天准确性 vs 刷新性能，这属于产品口径和体验取舍。
2. 第 2 点建议尽快处理，避免提交本机状态。
3. 第 3、4 点是稳健性问题，若当前要快速收尾，可以放到 follow-up；若要最终交付质量更稳，建议顺手补测试修掉。
