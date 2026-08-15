# 魔兽任务路线永久规则索引

用途：这是本项目永久规则的唯一总入口。不要一次性读取全部规则；先判断当前任务属于哪一类，再只加载对应子文档。

当前状态、等级、任务进度和本批次局部路线不写在这里，统一读 `docs/verified-routes/CURRENT.md`。日期化 NEAT、一次性 analysis、旧候选路线统一在 `docs/archive/` 保存形成过程，不承担永久规则入口，也不属于日常默认加载范围。

## 所有工作都必须遵守的最小规则

1. 当前现场真值优先级：用户当前实测 > 最新 Questie/实跑状态 > observations/verified route > Questie 数据库 > 公共资料 > 旧路线假设。
2. 五开等级、经验和离图预算以五个角色中最低号为基准；任何“共享”都不能从击杀自动外推到拾取、点击、技能或任务物。
3. Questie 坐标是定位证据，不是道路导航。洞穴、楼层、悬崖、水下、桥梁、入口和跟随可达性必须单独审计。
4. 不按“护送/掉落/收集/低等级”等标签整类保留或删除；按真实剩余墙钟、重叠、掉率、地形、后续链和五开机制逐任务判断。
5. 自动候选、区域分类、当前任务日志都只负责召回，不能证明任务覆盖完整。
6. 玩家执行稿必须比玩家自己整理任务更省脑：一眼知道下一步去哪、做什么、什么时候离开、回哪里交。
7. 从零复用主路线和当前角色执行路线必须分离；当前角色做完任务只裁当前执行动作，不删除下一批仍需的任务知识。
8. Route Atlas 只维护一个正式 HTML：`data/routes/route-atlas-workbench.html`。地图、角色状态、版本变化都不能制造新的独立 HTML。
9. 用户实跑确认的新机制先修执行稿，再写 observations；跨地图长期有效的结论再提升为永久规则。
10. 历史经验、错误案例和一次性讨论不重复塞回永久规则；已稳定内容进入对应规则文件，临时发现只放 `tasks/lessons.md`。

## 按任务类型加载

| 当前任务 | 必读规则 | 再按需读取 |
| --- | --- | --- |
| 继续当前实跑、回答“下一步去哪” | `docs/verified-routes/CURRENT.md` | CURRENT明确指向的最近NEAT/执行稿 |
| 新建、修订、重算任务路线 | `leveling-and-selection.md` + `execution-and-mechanics.md` | `docs/verified-routes/ROUTE-DESIGN-PROCESS.md`、`ERROR-BOOK.md`、任务卡 |
| 做经验预算、任务取舍、掉落/护送价值判断 | `leveling-and-selection.md` | 当前地图任务资料、observations |
| 写玩家攻略、补任务备注、处理洞穴/道具/触发机制 | `execution-and-mechanics.md` | task-library、ERROR-BOOK |
| 裁当前角色路线、导入 Journey、做完整性/发布审计 | `state-and-validation.md` | CURRENT、Journey 文档、ERROR-BOOK |
| Route Atlas 路线数据、插入/裁剪、状态机、炉石、求解器 | `route-atlas-optimization.md` | 需要考古时定向读 `docs/archive/analysis/` 或 `docs/archive/neat/` |
| Route Atlas HTML、逻辑步骤、HUD、地图底图、离线资源 | `route-atlas-ui-and-assets.md` | `scripts/build_route_atlas_workbench.py`、地图资源 manifest |
| 视频逐集拆解 | 不读以上路线规则 | `docs/video-extraction/README.md` + `CURRENT.md` |

## 权威边界

- `docs/verified-routes/CURRENT.md`：当前角色状态与唯一恢复点。
- `docs/rules/*.md`：跨地图、跨批次长期规则。
- `docs/verified-routes/ROUTE-DESIGN-PROCESS.md`：完整路线设计 SOP，只在真正设计/修订路线时加载。
- `docs/verified-routes/ERROR-BOOK.md`：历史错误与发布前对抗复查，只在生成/修订/审计时加载。
- `docs/task-library/`：单任务可复用事实。
- `data/observations/`：当前服务器五开机制与阻断实测。
- `docs/archive/`：历史考古区；NEAT、旧候选路线、一次性analysis和视频历史都在这里，默认不参与日常加载。

新代码、文档和NEAT一律从本索引路由永久规则，不再维护其它永久规则总入口。
