# NEAT阶段归档：2026-08-17 Route Atlas优化规则统一、动态交通与时间基准

状态：本阶段完成北风实跑反馈后的Route Atlas路线规则、玩家文案规则、动态飞行网络、步骤粒度、副本边界、路线估时/实跑对比和长期目标基准的统一审查。当前首组仍在北风苔原，下一次从Route Atlas第48步“蓝玉营地第一轮 + 悬崖异常”继续；本NEAT只归档任务路线项目本轮工作，**未读取、修改或整理视频拆解工作流及另一个窗口正在产生的视频文件**。

## N — 当前状态

- 当前唯一主线仍是首组五个血精灵圣骑士从68继续升到80。
- 最新五号状态以`docs/verified-routes/CURRENT.md`为真值：`72级20487 / 71级1537597 / 71级1535479 / 71级1536418 / 71级1532033`，最低号71级`1532033`。
- 北风Route Atlas第47步已结束；下一次从第48步“蓝玉营地第一轮 + 悬崖异常”继续。
- 北风从零复用路线当前为221个几何点、68个玩家逻辑步骤；龙骨从零路线为193个几何点、51个玩家逻辑步骤。赞加43点/13步、纳格兰14点/4步，四张正式地图均显式维护`stepGroups`。
- 当前唯一正式执行页仍为`data/routes/route-atlas-workbench.html`。
- 路线时间观测统一保存到`data/observations/route-timing-runs.json`。诺森德68→80老手最快实测约14小时（840分钟）被记录为本阶段**最终长期优化目标基准**；“老手几乎不做刷怪后拾取任务物品”仍只是用户推测，不视为已确认事实。

## E — 本轮证据、规则审计与修正

### 1. 永久规则入口补齐时间规则

发现`docs/rules/timing-and-benchmarking.md`已经承担正式永久规则，但项目最小上下文入口仍不完整：`docs/rules/README.md`能路由到它，`SKILL.md`和`docs/INDEX.md`却没有独立列出。

已统一：

- `SKILL.md` ENTRY MAP新增`timing-and-benchmarking.md`，并新增`data/observations/route-timing-runs.json`入口；Route Atlas专项DO FIRST也固定加载优化规则＋时间规则，核心流程在路线数据/步骤审计后增加“重算受影响步骤/整图时间”；
- `docs/INDEX.md`永久规则表新增时间规则，数据层把`data/observations/`统一描述为“实跑观测层”，覆盖五开机制、阻断、路线墙钟和长期目标；
- `route-atlas-optimization.md`与`route-atlas-ui-and-assets.md`增加对`timing-and-benchmarking.md`的明确交叉引用，避免只改路线/UI却漏掉时间模型；
- `docs/rules/README.md`继续作为唯一永久规则总入口，不新增第二个规则入口；
- 新增`tests/test_rule_routing.py`：自动枚举`docs/rules/*.md`子规则，要求每个永久规则都同时能从`SKILL.md`、`docs/INDEX.md`和`docs/rules/README.md`找到，防止以后再出现“规则文件存在但入口漏挂”。

### 2. 14小时长期目标与永久方法规则重新分层

发现时间规则正文一度直接硬编码“诺森德68→80约14小时”和“可能几乎不做掉落拾取任务”这类具体阶段数据，这与`state-and-validation.md`中“rules只保存长期方法/产品契约，不保存某次目标数字和阶段事实”的边界冲突。

已统一：

- 具体14小时目标只以结构化真值保存在`data/observations/route-timing-runs.json.long_term_targets`；
- `docs/verified-routes/CURRENT.md`和`VETERAN-LEVELING-BACKBONE.md`可以引用当前长期目标；
- `timing-and-benchmarking.md`只规定“外部长期基准如何保存、如何与地图预测分离、推测不能升级为硬规则”，不再硬编码某一阶段具体数字。

### 3. 玩家任务名与任务ID契约消除旧冲突

旧长文路线曾要求“每一次任务引用都必须完整任务名＋ID”，但当前Route Atlas产品契约已经明确：玩家第一目标是快速执行，页面不能被内部定位信息污染；现有Route Atlas实际也只需要完整任务名，不需要每一次重复显示ID。

已统一为：

- 玩家可见任务引用必须至少使用完整`《任务名称》`；
- Route Atlas等紧凑执行页不要求每次重复ID；
- 如果玩家可见位置出现ID，必须与完整任务名绑定为`《任务名称》（ID）`；
- 纯ID、裸ID、用ID替代任务名继续视为发布失败；
- 结构化数据、任务卡、内部审计继续保留ID用于精确定位。

同步修正：`execution-and-mechanics.md`、`ROUTE-DESIGN-PROCESS.md`和`ERROR-BOOK.md`错题013/固定复查清单。

### 4. “攻略第一目标”与内部审计文字彻底分层

审查发现两处旧规则仍与当前第一目标原则冲突：

1. `ROUTE-DESIGN-PROCESS.md`曾要求“路线正文开头注明已完成当前状态/飞行点/错题本/候选差集/经验闭合审计”；
2. `ERROR-BOOK.md`曾要求“路线正文注明已执行错题本复查”。

这两条都会把内部证明文字重新塞回玩家攻略。

已统一为：

- 审计完成情况、候选差集、错题本复查统一写发布审计记录/NEAT；
- 玩家路线正文只保留会改变实际操作的动作、特殊机制、跳过条件和具体回访点；
- 不允许为了“证明我们审过”而向玩家展示内部审计状态。

### 5. 任务知识卡职责与玩家文案职责统一

`route-atlas-ui-and-assets.md`旧条款曾允许玩家任务知识卡展示`typed relations`、Target Cluster / Spatial Instance、numeric features和当前路线编排理由，与“玩家页只放执行信息”矛盾。

已改为：

- 玩家可见知识卡只展示任务特殊机制、地形、任务物、掉落/刷新、失败风险和必要时间提示；
- typed relations、Target Cluster、Spatial Instance、numeric features、路线编排理由保留在后台事实/审计层；
- 不因为前端隐藏而删除后台数据，但也不因“可审计”而直接暴露给玩家。

### 6. 时间展示、内部成本模型和实跑精度统一

已确认并统一以下契约：

- 每个玩家逻辑步骤/自然任务块必须有clean baseline中心估时与合理区间；整段/整图必须有总时间；
- 内部估时按`T_move + T_objective_service + T_accept_turnin + T_wait + T_special`分解；玩家HUD默认只显示本段总预计与区间，不把所有内部成本拆解塞给玩家；
- 右上状态卡没有任何“炉石与时间/当前状态”小标题，直接炉石一行、预计时间一行；有可靠实测才显示实测行；
- `route-timing-runs.json`新增`recording_contract`，明确`exact / approximate / journey_derived / mixed`等时间精度可以被保存；用户只能记录大致起止时间时也保留，不伪装成秒级精度；
- 局部实测必须写清scope，不能冒充整图；actual与baseline只在同端点下直接比较。

### 7. 动态飞行网络规则确认已跨文档闭合

本轮复核确认“系统飞行点不是静态最终集合，而是RouteState中的动态网络”已经在以下层级保持同一语义：

- `route-atlas-optimization.md`：`opened_flight_points`是RouteState硬状态；新开点后重放未执行后缀交通；
- `execution-and-mechanics.md`：每个任务/任务块使用该时点已开启飞行点判断交通；
- `state-and-validation.md`：裁剪/重排后从受影响点向后重放动态交通；
- `ROUTE-DESIGN-PROCESS.md`：阶段2按任务时点重放飞行网络，发布门禁逐条检查“已经可飞但仍骑/绕Hub”；
- `ERROR-BOOK.md`错题006：记录北风复发及根因，禁止只在开点瞬间检查一次。

当前统一含义：个人飞行坐骑仍不参与当前诺森德路线优化；系统飞行点、炉石、任务脚本交通必须按实际时点参与完整墙钟比较。

### 8. 其它关键优化规则复核结果

本轮同时对以下已形成规则做了交叉核对，未发现新的语义冲突：

- **玩家逻辑步骤**：几何点与玩家步骤分离；正式地图必须显式`stepGroups`；数字只作过长报警，不设机械硬上限。
- **五开待实测**：未知共享/个人机制用独立`fivebox_check`；确认后先写observations，再按是否改变操作转普通备注并移除黄色标记。
- **副本边界**：当前五开户外升级Route Atlas排除`is_dungeon`/raid；只有用户明确开启专项副本路线才纳入。
- **随机掉落**：类型只作为先验，逐任务比较真实边际墙钟；14小时老手基准不能反推“所有掉落任务都删”。
- **当前路线 vs 从零路线**：首组已完成动作只影响当前状态/局部执行，不删除下一批从零路线知识。
- **路线发布**：任务结构、玩家可执行性、攻略第一目标、全图几何和技术测试分别验收，不能互相代替。

### 9. 最终一致性与技术门禁

本轮收尾重新执行：

- 永久规则路由测试：自动枚举6个`docs/rules/`子规则，确认均可从`SKILL.md`、`docs/INDEX.md`、`docs/rules/README.md`进入；
- 规则边界断言：`timing-and-benchmarking.md`不再硬编码14小时/840分钟；旧“路线正文写审计证明”和旧“每次任务引用必须显示ID”冲突文本已退出活跃规则；
- JSON解析：`route-timing-runs.json`与`workbench-routes.json`正常；CURRENT已指向本NEAT；
- `scripts/build_route_atlas_workbench.py`重新构建正式HTML成功；
- `tests/test_rule_routing.py` + `tests/test_route_atlas_timing_ui.py` + Dragonblight两组现有核心测试：**22 passed**。

### 10. 视频窗口隔离

本轮明确排除了另一个窗口正在处理的所有视频工作：

- 未修改`docs/video-extraction/`；
- 未修改`../.ai-bridge/wow-video-extraction/`；
- 未修改任何`episode-*.json`/`episode-*-extraction.md`；
- 工作区若显示这些文件仍在变化，属于并行视频处理窗口，不纳入本NEAT的任务路线修改范围，也不做清理/回滚。

## A — 本阶段判断

### 1. 永久规则现在按“入口—方法—状态—观测—玩家前端—历史”分层闭合

当前推荐理解：

`SKILL/INDEX → rules/README → 对应子规则 → CURRENT/observations真值 → workbench-routes.json → route-atlas-workbench.html → NEAT/archive保留形成过程`

具体目标数字和单次实跑不再混入永久方法规则；内部审计理由也不再混入玩家执行稿。

### 2. 14小时是长期优化目标，不是首组保证时间

首组仍承担摸图、确认五开机制和发现地形/交通问题的学习成本。后续复用批次应在同口径墙钟下向14小时目标收敛；是否主要靠减少随机掉落任务，要由后续实跑对比验证，而不是先写成路线硬规则。

### 3. 后续时间记录允许粗粒度，但必须诚实标精度

用户后续只需尽量记录任务块大致开始/结束时间即可。粗粒度时间比完全没有样本更有价值；保存时标`approximate`，若Journey能给更精确端点再更新精度，不反向伪造。

### 4. 不再新增第二套“规则摘要”

本NEAT只保存本阶段形成过程。以后执行仍从`docs/rules/README.md`路由；不能从本NEAT复制一套长期规则继续双维护。

## T — 下一恢复点

1. 继续首组时先读`docs/verified-routes/CURRENT.md`，下一步仍是北风Route Atlas第48步“蓝玉营地第一轮 + 悬崖异常”。
2. 若继续路线实跑修正，按`docs/rules/README.md`加载最小规则；涉及估时/实跑效率必须加载`timing-and-benchmarking.md`。
3. 每个大任务块尽量记录大致起止墙钟和最低号等级/经验；允许`approximate`。
4. 用户反馈新飞行点/新直飞关系时，从该开点时刻向后重放所有未执行跨片区交通，不只修下一跳。
5. 用户反馈掉落/共享/地形/脚本机制时，先修当前执行局部，再写observations；跨地图长期规律才进入rules。
6. 北风完成后记录整图离图等级/经验、实际总墙钟、机会任务/未完成项，并与14小时诺森德68→80长期目标继续建立同口径分段对比。
7. 龙骨首组进入后直接使用现有51步从零路线，优先收集黄色`fivebox_check`；只修受影响局部，不重新加载全部Dragonblight历史。
8. 视频拆解继续由另一个窗口独立推进；本任务路线恢复点不得清理、覆盖或归档视频窗口的并行改动。
