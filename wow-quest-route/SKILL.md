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
| `lib/simple_route.py` | 共用单页渲染、首组圣骑士路线、任务详情和距离反馈 | 修改页面结构或首组参考路线时 |
| `lib/world_builder.py` | 按角色配置生成圣骑士/死亡骑士全区域候选任务库 | 修改种族职业过滤或区域候选时 |
| `lib/world_review.py` | 将死亡骑士55—80全任务合并为当前样式单页 | 修改打金任务母版时 |
| `data/route-specs/simple-leveling-route.json` | 首组圣骑士1—55实跑参考与历史1—80阶段 | 调整首组任务顺序、炉石或实跑路段时 |
| `data/journey/current-paladin.json` | 当前账号级日志中最新角色条目的脱敏历程 | 对比实跑顺序或继续追加历程时 |
| `data/journey/2026-07-31-account-journey-analysis.md` | 6—20级历程、保存点差异、长空档与放弃任务分析 | 复盘本轮死亡和路线问题时 |
| `data/journey/account-container-audit.md` | Questie账号级容器、`char`条目和脱敏边界 | 再次导入账号级日志时 |
| `data/observations/blocked-tasks.json` | 无法进入、无法接交、服务器位面异常任务 | 用户反馈阻断时必须更新 |
| `data/observations/fivebox-task-types.json` | 五开共享/个人操作实测 | 用户反馈任务行为时 |
| `data/routes/dk-55-80-world-tasks.html` | 当前死亡骑士主任务母版 | 审阅55—80全任务覆盖时 |

## CORE FLOWS

### 首组圣骑士参考页
`Questie ZIP/目录 → 读取人工 route spec → 补全前置、坐标、距离档位和补经验清单 → 输出 simple-leveling-route.html`

### 死亡骑士打金母版
`Questie ZIP/目录 → death-knight角色与阵营过滤 → 65个可用区域候选JSON → 选择出生链及55—80级可执行任务 → 按接取/目标/交付整理 → 输出 dk-55-80-world-tasks.html + 内部归档`

### 实测修正
`用户异常记录 → blocked-tasks/lessons/人物历程 → 修正任务或地图步骤 → 重新生成 → 下一组死亡骑士复跑验证`

### 人物历程
`账号级 QuestieConfig.char[*].journey → 脱敏接取/完成事件 → 与候选路线对比 → 定位回头路和遗漏`

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
