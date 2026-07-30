# 魔兽世界任务路线

项目中文名：魔兽世界任务路线

## Session 启动（必做，按顺序）
1. 读 `SKILL.md` — 项目入口、文件地图和数据边界，禁止跳过
2. 读 `tasks/todo.md` — 确认当前待办和路线进度
3. 运行 `python3 cli.py --help` 确认入口可用
4. 读 `docs/INDEX.md` — 路线生成规则和置信度定义

## 规则文档（渐进式，按需加载）
| 文档 | 加载时机 |
| --- | --- |
| `docs/INDEX.md` | 修改解析、路线或实测修正规则时 |
| `docs/JOURNEY_EXPORT.md` | 导出或分析 Questie 人物历程时 |

## 教训沉淀流程
- `tasks/lessons.md` — Session 级新发现，先记这里
- `docs/INDEX.md §6` — 稳定后迁入，不在两处重复维护

## 数据边界
- Questie 插件与 WTF 文件均为只读输入，不修改游戏文件。
- 不保存账号名、服务器名、角色名、GUID、登录信息。
- `data/routes/` 保存可复用JSON/Markdown/坐标导航HTML；`data/observations/` 保存实测修正。
- 原始 Questie 压缩包、WTF 文件与临时解析产物放工作区 `_sandbox/`，不提交。

## 目录说明
| 目录 | 用途 |
| --- | --- |
| `lib/` | Questie Lua 数据解析、单区域导航和全区域候选生成 |
| `data/route-specs/` | 人工可审阅的路线步骤骨架 |
| `data/routes/` | 生成的 Markdown/JSON/坐标导航HTML与全区域索引 |
| `data/observations/` | 五开共享类型、卡点、地形和路线修正 |
| `docs/` | 规则和导出说明 |
| `tasks/` | 当前待办与临时教训 |
| `tests/` | 解析与路线生成测试 |
