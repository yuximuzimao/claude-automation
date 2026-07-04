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

## 未处理问题

- [ ] **P0：项目流量归因仍需复查（2026-06-04）**
  - 现象：2026-06-04 用户没有用 AI 对鲸灵售后自动化做优化，但流量统计里仍出现售后项目消耗。
  - 已知进展：Claude 已修复过一轮，修复后一开始统计确实有变化。
  - 2026-07-03 进展：已修复 Codex 多项目弱信号打平时任意选首个项目的问题；`product-detect` 今日误归因已归入 `其他`。
  - 剩余问题：2026-06-04 下班前再次查看，仍有部分统计归因错误。
  - 下次处理方向：继续排查项目推断逻辑，重点验证是否还有工具输出、历史路径、cwd fallback、session 内容路径或中文项目名映射把无关会话误判进 `aftersales-automation`。
- [ ] **P2：售后自动化当日 token 统计继续观察（2026-06-06）**
  - 现象：此前出现过售后自动化今日 token 计算不对。
  - 2026-06-06 观察：用户反馈未再出现。
  - 处理策略：暂不改代码，连续观察数日；若复现再按项目归因链路重新定位。

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
