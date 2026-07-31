# 魔兽世界任务路线 SKILL.md

## DO FIRST
1. 读 `tasks/todo.md` — 确认当前区域、版本和待验证项
2. 读 `docs/INDEX.md` — 路线规则、数据层级和置信度定义
3. 核心入口：`cli.py`

## ENTRY MAP
| 文件 | 用途 | 何时读 |
| --- | --- | --- |
| `cli.py` | 命令入口 | 运行或增加命令时 |
| `lib/questie_lua.py` | 解析 Questie 内嵌 Lua table | 数据读取失败或扩展字段时 |
| `lib/questie_source.py` | 从 ZIP/目录加载 Questie任务、中文名和WotLK经验数据库 | 更换插件来源或经验字段时 |
| `lib/route_builder.py` | 历史逐日岛路线骨架解析、数据补全和输出 | 修改旧逐日岛生成逻辑时 |
| `lib/simple_route.py` | 单页路线生成、前置闭包、地点合并和任务名着色 | 修改当前单页路线时 |
| `data/route-specs/simple-leveling-route.json` | 当前1—80地图阶段与人工审计步骤 | 调整任务顺序、炉石或实跑路段时 |
| `data/route-specs/sunstrider-isle.json` | 历史逐日岛 V1 步骤骨架 | 调整旧路线时 |
| `data/observations/fivebox-task-types.json` | 五开共享/个人操作实测 | 用户反馈任务行为时 |
| `data/routes/horde/blood-elf/` | 生成路线 | 审阅当前成品时 |

## CORE FLOWS

### 生成候选路线
`Questie ZIP/目录 → 解析任务/NPC/物体/物品/中文名/任务经验 → 读取 route spec → 补全前置、坐标、距离档位和补经验清单 → 输出 HTML + 内部归档`

### 实测修正
`用户异常记录 → observations → 调整 route spec 或任务类型 → 重新生成路线 → 保留版本`

### 人物历程
`脱敏 Questie SavedVariables → 接取/完成事件 → 与候选路线对比 → 定位回头路和遗漏`

## FAILURE PATTERNS
- 不把 Questie 地图坐标当成道路导航；山、桥、洞穴和跟随卡点必须实测。
- 不把击杀共享推断到拾取、点击、技能或任务物品。
- 不使用历史 RXP SavedVariables 作为当前插件或当前角色证据。
- 不直接上传或提交完整 WTF；先脱敏人物历程。
- 修正层可能改变基础数据库；生成结果必须记录 Questie 版本和来源哈希。

## PATHS
| 路径 | 说明 |
| --- | --- |
| `lib/` | 可复用解析与生成逻辑 |
| `data/route-specs/` | 路线步骤骨架 |
| `data/routes/` | 生成路线 |
| `data/observations/` | 实测修正 |
| `docs/` | 操作规则和导出说明 |
| `tasks/` | 待办与教训 |
| `tests/` | 自动测试 |
