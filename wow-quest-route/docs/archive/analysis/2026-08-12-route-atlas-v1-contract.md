# Route Atlas V1：已确认产品边界与 Questie 离线地图方案

状态：2026-08-12 讨论后冻结为下一张实际练级地图的首个 HTML 工作台实现合同。地狱火半岛继续作为首跑证据，不再强行作为 MVP。

## 1. 产品职责

Route Atlas 的主地图只回答三件事：

1. 下一步往哪个大方向走；
2. 到这个节点是接任务、做任务还是交任务；
3. 当前附近哪些任务属于这一趟，避免把下一趟/另一方向的任务顺手做掉而破坏路线。

主地图不负责：

- 道路级导航；
- 山路、桥梁、洞穴等精确行走路线；
- 任务机制说明；
- 目标怪/目标物的完整分布范围；
- 五开机制推断。

Questie 继续承担游戏内精确任务目标定位；Route Atlas 负责宏观顺序和方向。

## 2. 唯一前端载体

- 只做 HTML 工作台，不自动导出 PNG/JPG。
- 每次前端默认只展示当前最新路线版本。
- 历史路线、失败关系、讨论原因继续保存在后台数据/文档，不要求前端默认展示。

## 3. 主地图默认信息密度

节点只显示：

- 序号；
- 动作简写：`接任务` / `做任务` / `交任务`；
- 节点之间的大方向箭头。

默认不在地图上写具体任务操作。

点击节点后：

1. 显示该节点对应的任务清单；
2. 任务清单下可继续打开单任务卡。

## 4. 单任务卡与路线攻略严格分离

单任务卡只对应一个任务，是长期维护的知识节点。

允许包含：

- Questie 可读取的单任务事实；
- 单任务攻略备注；
- Questie 信息不足时才需要额外查询的机制、地形、操作说明；
- 来源和人工备注。

禁止包含路线版本专属描述，例如：

- “本区域共 4 个任务”；
- “进入后先沿东侧清怪”；
- “这一趟和 A/B/C 一起做”；
- “下一步去某区域”。

这些内容只能存在于路线攻略/路线节点中。

Questie 原始字段不因人工实跑而改写。人工攻略和项目修正必须与 Questie Raw 分层保存。

## 5. 数据层边界

正式结构按以下顺序：

`Questie Raw（不可变）`
→ `Questie Effective / TitanReforged 派生有效层`
→ `单任务卡 + 任务关系`
→ `路线版本/节点`
→ `HTML 工作台`

当前游戏实际使用插件：

- Questie 夜月修复版；
- Version: `11.34.0`；
- Client: `3.80.2 TitanReforged-Wotlk-ChinaRegion`；
- Locale: `zhCN`。

用户提供包：`.ai-bridge/Questie.zip`

2026-08-12 本地只读审计：

- SHA256: `3c31d28a9c18189f3e245cdfb5b806210612e66da91c3661757c363724957861`
- ZIP entries: `775`
- `Questie-WOTLKC.toc` Interface: `38002`
- `Database/Corrections/` 下发现 64 个条目/文件。
- `QuestieCorrections.lua` 明确在 `Questie.IsTitanReforged` 时叠加 TitanReforged NPC/Quest/Item fixes，并额外应用 TitanReforged blacklist。

因此不能继续把 `Database/Wotlk/*.lua` 基础表直接当成时光服最终有效任务库。

## 6. Titan 有效性原则

不要把“文件中出现 Titan 字样”当作筛选条件。

绝大多数普通 WotLK 任务会在 Titan 服务器继承有效，而不会逐条带 Titan 标识。正确语义是：

> 在 WotLK base + Questie corrections + TitanReforged fixes + Titan blacklist/条件应用之后，该记录是否对当前 TitanReforged 客户端有效。

离线解析器后续应生成派生状态，例如：

- `effective_for_titan = true`
- `effective_for_titan = false`
- `effective_for_titan = unknown`

同时保留有效性来源/原因；不得修改 Questie Raw。

首跑阶段允许少量个别 Questie/服务器差异由用户现场纠正，不要求在路线工作开始前证明所有任务 100% 无误。

## 7. Questie 离线单地图点位层：确认可行

对用户提供的 v11.34.0 包审计确认：

- NPC/Object 位置数据以区域局部 0–100 坐标保存；典型结构为：
  `spawns[zoneID] = {{x1,y1},{x2,y2},...}`。
- `QuestieMap:ShowNPC` 会遍历 `npc.spawns` 的每个坐标并绘图。
- 移动 NPC 的 `npc.waypoints` 单独处理。
- 世界地图绘制最终交给 `HereBeDragonsQuestie-Pins-2.0` 的 `AddWorldMapIconMap`。
- Questie 自身负责选择需要画的记录、图标类型和缩放；HereBeDragons 负责地图坐标定位。
- `QuestieMapUtils:IsExplored` 将 Questie 的 `x,y` 转成 `x/100,y/100` 交给 Blizzard 地图 API，再次确认坐标是区域地图归一化百分比。

因此只要底图与游戏区域地图采用同一坐标框，离线 HTML 可以原样复现 Questie 点位：

`px = left + (x / 100) * (right - left)`

`py = top + (y / 100) * (bottom - top)`

其中 `left/top/right/bottom` 是下载底图中真正对应游戏地图 0–100 坐标的有效矩形。若底图本身就是无裁切的标准区域地图，则有效矩形就是整张图。

## 8. 离线点位层的前端定位

Questie 点位层不是主路线图的默认信息主体，而是一个可切换参考层。

建议至少有：

- `路线`：默认开启；序号 + 动作 + 大方向箭头。
- `任务点位`：默认关闭或只在选中节点时开启；显示当前节点相关 NPC/Object/Mob 的 Questie spawn 点。
- `移动路线`：有 `waypoints` 的目标才显示对应折线。

这样既保留 Questie 级别的点位精度，又不会让主路线重新变成一张密密麻麻的 Questie 地图。

## 9. 推荐的 HTML 绘制方式

优先使用：

- 高清地图 `<img>` 作为底图；
- SVG/HTML absolute overlay 作为坐标层；
- 路线箭头和移动 NPC waypoints 使用 SVG；
- 可点击节点/任务点使用 HTML/SVG 交互元素。

不用把点位烘焙进位图，也不需要 Canvas 作为首选。

理由：

- 百分比坐标容易与 0–100 Questie 坐标一一对应；
- 缩放后仍保持清晰；
- 路线层、Questie 点位层可以独立开关；
- 点击节点打开任务清单/任务卡更简单；
- 改路线只改结构化数据，不需要重做图片。

## 10. 底图校准验收

每进入一张新地图只做一次底图校准：

1. 选一张清晰、无透视的区域地图；
2. 找 3–5 个分散在地图不同位置、Questie 坐标明确的固定 NPC/Object；
3. 按 0–100 线性投影；
4. 检查这些点是否都落在正确地物/NPC位置；
5. 若整体存在边距/裁切，则只调整该底图的 `map_bounds`；
6. 通过后锁定该地图底图和 bounds，不再逐任务人工校坐标。

如果 3–5 个远距离锚点同时吻合，说明该底图和 Questie 坐标系已经对齐；后续数百个 spawn 点都可以直接批量投影。

## 11. 任务关系：先保留原始可计算事实，规则后定

关系库当前先保证能计算/保存这些基础事实：

- 前置/后续任务；
- 相同接取 NPC；
- 相同交付 NPC；
- 相同目标 NPC/Mob；
- 相同目标 Object；
- 目标点云之间的距离；
- 目标点云重叠/邻近程度；
- 接交点之间的距离。

“距离多少算相邻”“同一区域如何聚类”“哪些关系足够强才应当同一趟做”等阈值，等下一张地图真正做路线时再根据实用性确定，不提前硬编码。

## 12. 首个 MVP

- 地狱火半岛：继续首跑，收集折返、误做附近任务、任务链解锁等证据，不等待工作台基建。
- 下一张首组实际进入的练级地图：作为首个 Route Atlas HTML 工作台 MVP。
- MVP 首先验证：
  1. 底图坐标校准是否稳定；
  2. 大方向箭头 + 极简节点是否足够执行；
  3. 点击节点查看任务清单是否顺手；
  4. Questie 点位参考层是否能正确复现目标 spawn；
  5. 哪些关系规则真正能防止“附近任务做错圈”。
