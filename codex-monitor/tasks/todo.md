# Codex Monitor 待办

## 当前阶段

Claude Code 已正式放行并已完成：

- 阶段 0：项目初始化
- 阶段 1：`reader_codex.py`

当前状态：

- 第一版已封板（2026-06-02）：本地 JSONL 读取、近 30 天聚合、Top 项目、tkinter 浮窗、折叠态、macOS `.app` wrapper、LaunchAgent plist 生成和刷新 fallback 已完成。
- 代码质量：/simplify 通过 — 提取 `reader_common.py`、单次文件 open、`dataclasses.replace`、去 WHAT 注释（27/27 测试，2026-06-01）。
- 封板验证：`python3.13 -m unittest discover -s tests -v`、`python3.13 -m compileall app tests`、`python3.13 main.py --smoke-aggregate` 均通过（2026-06-02）。

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
