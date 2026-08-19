# 视频拆解当前状态

更新时间：2026-08-19 14:39（UTC+8）

## 当前阶段

- 阶段：第一阶段，逐集事实提取；正序第13—53集已完成，当前回补第1—12集。
- 已完成：第1—10集、第13—53集。
- 回补进度：10/12。
- 下一集：回补第11集。
- 本轮停止点：第10集检查点、事件JSON、238帧正式原始证据、OCR和Questie交叉审计均已完成；11个manifest共238/238帧截图成功、seek匹配且全部`paused=true`，覆盖0—3075秒。第11集只从第10集页面合集状态只读查询元数据，未导航、未播放、未截图、未处理。
- 最新NEAT归档仍为：`docs/archive/video/neat/2026-08-18-video-backfill-1-5-neat.md`；本轮未额外做NEAT归档，只完成逐集事实检查点。

## 下一集唯一入口

- 回补集数：11/12（合集第11/53集）
- 标题：《湿地任务 33》
- BVID：`BV1UoBvByEkZ`
- CID：`34999305144`
- 合集标注时长：00:50:16（3016秒）
- 目标检查点：
  - `/Users/chat/claude/.ai-bridge/wow-video-extraction/episode-11-extraction.md`
  - `/Users/chat/claude/.ai-bridge/wow-video-extraction/episode-11-events.json`
- 原始证据目录：`wow-quest-route/.ai-bridge/video-ep11/`

用户下次说“继续处理下一个视频”时，直接按`README.md`执行回补第11集，不重新讨论流程，不做路线评价，不进入`POST-EXTRACTION`。

## 最小恢复步骤

1. 读`docs/video-extraction/README.md`。
2. 读本文件。
3. 读`/Users/chat/claude/.ai-bridge/wow-video-extraction/episode-10-extraction.md`。
4. 如需机器结构，再读`episode-10-events.json`。
5. 重新取得当前Chrome浏览器WebSocket地址；不要复用旧CDP地址。
6. 通过新空白标签并用`.ai-bridge/bili-open-paused-bvid.js`在导航前禁止自动播放。
7. 只处理回补第11集，写独立检查点，更新本文件，关闭本轮B站标签，然后停止；继续按11→12逐集回补。

## 已完成集索引

| 集数 | 标题 | BVID | 时长 | 原始帧 | 检查点 |
| ---: | --- | --- | --- | ---: | --- |
| 1 | 北郡修道院 1-9 | `BV1rYq6BkEWw` | 01:02:32 | 809 | `episode-1-extraction.md/json` |
| 2 | 艾尔文森林 10-13 | `BV1v1q6BeExv` | 01:10:44 | 604+6 | `episode-2-extraction.md/json` |
| 3 | 西部荒野 14-16 | `BV1wUqUBvEuX` | 01:03:48 | 494+74 | `episode-3-extraction.md/json` |
| 4 | 西部荒野 16-18 | `BV1EJBsBcE1Z` | 00:53:16 | 333 | `episode-4-extraction.md/json` |
| 5 | 赤脊山 19-20 | `BV1c7B4BgEiZ` | 01:04:30 | 433 | `episode-5-extraction.md/json` |
| 6 | 赤脊山 20-22 | `BV1NaBNBnEca` | 01:10:04 | 266 | `episode-6-extraction.md/json` |
| 7 | 赤脊山 23-26 | `BV1EABNBgETt` | 01:11:39 | 229 | `episode-7-extraction.md/json` |
| 8 | 暮色森林 27-28 | `BV1xYBTBtErC` | 00:56:32 | 265 | `episode-8-extraction.md/json` |
| 9 | 暮色森林 29-30 | `BV19VBjBwE5M` | 00:54:46 | 310 | `episode-9-extraction.md/json` |
| 10 | 暮色森林 31-32 | `BV1mxBUBVETo` | 00:51:16 | 238 | `episode-10-extraction.md/json` |
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
| 39 | 北风苔原73 | `BV1fdraBbE9B` | 45:09 | 425 | `episode-39-extraction.md/json` |
| 40 | 龙骨荒野 73 | `BV1qGrjBCEgr` | 60:07 | 492 | `episode-40-extraction.md/json` |
| 41 | 龙骨荒野 74 | `BV1BurjB1Ep3` | 44:14 | 462 | `episode-41-extraction.md/json` |
| 42 | 龙骨荒野 74.5 | `BV1EwrWBeEMZ` | 61:33 | 525 | `episode-42-extraction.md/json` |
| 43 | 嚎风峡湾 74.5 | `BV14SrfBEE5W` | 52:16 | 520 | `episode-43-extraction.md/json` |
| 44 | 嚎风峡湾75 | `BV1unkTB3Ejj` | 60:09 | 547 | `episode-44-extraction.md/json` |
| 45 | 嚎风峡湾75.9 | `BV1iWkKBJEhC` | 01:08:55 | 571 | `episode-45-extraction.md/json` |
| 46 | 嚎风峡湾76 | `BV1KCkKBiEUh` | 54:46 | 523 | `episode-46-extraction.md/json` |
| 47 | 灰熊丘陵 77 | `BV1MGrQBhERs` | 01:13:32 | 750 | `episode-47-extraction.md/json` |
| 48 | 灰熊丘陵 77.5 | `BV1rnkHBqE8M` | 01:03:59 | 640 | `episode-48-extraction.md/json` |
| 49 | 灰熊丘陵 78 | `BV1PFksBUE9j` | 01:06:33 | 677 | `episode-49-extraction.md/json` |
| 50 | 灰熊丘陵 78.5 | `BV1u6kMBjE11` | 01:09:00 | 599 | `episode-50-extraction.md/json` |
| 51 | 灰熊丘陵 79 | `BV1uFkMByEaV` | 38:59 | 289 | `episode-51-extraction.md/json` |
| 52 | 祖达克79 | `BV1pGkMBvEU1` | 01:10:53 | 584 | `episode-52-extraction.md/json` |
| 53 | 祖达克 80 | `BV1N9kgBLE7W` | 01:14:04 | 656 | `episode-53-extraction.md/json` |

检查点根目录：

```text
/Users/chat/claude/.ai-bridge/wow-video-extraction/
```

原始证据根目录：

```text
/Users/chat/claude/wow-quest-route/.ai-bridge/video-epN/
```

## 回补第10集恢复摘要

第10集按60秒全片粗扫、20秒任务中心复查和5秒关键窗口加密；结合系统聊天、任务窗口、追踪栏与Questie任务链/经验进行交叉审计，已确认：

- 正式证据11批238帧，238/238截图成功、seek匹配且全部`paused=true`，覆盖0—3075秒。
- 约50:45—51:05系统聊天连续多帧直接显示玩家升到`32级`，成为当前回补段最新可靠具体等级证据。
- `323《证明你的实力》`由唯一后续转移确认完成；`269《寻求指引》`直接完成并接受`270《被诅咒的舰队》`。
- `158《僵尸》`由唯一后续转移确认完成，随后直接接受`156《收集腐败之花》`。
- `229《幸存的女儿》`完成并接受`231《女儿的爱》`；`231`虽出现奖励窗口，但之后仍明确在追踪栏，因此严格不算最终完成。
- 亚伯克隆比线中`156→159→133`由唯一链转移确认完成；`134《食人魔潜行者》`直接完成并获得2400经验，随后接受`160《给镇长的信》`。
- `160《给镇长的信》`、`251《翻译亚伯克隆比的信》`由唯一链转移确认完成；`401《等待希拉完工》`直接完成并获得3700经验；随后`252《翻译好的信件》`完成并接受`253《藏尸者的妻子》`。
- `253《藏尸者的妻子》`片尾只完成目标，没有回镇长最终交付，因此保持`objective_complete_not_turnin`。
- `98《斯塔文的传说》`片尾虽位于密斯特曼托庄园，但没有斯塔文/家族戒指或伊瓦夫人交付直接证据，继续保持未闭环；地名不能替代任务动作证据。

下一处理入口是回补第11集《湿地任务 33》，BVID `BV1UoBvByEkZ`，CID `34999305144`，时长00:50:16（3016秒）。第11集仅从第10集页面合集状态只读查询元数据，未导航、播放、截图或处理。

## 当前已知风险

- 视频可能在任务中心或地区之间发生剪辑，必须比较剪辑前后任务状态。
- 任务日志与追踪栏不是同一概念；`目标(N)`不能当完整任务数。
- “目标完成”和“最终交付”必须分开记录。
- B站页面DOM、CDP target和浏览器WebSocket地址会变化，不能把本次值写成永久命令。
- OCR对小字号数字、地点名和系统聊天容易误读；Questie只负责校准名称/ID/NPC/基础经验，不能替代动作证据。
- 视频属于联盟角色，任务链只能作为事实证据；路线整合阶段不能直接套用到当前部落五开。

## 全集结束后的入口

当前事实提取的完整范围是第1—53集。正序第13—53集已经完成；回补第1—10集已完成，当前从第11集继续逐集处理到第12集。

只有第1—53集全部完成事实提取后，才转入：

```text
docs/video-extraction/POST-EXTRACTION-PLAN.md
```

该阶段会先合并和审计全部事件JSON，再把联盟视频路线作为参考证据接入现有35—55任务块、动态经验、交通和部落路线优化工作。
