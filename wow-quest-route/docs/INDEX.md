# 魔兽世界任务路线文档索引

用途：这是项目文档导航，不承载完整永久规则，也不保存当前角色状态。Agent进入项目先读 `SKILL.md`；当前进度只读 `docs/verified-routes/CURRENT.md`；永久规则从 `docs/rules/README.md` 按需加载。

## §1 当前执行与恢复

| 需求 | 入口 |
| --- | --- |
| 继续当前首组实跑 | `verified-routes/CURRENT.md` |
| 查看已验证路线/NEAT索引 | `verified-routes/README.md` |
| 当前飞行点状态 | `verified-routes/FLIGHT-POINTS.md` |
| 圣骑士战斗/雕文/圣契 | `verified-routes/PALADIN-COMBAT-NOTES.md` |
| 当前Route Atlas执行页 | `../data/routes/route-atlas-workbench.html` |
| Route Atlas当前结构化路线 | `../data/route-atlas/workbench-routes.json` |

`CURRENT.md` 是当前等级、位置、任务状态和唯一恢复点的真值。README、CLAUDE、SKILL和永久规则不得复制当前等级/任务栏长期维护。

## §2 永久规则路由

总入口：`rules/README.md`

| 规则主题 | 文档 |
| --- | --- |
| 经验预算、地图轴、任务取舍、随机掉落/护送 | `rules/leveling-and-selection.md` |
| 玩家攻略、隐藏机制、掉落触发、五开共享、洞穴/楼层 | `rules/execution-and-mechanics.md` |
| 当前/从零路线、Journey、完整性审计、NEAT/Git边界 | `rules/state-and-validation.md` |
| Route Atlas数据层、状态机、插入/裁剪、炉石、求解器 | `rules/route-atlas-optimization.md` |
| Route Atlas HTML、逻辑步骤、HUD、地图底图/资源 | `rules/route-atlas-ui-and-assets.md` |

所有永久规则只从 `rules/README.md` 路由；禁止新增其它永久规则总入口。

## §3 路线设计与错误复查

- `verified-routes/ROUTE-DESIGN-PROCESS.md`：完整新建、重算、系统修订路线时才加载的SOP。
- `verified-routes/ERROR-BOOK.md`：历史重复错误和发布前对抗复查；路线生成/修订/审计时加载。
- `task-library/README.md`：单任务知识字段、证据和纠错写回规则。

局部现场问题不必为了“保险”一次性读完整SOP、全部错题、全部任务卡和全部永久规则；按 `SKILL.md` 路由最小上下文。

## §4 数据与证据层

1. **Questie Raw / Effective**：任务ID、前置、NPC/物体/物品、静态坐标、修正层；原始事实不被实跑覆盖。
2. **任务知识层**：`task-library/`，保存可复用机制、地形、来源与证据。
3. **五开实测层**：`../data/observations/`，保存共享/个人、阻断和服务器特定行为。
4. **Route Atlas路线层**：`../data/route-atlas/`，保存当前有效结构化路线和地图任务基础数据。
5. **人物历程层**：`../data/journey/`，只保存脱敏Journey，用于复盘接取/交付/升级，不代表移动轨迹。
6. **阶段历史层**：`verified-routes/sessions/`，保存NEAT当时状态/证据/判断；不覆盖CURRENT和永久规则。
7. **视频事实层**：`video-extraction/`，逐集保存视频事实，只有后续整合阶段才映射到当前路线。

证据冲突默认优先级：用户当前实测 > 最新Questie/实跑状态 > observations/verified route > Questie数据库 > 公共资料 > 旧路线假设。

## §5 Route Atlas

- 唯一正式HTML：`../data/routes/route-atlas-workbench.html`。
- 地图资源池：`../data/routes/maps/`。
- 工作台构建：`../scripts/build_route_atlas_workbench.py`。
- 路线数据：`../data/route-atlas/workbench-routes.json`。
- 永久路线优化规则：`rules/route-atlas-optimization.md`。
- 永久前端/地图资源规则：`rules/route-atlas-ui-and-assets.md`。

地图特定R快照、某次局部路线、某批角色等级经验和一次性异常只留analysis/NEAT，不提升为永久规则，除非明确验证为跨地图长期规律。

## §6 Journey与Questie

- 导出/脱敏说明：`JOURNEY_EXPORT.md`。
- 当前脱敏历程：`../data/journey/current-paladin.json`。
- Questie Journey位于账号级 `QuestieConfig.char[*].journey`；一个文件可能有多个角色。
- Journey记录接取、完成/交付、放弃、升级、时间戳；不记录死亡、真实移动、找怪耗时或目标进度。
- 原始Questie/WTF不提交Git；任务触发物、物体触发等不能只靠NPC任务列表推导。

## §7 视频拆解

- 方法：`video-extraction/README.md`
- 当前集恢复点：`video-extraction/CURRENT.md`
- 全集后整合：`video-extraction/POST-EXTRACTION-PLAN.md`
- 阶段NEAT：`video-extraction/sessions/`

视频逐集阶段只提取事实，不与当前首组Questie状态或路线优化混算。

## §8 历史与归档

- `verified-routes/sessions/`：首组练级/Route Atlas阶段NEAT。
- `verified-routes/segments/`：已验证历史路线段。
- `analysis/`：日期化分析、模型实验、地图特定审计和形成过程。
- `NEAT_SIMPLE_LEVELING_ROUTE.md` 等旧文档仅作历史，不作为当前入口。

历史文件只按当前问题需要读取一份或少量相关文件，禁止批量加载整个目录。

## §9 临时待办与教训

- `../tasks/todo.md`：只记录仍会改变下一步工作的事项。
- `../tasks/lessons.md`：只记录尚未确定归宿的新发现；稳定后迁入 `rules/`、ERROR-BOOK、task-library、observations或NEAT，并从lessons删除。

## §10 Git与sessions命名

- 仓库根 `/sessions/`：浏览器/账号运行时会话，敏感数据，必须Git忽略。
- `verified-routes/sessions/` 与 `video-extraction/sessions/`：项目Markdown历史，必须正常commit/push。
- 根 `.gitignore` 必须使用 `/sessions/`，不能写成会误伤子项目文档的 `sessions/`。
