# 新对话工作流分流

本文件只负责把新对话引向权威入口，不复制等级、经验、任务状态或下一集编号。具体状态只能在对应`CURRENT.md`维护。

## A. 继续、修改或审计首组圣骑士路线

按顺序读取：

```text
docs/verified-routes/README.md
docs/verified-routes/CURRENT.md
docs/verified-routes/ROUTE-DESIGN-PROCESS.md
docs/verified-routes/ERROR-BOOK.md
docs/task-library/README.md
CURRENT.md指定的唯一执行稿
```

仅继续照攻略执行时，可跳过流程和错题本；只读索引、当前状态与唯一执行稿。需要调整任务、回答“是否顺路”或补路线时，必须读相关任务卡，缺资料再逐任务核验并写回任务库。

## B. 恢复视频拆解

按顺序读取：

```text
docs/video-extraction/README.md
docs/video-extraction/CURRENT.md
CURRENT.md指定的上一集检查点
```

逐集阶段只提取视频事实；不得混入当前五开路线判断。下一集编号、BVID和进度只以视频`CURRENT.md`及机器检查点为准。

## C. 第53集完成后的证据整合

唯一入口：

```text
docs/video-extraction/POST-EXTRACTION-PLAN.md
```

历史35—55优化器材料位于`docs/analysis/`和`data/routes/horde/blood-elf/`，仅作候选、差集和机制证据，不得覆盖当前实跑路线或任务库结论。

## D. 死亡骑士55—80任务母版

按顺序读取：

```text
README.md
docs/DK_55_80_WORLD_TASKS.md
data/routes/dk-55-80-world-tasks.html
```

`docs/analysis/2026-08-08-northrend-daily-quests-unverified-source.md`只是用户提供的待核验线索；其中任务名、坐标、前置和奖励未经验证，不能直接写入正式母版。

## E. 恢复 Route Atlas / 地图路线 / 任务知识图谱工作

先读无日期长期总规则，再按任务需要读取日期化阶段索引与专项文档：

```text
docs/ROUTE_ATLAS_RULES.md
docs/analysis/2026-08-14-route-atlas-session-decision-index.md
docs/analysis/2026-08-14-route-atlas-cluster-incremental-insertion-method.md
docs/analysis/2026-08-14-zangarmarsh-route-version-index.md
```

若继续当前首组的赞加执行，先以`docs/verified-routes/CURRENT.md`指定的当前执行稿为唯一玩家路线；不要从从零复用版自行剪枝。

若正在继续赞加沼泽从零复用版设计，再读：

```text
docs/analysis/2026-08-14-zangarmarsh-complete-task-universe-audit.md
docs/analysis/2026-08-14-zangarmarsh-final-reusable-route-v1.md
data/routes/zangarmarsh-final-reusable-route-preview.html
```

`2026-08-12-route-atlas-quest-knowledge-graph-concept.md`保留最初需求来源；`2026-08-12-route-atlas-v1-contract.md`保留Questie/前端数据边界；`2026-08-13-route-atlas-optimization-framework.md`与mother-model/global-model文档保留路线计算理论与标签/关系设计。永久方法发生冲突时以`docs/ROUTE_ATLAS_RULES.md`为准；日期化决策索引、增量方法和版本索引用于恢复形成过程与地图特定细节。

当前Route Atlas已经不是“仅设计提案”：赞加已完成R1–R71历史快照、完整任务宇宙审计、从零复用路线、最终整图动态审计和HTML工作台。旧exact/CP-SAT/MIP/solver只作为对照/异常检测/局部成本参考，不再直接生成玩家路线。
