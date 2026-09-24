# 已验证路线索引

本目录只保留**当前恢复入口、仍有效的路线设计SOP/错题本，以及后续可能复用的已验证路线**。已经被替代的执行稿、旧方案、一次性分析和阶段NEAT统一进入 `../archive/`。

## 当前执行入口

- [`CURRENT.md`](CURRENT.md)：当前等级、位置、任务状态和唯一恢复点。继续当前项目先读它。
- Route Profile正式路线数据：`../../data/route-profiles/`。
- 当前Route Atlas派生数据：`../../data/generated/route-lifecycle/`（由现役owner生成，不是业务真源）。
- 当前Route Atlas正式页面：`../../data/routes/route-atlas-workbench.html`；纯文本玩家页：`../../data/routes/player-view/`。
- 旧聚合`workbench-routes.json`只在`../archive/generated/route-atlas/`保留为历史证据，不参与当前生成链。
- 最新阶段NEAT：[`../archive/neat/2026-09-17-route-lifecycle-stage8-and-dk-live-anchor-neat.md`](../archive/neat/2026-09-17-route-lifecycle-stage8-and-dk-live-anchor-neat.md)，记录Stage 1–7闭合、Stage 8 XP收口恢复点、Stage 4当前两条业务blocked的真实含义，以及本轮地狱火DK实跑唯一续接锚点。
- 上一阶段NEAT：[`../archive/neat/2026-09-16-route-lifecycle-sop-validation-handoff-neat.md`](../archive/neat/2026-09-16-route-lifecycle-sop-validation-handoff-neat.md)，记录Route Lifecycle SOP逐stage验证入口、Stage 1–3实现候选状态、Stage 3循环验证纠偏及恢复纪律。
- 更早历史统一从[`../archive/README.md`](../archive/README.md)按日期/主题定向查找，不在当前入口维护长链索引。

## 仍有效的路线与支撑文档

- [`VETERAN-LEVELING-BACKBONE.md`](VETERAN-LEVELING-BACKBONE.md)：50—80地图主轴与老手路线宏观参考。
- [`ZANGARMARSH-V2.md`](ZANGARMARSH-V2.md)：赞加沼泽下一批从零复用权威骨架。
- [`segments/`](segments/)：已经通过实跑、后续仍可能复用的路线段。
- [`ROUTE-DESIGN-PROCESS.md`](ROUTE-DESIGN-PROCESS.md)：真正新建、重算或系统修订路线时才加载的SOP。
- [`ERROR-BOOK.md`](ERROR-BOOK.md)：重复失败模式和发布前对抗复查；只在生成/修订/审计时定向加载。
- [`FLIGHT-POINTS.md`](FLIGHT-POINTS.md)：首组已确认飞行点与最近明确交通状态。
- [`PALADIN-COMBAT-NOTES.md`](PALADIN-COMBAT-NOTES.md)：圣骑士战斗、天赋、雕文与圣契记录。
- [`DK-COMBAT-NOTES.md`](DK-COMBAT-NOTES.md)：当前兽人双手鲜血DK的种族/流派决定，以及已冻结的精确天赋、分等级雕文和70级武器附魔切换流程。

## 历史资料

历史总入口：[`../archive/README.md`](../archive/README.md)。

旧NEAT、旧执行版本、R1—R71插入快照、求解器形成过程、废弃候选路线和视频历史都不再列在本目录。需要复盘某一阶段时按日期/关键词进入archive定向查，不批量加载整个历史库。

## 文档维护规则

1. 当前执行入口只能有一份：`CURRENT.md`。
2. 新版本完成玩家视角可执行性复审后才能替换当前入口。
3. 仍然可信、以后会复用的路线可留在本目录；已经被替代且只剩考古价值的版本移入 `docs/archive/`。
4. 用户实跑反馈只在本目录保留当前执行记录；需要写回长期事实/路线/规则时统一交给`ROUTE-DESIGN-PROCESS.md`分类，本索引不再维护第二套归属规则。
