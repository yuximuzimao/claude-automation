# Codex Monitor 待办

## 当前阶段

Claude Code 已正式放行并已完成：

- 阶段 0：项目初始化
- 阶段 1：`reader_codex.py`

当前状态：

- 第一版已封板（2026-06-02）：本地 JSONL 读取、近 30 天聚合、Top 项目、tkinter 浮窗、折叠态、macOS `.app` wrapper、LaunchAgent plist 生成和刷新 fallback 已完成。
- 代码质量：/simplify 通过 — 提取 `reader_common.py`、单次文件 open、`dataclasses.replace`、去 WHAT 注释（27/27 测试，2026-06-01）。
- 封板验证：`python3.13 -m unittest discover -s tests -v`、`python3.13 -m compileall app tests`、`python3.13 main.py --smoke-aggregate` 均通过（2026-06-02）。
- 项目推断误分类已修复（2026-06-04）：`reader_common.infer_project_from_handle()` 按事件类型加权，跳过 Codex 工具调用/输出/token_count 噪声，扫描窗口提高到 200 行；`tests/test_reader_common.py` 已覆盖回归场景。
- UI 卡顿和高 CPU 已修复（2026-06-06）：watcher/polling 触发的聚合读取移出 tkinter 主线程，刷新中请求合并，自动刷新 60 秒节流；`.app` 进程实测空闲 CPU 0.0-0.2%，RSS 约 185-191MB；`python3 -m unittest discover -s tests -v` 43/43 通过，`python3 -m compileall app tests` 通过。
- quota 缺失值回退已修复（2026-06-26）：较新的不可显示 `rate_limits` 不再覆盖旧的可显示 quota；折叠态未知值显示 `—`，真实 `0.0` 仍显示 `0%`；`python3 -m unittest discover -s tests -v` 51/51 通过，`python3 -m compileall app tests` 和 `python3 main.py --smoke-aggregate` 通过。
- 折叠态点击灰框与 App 启动体验已修复（2026-07-03）：倒计时改为 Canvas text；`.app` 可见模式会让位/恢复隐藏 LaunchAgent，并使用单实例锁避免双开；本机 App 已重建到 `/Users/chat/Applications/Codex Monitor.app`。验证：`python3.13 -m unittest discover -s tests -v` 81/81 通过，`python3.13 -m compileall app tests main.py` 通过；LaunchAgent 运行正常，日志仅见 macOS 输入法/键盘布局警告，未见业务错误。
- 今日项目误归因已修复（2026-07-03）：多项目弱信号打平时不再按插入顺序归因到先出现的项目，改为归入 `其他`；已修复 `product-detect` 今日误显示 2100 万+ Codex token 的问题。验证：`tests/test_reader_common.py` 覆盖打平回归，`python3.13 -m unittest discover -s tests -v` 82/82 通过。
- Claude 统计和项目明细交互已修复（2026-07-08）：Claude 工具输出 / SessionStart hook 不再参与项目归因，assistant `message.id` 重复事件只统计一次；项目明细 popover 改为持久 `Toplevel` 复用，隐藏后可立即再次展开。验证：`python3 -m unittest discover -s tests -v` 89/89 通过，`python3 -m compileall app tests main.py` 通过，`main.py --ui` 已通过 LaunchAgent 重启到新代码。

## 未处理问题

- [ ] **P2：统计准确性继续观察**
  - 目标：确认 2026-07-08 的 Claude 工具输出过滤、SessionStart hook 过滤和 assistant `message.id` 去重后，项目归因和 30 天用量是否持续符合实际使用感知。
  - 触发条件：再次出现“某项目明明没处理却出现 token”或“30 天数据突变但无法用日志口径解释”。
  - 处理方向：先按 `docs/INDEX.md §6-7` 的归因链路复核 `cwd`、session path、前 200 行 text 信号、重复 assistant usage；只有无法溯源时，再考虑做更细的归因解释面板。
- [ ] **P3：日志规模增长后的性能与增量索引**
  - 目标：随着 `.claude/projects` 和 `.codex/sessions` 继续增长，保持 UI 刷新稳定、低 CPU、低延迟。
  - 触发条件：近 30 天重算明显变慢、LaunchAgent 空闲 CPU 异常、手动刷新卡顿，或 smoke aggregate 耗时不可接受。
  - 处理方向：优先设计增量索引/缓存，避免每次刷新重复解析已处理 JSONL；继续保持 UI 主线程不做 JSONL 读取或全树扫描。

## 阶段 0：项目初始化

- [x] 创建项目目录结构
- [x] 创建 `CLAUDE.md`
- [x] 创建 `SKILL.md`
- [x] 创建 `docs/INDEX.md`
- [x] 创建 `tasks/todo.md`
- [x] 创建 `tasks/lessons.md`

## 阶段 1：Codex Reader

- [x] 用脱敏 fixture 写 `reader_codex` 单元测试
- [x] 验证测试先失败
- [x] 实现 `app/reader_codex.py`
- [x] 验证单元测试通过
- [x] 增加 `--smoke-codex` 结构摘要检查
- [x] 运行 `python3 -m compileall app tests`

## 暂缓

- HTTP quota

## 阶段 2：Claude Code Reader

- [x] 用脱敏 fixture 写 `reader_claude` 单元测试
- [x] 验证测试先失败
- [x] 实现 `app/reader_claude.py`
- [x] 验证单元测试通过
- [x] 增加 `--smoke-claude` 结构摘要检查，默认使用 1 天 mtime 窗口
- [x] 运行 `python3 -m compileall app tests`

## 阶段 3：聚合层

- [x] 扩展 reader 结构化 usage event，不输出正文
- [x] 用脱敏对象写 `aggregate` 单元测试
- [x] 验证测试先失败
- [x] 实现 `app/aggregate.py`
- [x] 验证单元测试通过
- [x] 增加 `--smoke-aggregate` 结构摘要检查
- [x] 运行 `python3 -m compileall app tests`

## 阶段 4：tkinter MVP UI

- [x] 根据 Claude 勘误补 `ProjectTotal.sample_cwds`
- [x] 用纯函数测试 UI 数字格式和 tooltip 数据
- [x] 验证测试先失败
- [x] 实现 `app/ui_tk.py`
- [x] 按用户反馈补项目自描述中文名、5小时/周限额、项目今日/近 30 天/占比，并删除事件类型用途模块
- [x] 新增 `python3 main.py --demo` 假数据 UI
- [x] 新增 `python3 main.py --ui` 真实数据 UI
- [x] 运行 `python3 -m compileall app tests`

## 阶段 5：交互增强

- [x] 窗口拖拽
- [x] 窗口位置持久化到 `data/state.json`
- [x] 手动刷新按钮
- [x] 折叠/展开状态
- [x] 运行 `python3 -m compileall app tests`
- [x] 运行 `python3 -m unittest discover -s tests -v`

## 阶段 6：macOS 产品化

- [x] 修复 Claude handoff inbox JSON，并吸收阶段 6 审查意见
- [x] 新增 runtime debounce / polling fallback，watcher 刷新保持近 30 天口径并受 `--claude-max-files` 上限约束
- [x] 新增 LaunchAgent plist 生成、安装、卸载、打印命令；安装不自动执行 `launchctl`
- [x] LaunchAgent 日志改到 `~/Library/Logs/Codex Monitor/`
- [x] 新增 `.app` bundle wrapper 生成命令
- [x] `main.py --ui` 接入 watchdog 可选监听和 5 秒轮询 fallback
- [x] 更新 README / docs / tasks

## 阶段 7：UI 细节与 App 启动体验

- [x] 折叠态倒计时从嵌入 `tk.Label` 迁移到 Canvas text，避免点击后短暂灰框。
- [x] `.app` 去掉 `LSUIElement`，可见模式尝试设置 Dock 名称和图标。
- [x] `.app` launcher 使用绝对 Python 路径，避免 GUI 环境 PATH 找不到 `python3.13`。
- [x] `.app` 启动时让隐藏 LaunchAgent 让位，退出后按原运行状态恢复后台服务。
- [x] 新增 `SingleInstance` 锁，避免 LaunchAgent 和 App 双开，并让可见 App 短暂等待旧实例释放锁。

## 阶段 8：统计准确性与明细交互

- [x] Claude 项目归因只扫描真实 text 段，跳过 `tool_result`、hook 和 attachment 噪声。
- [x] Claude assistant usage 按 `message.id` 去重，避免同一响应重复累计。
- [x] 项目明细 popover 改为持久窗口复用，隐藏用 `withdraw()`，关闭才 `destroy()`。
- [x] 增加回归测试覆盖 `健身计划生成` 类工具输出误判、重复 assistant usage、快速再展开弹窗。
