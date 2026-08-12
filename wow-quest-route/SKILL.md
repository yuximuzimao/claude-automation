# 魔兽世界任务路线 SKILL.md

## DO FIRST
1. 读 `tasks/todo.md` — 确认当前工作流和待办。
2. 若用户要求继续视频拆解：只读 `docs/video-extraction/README.md`、`docs/video-extraction/CURRENT.md` 和上一集检查点；不要先加载实时路线或全部视频历史。
3. 若用户要求继续现有路线：读 `docs/verified-routes/README.md`、`CURRENT.md` 和其中指定的唯一执行稿。
4. 若用户要求生成、修订或审计路线：再读 `ROUTE-DESIGN-PROCESS.md`、`ERROR-BOOK.md`、相关 `docs/task-library/` 任务卡和 `docs/INDEX.md`，执行逐任务复核与冷启动对抗复走。
5. 代码与数据生成的核心入口：`cli.py`；纯攻略修订不先运行生成器，也不让脚本替代人工判断。

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
| `docs/verified-routes/ERROR-BOOK.md` | 漏任务、额外往返和自动候选覆盖错误的错题本 | 每次生成、修订或审计执行路线前 |
| `docs/verified-routes/ROUTE-DESIGN-PROCESS.md` | 从任务库复用、逐任务核验、成稿后对抗复走的强制流程 | 继续、修订或审计路线前 |
| `docs/task-library/README.md` | 任务卡字段、证据和纠错写回规则 | 查询已核验任务或新增任务卡时 |
| `docs/video-extraction/README.md` | 视频逐集提取方法、证据优先级与完成定义 | 处理任意视频集前 |
| `docs/video-extraction/CURRENT.md` | 已完成集、下一集和最小恢复点 | 继续视频拆解时 |
| `docs/video-extraction/POST-EXTRACTION-PLAN.md` | 全集完成后的合并、映射、优化与实跑闭环 | 第53集完成后 |
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

### 视频拆解
`导航前禁止自动播放 → 全集时长粗扫 → 任务中心/日志/剪辑处精查 → Questie校准名称与ID → 单集Markdown+JSON检查点 → 更新CURRENT并停止`

## FAILURE PATTERNS
- 不把自动区域候选、Questie区域分类或当前任务日志当作完整覆盖证明；必须执行错题本中的NPC、现场任务、任务链和差集复查。
- 不把 Questie 地图坐标当成道路导航；山、桥、洞穴和跟随卡点必须实测。
- 不把击杀共享推断到拾取、点击、技能或任务物品。
- 不按“护送、掉落、低等级”等固定任务类型整类排除；逐任务比较真实剩余路程、掉率、地形、等级差、五开机制和后续重叠。
- 不重复从零计算已核验任务；先复用任务库，发现错误时同步修改任务卡与执行稿，再在错题本保留错误原因。
- 不使用历史 RXP SavedVariables 作为当前插件或当前角色证据。
- 不直接上传或提交完整 WTF；先脱敏人物历程。
- 修正层可能改变基础数据库；生成结果必须记录 Questie 版本和来源哈希。
- 视频第一遍只提取事实；`目标(N)`不是完整任务数，剪辑缺口不得补写，任务目标完成不得误记为已交付。
- 每次只处理用户指定的一集，写独立检查点并关闭标签；不得自动开始下一集。

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
