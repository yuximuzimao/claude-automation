# 2026-08-18 北风飞行时点纠错 + 龙骨全任务打标 + HTML发布 NEAT

## Situation

- 北风步骤57原文把“Transitus Shield乘系统航线返回琥珀崖”继续写成“落地后直接转乘博古洛克”，但博古洛克飞行点要抵达下一Hub后才开启。
- 这类错误不仅影响交通时间，还可能改变被迫陆路经过的任务Hub，因此必须同时复查沿途可接任务，而不是只改一句文案。
- 同轮需要检查北风和下一张龙骨荒野是否存在同类“目的地飞行点尚未开启却使用系统航线”的错误。
- 用户要求在修好HTML后，对下一张龙骨荒野全部任务按现行任务剔除优先级规则逐个打标。

## Action

1. 新增`scripts/audit_route_atlas_flight_state.py`，按路线时点重放`opened_flight_points`，把玩家文案中的系统鸟/系统航线与`taxi` transport一起审计；目的地必须在该飞行边发生前已经开启。
2. 修正北风`workbench-routes.json`：
   - Transitus Shield→琥珀崖仍为系统航线；
   - 琥珀崖→博古洛克改为骑马北上；
   - 博古洛克抵达后再开启飞行点；
   - point transport、步骤标题、步骤摘要和玩家动作文字同步修正。
3. 新增`scripts/audit_borean_amber_bogorok_corridor.py`，把琥珀崖→博古洛克强制陆路边与有效Borean foundation任务起点做走廊复查，并结合当前时点前置/路线调度状态筛选真正可插任务。
4. 沿途复查确认没有新漏项：
   - 《攻击！》《亡者的尊严》《让他们安息》虽然会经过接取NPC附近，但必须先在博古洛克接《钢腭的车队》，不能提前接；
   - 《学习沟通》本来就在后续《国王姆嘎姆嘎》自然链；
   - 最终`outstanding_interior_task_starts=0`。
5. 把本次复发追加到`ERROR-BOOK.md`错题006，并把飞行时点审计器加入Route Atlas发布门禁。
6. 重新估时并重建唯一`data/routes/route-atlas-workbench.html`。
7. 龙骨荒野任务事实仍以应用Questie修正层后的`dragonblight-task-foundation.json`为真值；旧`dragonblight-task-universe.json`的163条raw/superseded导出不能用于规划。但用户进一步明确：P级打标只应覆盖“最终实际可能被选择”的任务，而不是foundation全部266张primary候选。
8. 因此新增`scripts/build_dragonblight_removal_priority_tags.py`后又完成一次用户批准的口径迁移：
   - effective foundation里符合`include_*`且非副本的世界候选为147张；
   - 扣除当前北风→龙骨入口互斥的11979《牦牛人和牛头人》；
   - 扣除因北风唯一前置11916《地狱咆哮的勇士》已正式删除而不可解锁的12033《萨鲁法尔的信》；
   - 12791《魔法王国达拉然》仍保留，因为它本身可用，只是当前路线暂未选择；
   - 最终锁定**145张当前可用任务池**，只对这145张做P级打标与后续筛选。
9. 锁可装备奖励、升级阶段直接金币、多物品掉落/拾取、当前145池内的龙骨后续链与任务自身估时；多数量任务按现行规则进入P1—P4，A/B/C按有价值后续数量细分；尚未规划的下一地图不投机计入链价值；本轮只打标，不自动删除龙骨正式路线。
10. 直接金币核对仍覆盖16个P候选及其龙骨内下游闭包所需事实；80级XP折算金币不算“升级阶段直接金币”。

## Result

- 飞行状态审计：
  - 北风：4段系统航线，未开目的地违规0，未知目的地0；
  - 龙骨：3段系统航线，未开目的地违规0，未知目的地0。
- 琥珀崖→博古洛克陆路走廊：任务起点初筛33个，其中内走廊27个、已在后续正式路线调度13个、真正未覆盖且当时可接0个；无需新增任务步骤。
- 北风整图估时仍为751.3分钟中心值（609.2—894.0），67步；交通修正没有造成整图预算级变化。
- 龙骨当前可用任务池145张均有逐任务记录：
  - P候选16张；
  - P1=0；P2=7；P3=8；P4=1；
  - A=5；B=3；C=8；
  - 其余129张均明确标记为非P候选及原因；
  - 11979/12033不再进入打标池，12791仍保留在可用池；
  - 正式龙骨路线未因本轮打标自动删除任务。
- 生成/锁定：
  - `data/route-atlas/dragonblight-task-card-universe.json`
  - `data/route-atlas/dragonblight-priority-money-needed.json`
  - `data/route-atlas/dragonblight-removal-priority-tags.json`
  - `data/route-atlas/dragonblight-task-attribute-locks.json`
  - `data/route-atlas/dragonblight-removal-decision-locks.json`
  - `docs/analysis/2026-08-18-dragonblight-removal-priority-tags.md`

## Innovation / Reuse

- 飞行点不再只作为“已知总表”检查，而是成为按路线时点重放的状态机；玩家文案和transport元数据必须同时通过门禁。
- 任何交通纠错只要把原本的系统移动变成陆路，就必须重新做一次“强制陆路走廊任务起点复查”，但要结合前置状态和已调度路线，避免把后续任务误报成新漏项。
- 任务事实必须来自effective foundation，但P级打标池还要再经过“当前方案真正可用”过滤；不能把foundation全量primary候选等同于最终选择池，也不能从raw/superseded导出反推数量。
- P级是独立优化决策层：基础任务事实锁与P级决策锁分开，先锁145个当前可用任务，再决定是否删除；未来若龙骨P2开始反向优化，直接从当前145池锁继续。
