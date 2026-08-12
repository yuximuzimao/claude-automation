# 视频拆解当前状态

更新时间：2026-08-12 16:01（UTC+8）

## 当前阶段

- 阶段：第一阶段，逐集事实提取。
- 已完成：第13—38集。
- 下一集：第39集。
- 本轮停止点：第38集检查点、事件JSON、509帧正式原始证据、OCR和Questie交叉审计均已完成；第39集仅从当前合集状态只读查询元数据，未打开、未截图、未处理。
- 最新NEAT归档仍为：`docs/video-extraction/sessions/2026-08-07-episode34-neat.md`；本轮未额外做NEAT归档。

## 下一集唯一入口

- 集数：39/53
- 标题：《北风苔原73》
- BVID：`BV1fdraBbE9B`
- 合集标注时长：45:09（2709秒）
- 目标检查点：
  - `/Users/chat/claude/.ai-bridge/wow-video-extraction/episode-39-extraction.md`
  - `/Users/chat/claude/.ai-bridge/wow-video-extraction/episode-39-events.json`
- 原始证据目录：`wow-quest-route/.ai-bridge/video-ep39/`

用户下次说“继续处理下一个视频”或“继续处理第39集”时，直接按`README.md`执行，不重新讨论流程，不先做路线评价，不处理第40集。

## 最小恢复步骤

1. 读`docs/video-extraction/README.md`。
2. 读本文件。
3. 读`/Users/chat/claude/.ai-bridge/wow-video-extraction/episode-38-extraction.md`。
4. 如需机器结构，再读`episode-38-events.json`。
5. 重新取得当前Chrome浏览器WebSocket地址；不要复用旧CDP地址。
6. 通过新空白标签并用`.ai-bridge/bili-open-paused-bvid.js`在导航前禁止自动播放。
7. 处理第39集，写独立检查点，更新本文件，关闭本轮B站标签，然后停止。

## 已完成集索引

| 集数 | 标题 | BVID | 时长 | 原始帧 | 检查点 |
| ---: | --- | --- | --- | ---: | --- |
| 13 | 荆棘谷 36-37 | `BV1U5ByBNEKP` | 53:13 | 129 | `episode-13-extraction.md/json` |
| 14 | 奥达曼 38 | `BV1o8vkBvEAc` | 23:13 | 104 | `episode-14-extraction.md/json` |
| 15 | 荆棘谷 39-40 | `BV1rTvmBdEqX` | 64:18 | 211 | `episode-15-extraction.md/json` |
| 16 | 荆棘谷 41 大号来复仇 | `BV1oRvpB2Euw` | 67:56 | 283 | `episode-16-extraction.md/json` |
| 17 | 荆棘谷 42-43 | `BV1sovHB4E1A` | 62:44 | 432 | `episode-17-extraction.md/json` |
| 18 | 荆棘谷 44 终于有钱学大马了 | `BV1YBvHBzE2f` | 47:37 | 538 | `episode-18-extraction.md/json` |
| 19 | 加基森 45-46 | `BV1hxveBTEek` | 45:50 | 303 | `episode-19-extraction.md/json` |
| 20 | 菲拉斯 47-48 | `BV1eFiTBAENF` | 53:48 | 325 | `episode-20-extraction.md/json` |
| 21 | 灼热峡谷49-51 | `BV1CziKB2EaC` | 55:21 | 289 | `episode-21-extraction.md/json` |
| 22 | 安戈洛环形山 52 | `BV1p2iMBDEMw` | 01:02:06 | 430 | `episode-22-extraction.md/json` |
| 23 | 安戈洛环形山 53-54 | `BV1mGvdBsENa` | 48:56 | 441 | `episode-23-extraction.md/json` |
| 24 | 西瘟 54-56 | `BV1jiirBiE2L` | 01:05:09 | 775 | `episode-24-extraction.md/json` |
| 25 | 东瘟57-58 | `BV1iVi7BPEtL` | 47:50 | 826 | `episode-25-extraction.md/json` |
| 26 | 地狱火半岛59-60 | `BV12XijBmEhq` | 53:41 | 533 | `episode-26-extraction.md/json` |
| 27 | 地狱火半岛 城墙 61 | `BV1j8ijBeEfZ` | 46:29 | 750 | `episode-27-extraction.md/json` |
| 28 | 地狱火半岛 62-63 | `BV17uqcBdEWu` | 01:20:11 | 1007 | `episode-28-extraction.md/json` |
| 29 | 地狱火半岛 64 | `BV1MtqcBCEZs` | 38:48 | 511 | `episode-29-extraction.md/json` |
| 30 | 赞加沼泽 65 | `BV1hHqcBmEoY` | 43:17 | 530 | `episode-30-extraction.md/json` |
| 31 | 纳格兰 66 | `BV1kDiyBXEc7` | 54:22 | 684 | `episode-31-extraction.md/json` |
| 32 | 纳格兰 67 | `BV14aiSB3EJ6` | 59:34 | 566 | `episode-32-extraction.md/json` |
| 33 | 纳格兰 68 | `BV1dziXBAEjY` | 01:13:45 | 790 | `episode-33-extraction.md/json` |
| 34 | 北风苔原 69-70 | `BV11qiQB1ET2` | 01:04:02 | 730 | `episode-34-extraction.md/json` |
| 35 | 北风苔原 70.9 | `BV1EQiQBKEVC` | 01:12:12 | 564 | `episode-35-extraction.md/json` |
| 36 | 北风苔原 71 | `BV1k46oBaEJX` | 01:06:43 | 586 | `episode-36-extraction.md/json` |
| 37 | 北风苔原 魔枢 72 | `BV1DQrhBVEQA` | 43:25 | 335 | `episode-37-extraction.md/json` |
| 38 | 北风苔原72.5 | `BV19NrhByEMe` | 51:21 | 509 | `episode-38-extraction.md/json` |

检查点根目录：

```text
/Users/chat/claude/.ai-bridge/wow-video-extraction/
```

原始证据根目录：

```text
/Users/chat/claude/wow-quest-route/.ai-bridge/video-epN/
```

## 第38集恢复摘要

第38集按60秒粗扫、20秒全程复查、5秒关键事件窗加密、系统聊天、任务窗口、追踪栏和Questie前后置/经验进行交叉审计，已确认：

- 正式证据为8批509帧，509/509截图成功且全部`paused=true`；
- 本集没有直接可读的玩家等级数字或72→73升级祝贺消息；标题《北风苔原72.5》和下一集《北风苔原73》只作系列连续性元数据；
- 第37集遗留`11650《还要一些东西……》`、`11730《主与仆》`、`11692《寻找比希》`已在本集闭环；`11938《争取时间》`仍无完成或放弃证据；
- 菲兹兰克机械线连续完成`11650→11653《大块头》→11658《B计划》→11670《是兽人干的！真的！》`，并完成护送`11673《带我出去！》`；
- “尾旋”支线连续完成`11725《寻找“尾旋”》→11726《一点辣椒》→11728《狼的排泄物》→11795→11796→11873《通知菲兹兰克》`；
- 机械任务中心完成`11788《左膀右臂》`、`11730《主与仆》`、`11873《通知菲兹兰克》`，开启`11798《机甲专家麦卡佐德》`和`11713《侦查虫孔》`；
- `11798`本集已取得研究手册和麦卡佐德的徽记，`11713`已完成三个虫孔标记，但两项都没有最终交付，必须继续带入第39集；
- 片尾完成`11692《寻找比希》→11693《好极了……天灾猛犸人！》`，并开启严格后续`11694《山洞中的瘟疫》`；
- 本集明确最终完成15项任务，按Questie基础经验×2校准的任务奖励合计约582100；该数字只作为视频事实统计，不直接用于当前五开路线预算。

片尾/跨集高优先级未闭环：

`11798《机甲专家麦卡佐德》,11713《侦查虫孔》,11694《山洞中的瘟疫》,11938《争取时间》`。

更早仍未闭环至少包括：

`11940,11884,11872,12035,12086,12117,10004,9900,9925,9882,9937,9869,10810,9962`。

本集已经从旧遗留中闭环并移除：

`11650,11730,11692`。

连续性警告：

- `11798/11713`是“目标已完成、待最终交付”，不能在第38集提前记为任务完成；
- `11693`最终完成由交付窗口、任务列表变化和`11694`严格前置共同确认，未捕获单独系统完成聊天，因此经验按Questie×2校准；
- `12035《重新装配》`与本集机械任务视觉目标相近，但没有直接任务名完成证据，不能与`11730《主与仆》`混同；
- 第39集只查询了合集元数据，没有打开、播放或截图。

下一集是第39集《北风苔原73》，BVID `BV1fdraBbE9B`，时长45:09（2709秒）。完成第38集后，全系列还剩15集（第39—53集）。

## 当前已知风险

- 视频可能在任务中心或地区之间发生剪辑，必须比较剪辑前后任务状态。
- 任务日志与追踪栏不是同一概念；`目标(N)`不能当完整任务数。
- “目标完成”和“最终交付”必须分开记录。
- B站页面DOM、CDP target和浏览器WebSocket地址会变化，不能把本次值写成永久命令。
- OCR对小字号数字、地点名和系统聊天容易误读；Questie只负责校准名称/ID/NPC/基础经验，不能替代动作证据。
- 视频属于联盟角色，任务链只能作为事实证据；路线整合阶段不能直接套用到当前部落五开。

## 全集结束后的入口

完成第53集后，不再继续逐集处理。转入：

```text
docs/video-extraction/POST-EXTRACTION-PLAN.md
```

该阶段会先合并和审计全部事件JSON，再把联盟视频路线作为参考证据接入现有35—55任务块、动态经验、交通和部落路线优化工作。
