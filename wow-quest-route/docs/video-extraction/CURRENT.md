# 视频拆解当前状态

更新时间：2026-08-13 17:55（UTC+8）

## 当前阶段

- 阶段：第一阶段，逐集事实提取。
- 已完成：第13—43集。
- 下一集：第44集。
- 本轮停止点：第43集检查点、事件JSON、520帧正式原始证据、OCR和Questie交叉审计均已完成；第44集仅从当前合集状态只读查询元数据，未打开、未截图、未处理。
- 最新NEAT归档仍为：`docs/video-extraction/sessions/2026-08-07-episode34-neat.md`；本轮未额外做NEAT归档。

## 下一集唯一入口

- 集数：44/53
- 标题：《嚎风峡湾75》
- BVID：`BV1unkTB3Ejj`
- 合集标注时长：60:09（3609秒）
- 目标检查点：
  - `/Users/chat/claude/.ai-bridge/wow-video-extraction/episode-44-extraction.md`
  - `/Users/chat/claude/.ai-bridge/wow-video-extraction/episode-44-events.json`
- 原始证据目录：`wow-quest-route/.ai-bridge/video-ep44/`

用户下次说“继续处理下一个视频”或“继续处理第44集”时，直接按`README.md`执行，不重新讨论流程，不先做路线评价，不处理第45集。

## 最小恢复步骤

1. 读`docs/video-extraction/README.md`。
2. 读本文件。
3. 读`/Users/chat/claude/.ai-bridge/wow-video-extraction/episode-43-extraction.md`。
4. 如需机器结构，再读`episode-43-events.json`。
5. 重新取得当前Chrome浏览器WebSocket地址；不要复用旧CDP地址。
6. 通过新空白标签并用`.ai-bridge/bili-open-paused-bvid.js`在导航前禁止自动播放。
7. 处理第44集，写独立检查点，更新本文件，关闭本轮B站标签，然后停止。

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
| 39 | 北风苔原73 | `BV1fdraBbE9B` | 45:09 | 425 | `episode-39-extraction.md/json` |
| 40 | 龙骨荒野 73 | `BV1qGrjBCEgr` | 60:07 | 492 | `episode-40-extraction.md/json` |
| 41 | 龙骨荒野 74 | `BV1BurjB1Ep3` | 44:14 | 462 | `episode-41-extraction.md/json` |
| 42 | 龙骨荒野 74.5 | `BV1EwrWBeEMZ` | 61:33 | 525 | `episode-42-extraction.md/json` |
| 43 | 嚎风峡湾 74.5 | `BV14SrfBEE5W` | 52:16 | 520 | `episode-43-extraction.md/json` |

检查点根目录：

```text
/Users/chat/claude/.ai-bridge/wow-video-extraction/
```

原始证据根目录：

```text
/Users/chat/claude/wow-quest-route/.ai-bridge/video-epN/
```

## 第43集恢复摘要

第43集按60秒粗扫、20秒全片复查、5秒关键事件窗加密，并对片尾极速连续交付额外做1秒级复查；结合系统聊天、任务窗口、追踪栏和Questie严格前后置/经验进行交叉审计，已确认：

- 正式证据37批520帧，520/520截图成功且全部`paused=true`；最初超时留下的`coarse-a/` 17张无manifest临时帧明确不计入正式证据。
- 本集内部没有新的直接玩家等级证据；标题《嚎风峡湾 74.5》只作合集元数据，不用于绑定升级任务。
- 本集明确最终完成25项任务，视频直接经验/Questie基础经验×2校准合计`667700`；探索经验和怪物经验不计入该数字。
- 开场直接切到联盟嚎风峡湾瓦加德，本集没有回龙骨荒野集中交任务；约38:40任务日志仍直接可见`12253《拯救暮冬城的平民》`、`12459《创造与毁灭的力量》`、`12456《奥雷托斯的羽毛》`，因此不能清除这些旧任务。
- 嚎风峡湾本集完成瓦加德/龙颅村主干与多条并行支线，包括`11228→11243→11244`、`11274→11276→11277→11299→11300→11278`、`11288→11289`、`11255→11290`、`11420→11426`、`11333→11343→11344`、`11427→11429→11430→11421→11436`。
- `11251《跑腿侦查》`在约37:35最终交付并接出`11252《杀入乌特加德！》`；同段接受联盟`13205《削减军备》`。
- 片尾最终完成`11344《尼弗莱瓦的痛苦》`和`11436《冲浪去！》`；后者交付过快，使用3078—3087秒1秒级窗口确认约4000经验和任务追踪减少。

第44集最高优先级连续性：

1. `11448《探险者协会哨站》`：片尾仍在追踪栏，未交；
2. `11291《前往西部卫戍要塞！》`：片尾仍在追踪栏，未交；
3. `11252《杀入乌特加德！》`、联盟`13205《削减军备》`：已接受未完成；
4. 第42集遗留`12253`、`12459`、`12456`在第43集中段仍有直接任务日志证据；
5. `12447《黑曜石巨龙圣地》`、`12470《永恒之龙的秘密》`、`12511《丘陵援兵》`、`12794《魔法王国达拉然》`、`12464《我的老对手》`仍无新增最终交付/放弃证据；
6. `12167《消灭教徒》`继续保持`turnin_unknown_across_cut`，不能自动闭环。

更早仍未闭环至少包括`11940,11884,11872,12035,12086,10004,9900,9925,9882,9937,9869,10810,9962`；`9962`此前明确失败，但是否保留/已放弃仍未知。

连续性警告：

- 任务追踪栏不是完整任务日志；片尾只显示两项，不能据此清除旧任务。
- `11255《龙颅村的囚犯》`由1295秒完成任务窗口+1300秒接受Questie严格后续11290共同确认最终交付，经验按Questie×2校准。
- `11436《冲浪去！》`必须使用1秒级窗口才能与前一个`11344`交付拆开；已单独记录。
- 第44集只查询了合集元数据，没有打开、播放、截图或处理。

下一集是第44集《嚎风峡湾75》，BVID `BV1unkTB3Ejj`，时长60:09（3609秒）。完成第43集后，全系列还剩10集（第44—53集）。

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
