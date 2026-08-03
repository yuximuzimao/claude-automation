# 已验证练级路线索引

本目录只保存首组五开血精灵圣骑士已经实跑确认的路线规则、当前节点和小段路线。未经实跑的候选任务不得写成“已验证”。

## 新对话最小读取顺序

1. `CURRENT.md`：读取五个角色中等级/经验最低角色的当前状态、身上关键任务和下一步。
2. `RULES.md`：读取路线选择、输出格式、五开负担和接续规则。
3. 只读取与当前等级相邻的一份 `segments/*.md`，不要一次加载全部历史路线。
4. 再按需读取下一地区的Questie候选JSON、任务经验和前置数据。

`docs/NEXT_CHAT_HANDOFF.md`保留项目级交接；`docs/NEAT_SIMPLE_LEVELING_ROUTE.md`保留生成审计与项目背景，不再持续堆积逐任务实跑细节。

## 当前有效文档

- [`CURRENT.md`](CURRENT.md)：当前首组实跑节点。
- [`RULES.md`](RULES.md)：后续生成路线时必须遵守的规则。
- [`segments/20-23-stonetalon-ratchet-ashenvale.md`](segments/20-23-stonetalon-ratchet-ashenvale.md)：石爪山脉、棘齿城、灰谷东部的已验证路线和经验样本。
- [`segments/23-south-barrens.md`](segments/23-south-barrens.md)：南贫瘠之地《野猪人的内战》、血岩碎片顺交机制与《加恩的报复》的实跑记录。
- [`segments/24-25-stonetalon-capitals-tarren.md`](segments/24-25-stonetalon-capitals-tarren.md)：石爪收尾、雷霆崖/奥格瑞玛补点、幽暗城—瑟伯切尔—塔伦米尔转场及494《进攻的时机》的已验证记录。
- [`segments/25-26-hillsbrad-farms-mine-syndicate.md`](segments/25-26-hillsbrad-farms-mine-syndicate.md)：希尔斯布莱德农场、镇政厅、矿洞、辛迪加任务、经验检查点和错误修正。
- [`sessions/2026-08-02-hillsbrad-neat.md`](sessions/2026-08-02-hillsbrad-neat.md)：本次希尔斯布莱德会话的NEAT复盘、错误原因和新对话执行约束。
- [`segments/27-29-thousand-needles-west-darkcloud.md`](segments/27-29-thousand-needles-west-darkcloud.md)：千针石林西部、黑云峰、信仰试炼入口和西部补足环的已验证记录。
- [`sessions/2026-08-02-thousand-needles-neat.md`](sessions/2026-08-02-thousand-needles-neat.md)：千针石林阶段NEAT归档，包含任务分区、护送、斜坡入口、拾取机制和经验预算修正。
- [`PALADIN-COMBAT-NOTES.md`](PALADIN-COMBAT-NOTES.md)：命令圣印、洗点结果和后续惩戒天赋顺序。
- [`FLIGHT-POINTS.md`](FLIGHT-POINTS.md)：首组五开的长期飞行点状态；未列出的点一律按未开启处理。

## 文档维护规则

- 每份路线段尽量只覆盖2—4级或一个明确跨区闭环。
- 文件名包含等级段与主要区域，便于按需读取。
- 当前状态只在`CURRENT.md`维护；历史路线段不反复改写当前等级。
- 通用方法只在`RULES.md`维护；路线段只记录本段任务、机制、经验和实跑修正。
- 新发现的隐身、巡逻、楼层、洞穴入口、跟随卡点、个人拾取等机制，必须写入对应路线段，并在必要时同步到`data/observations/`。
