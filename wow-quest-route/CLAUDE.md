# 魔兽世界任务路线

项目中文名：魔兽世界五开打金任务路线

## 当前策略（最高优先级）

- 当前唯一主线目标改为：先把首组五个血精灵圣骑士连续练到80级；死亡骑士路线暂缓，后续再重新评估。
- 50—58当前已明确为：50级安戈洛全清到约54；放弃《无人知晓的秘密》（3908）和《新的泉水》（980）两条冬泉谷远后续；54级去希利苏斯塞纳里奥要塞，只做当前等级/战力能稳定完成的任务到55；55级转奥格瑞玛北侧艾萨拉练到58；58立即进入外域。以后老手给出的“某地图到X级”默认先视为阶段检查点，必须用本地图可执行经验与首组实跑核验，不能无任务刷怪硬补数字。
- 血精灵圣骑士雕文/圣契方案已冻结，详见`docs/verified-routes/PALADIN-COMBAT-NOTES.md`。玩家路线必须显式提醒：15级首个大/小雕文槽与《审判》《力量祝福/圣疗》；20级《感知亡灵》并做拍卖行检查；30级第2大槽；40级再次拍卖行补漏；50级《复仇圣印》＋第2小槽；70级时光服新版《正义雕文》＋第3小槽；80级第3大槽并检查《致命角斗士的坚韧圣契》。最终大雕文为《复仇圣印》《正义》《审判》，26精准时复仇圣印可换奉献/驱邪；小雕文为《力量祝福》《感知亡灵》《圣疗》，禁止误用《智者雕文》。当前首组55级转艾萨拉前在奥格瑞玛补齐当前可用雕文。
- 单地图路线设计的第一目标是最少转圈、最少重复经过同一远端目标；任务原则上全部排列完成，只排除当前职业不可接、当前缺失前置且不能在本地图解锁、或多日/重复任务无法作为一次性地图清空条件的内容。
- 死亡骑士相关母版`data/routes/dk-55-80-world-tasks.html`保留为历史/后续资料，但不再驱动当前玩家路线。
- 任何接不到、进不去、交不了或服务器位面异常的任务必须记录到`data/observations/blocked-tasks.json`并跳过，不能阻塞当前圣骑士1—80升级主目标。

## Session 启动（必做，按工作流分流）
1. 读 `SKILL.md` 和 `tasks/todo.md`。
2. 视频拆解：读 `docs/video-extraction/README.md`、`docs/video-extraction/CURRENT.md` 和上一集检查点；不要运行路线生成或加载实时状态。
3. 路线继续执行：读 `docs/verified-routes/README.md`、`CURRENT.md` 和其中指定的唯一执行稿。
4. 路线生成、修订或审计：额外读 `ROUTE-DESIGN-PROCESS.md`、`ERROR-BOOK.md`、相关 `docs/task-library/` 任务卡和 `docs/INDEX.md`；只有修改代码或生成数据时才运行 `python3 cli.py --help`。
5. 攻略成稿后必须脱离原编排思路，从玩家起点冷启动复走一遍；发现问题先改执行稿和任务卡，再登记错题，不能保留错误正文等待以后解释。
6. 不得把视频第一遍事实提取与当前Questie人物状态、阵营映射或路线优化混在同一步。

## 规则文档（渐进式，按需加载）
| 文档 | 加载时机 |
| --- | --- |
| `docs/INDEX.md` | 修改解析、路线或实测修正规则时 |
| `docs/JOURNEY_EXPORT.md` | 导出或分析 Questie 人物历程时 |
| `docs/video-extraction/README.md` | 逐集视频事实提取时 |
| `docs/video-extraction/CURRENT.md` | 恢复下一集处理点时 |
| `docs/video-extraction/POST-EXTRACTION-PLAN.md` | 第53集完成后整合视频证据时 |
| `docs/verified-routes/ROUTE-DESIGN-PROCESS.md` | 继续、修订或审计玩家路线时 |
| `docs/task-library/README.md` | 复用或补充逐任务人工核验结论时 |

## 教训沉淀流程
- `tasks/lessons.md` — Session 级新发现，先记这里
- `docs/INDEX.md §6` — 稳定后迁入，不在两处重复维护

## 数据边界
- Questie 插件与 WTF 文件均为只读输入，不修改游戏文件。
- 不保存账号名、服务器名、角色名、GUID、登录信息。
- `data/routes/` 保存可复用JSON/Markdown/坐标导航HTML；`data/observations/` 保存实测修正。
- 原始 Questie 压缩包、WTF 文件与临时解析产物放工作区 `_sandbox/`，不提交。
- 视频原始帧/OCR放项目`.ai-bridge/video-epN/`，跨对话检查点放工作区根`.ai-bridge/wow-video-extraction/`。

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
