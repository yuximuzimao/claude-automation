# Codex Monitor

项目中文名：用量监控软件

## Session 启动
1. 读 `tasks/todo.md` — 确认当前阶段和待办
2. 读 `docs/INDEX.md` — 所有规则和安全边界的权威入口
3. 若要修改代码、数据口径、UI 行为或运行边界，先运行基线验证：
   - `python3 -m unittest discover -s tests -v`
   - `python3 -m compileall app tests`

## 规则文档（渐进式，按需加载）
| 文档 | 加载时机 |
|------|----------|
| `docs/INDEX.md` | 每次 session 启动、修改数据口径或安全边界前 |
| `tasks/todo.md` | 每次 session 启动、开始/结束阶段任务时 |
| `tasks/lessons.md` | 记录新坑位或迁移稳定经验时 |

## 教训沉淀流程
- `tasks/lessons.md` — Session 级新发现，先记这里
- `docs/INDEX.md §7` — 稳定后迁入，不在两处重复维护

## 相关项目
- `../docs/codex-handoff/` — Codex 与 Claude Code 对本项目计划、复审、绿灯的协作记录
- `/Users/chat/.codex/sessions/` — Codex 本地 JSONL 数据源，只读
- `/Users/chat/.claude/projects/` — Claude Code 本地 JSONL 数据源，只读；UI 和 smoke 路径不得全量同步扫 3.9GB 历史日志

## 目录说明
| 目录 | 用途 |
|------|------|
| `app/` | 纯 Python 应用代码，reader、模型、聚合和后续 UI 分层放置 |
| `tests/` | 单元测试与脱敏 fixture，不放对话正文 |
| `docs/` | 项目规则、数据口径、安全边界 |
| `tasks/` | 当前待办与临时教训 |
| `data/` | 结构化持久状态，例如窗口位置或后续增量索引；禁止放日志和临时文件 |

## 安全边界
- MVP 不读取 `.codex/auth.json`，不请求 `wham/usage`。
- 只读本地 JSONL；不修改 `.codex/sessions` 或 `.claude/projects`。
- 不把历史对话正文写入 UI、日志、测试快照或调试输出。
- 错误输出只包含文件路径、行号、错误类型，不输出整行 JSONL。
- UI 运行使用 `python3.13 main.py --demo` 或 `python3.13 main.py --ui`；当前 `python3` 可能缺 `_tkinter`，只用于测试和 smoke。
- tkinter 主线程不得执行 JSONL 读取、聚合或全树 mtime 扫描；自动刷新必须后台执行、合并并节流。
