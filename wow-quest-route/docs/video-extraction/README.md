# 魔兽世界升级视频拆解工作流

## 1. 目标与边界

本目录保存B站合集《魔兽世界时光服 骑士升级1-80》的逐集事实拆解工作流。

当前阶段是**第一阶段：逐集事实提取**。只记录视频里实际发生的：

- 接取、完成、放弃和任务目标进度；
- 等级、技能、坐骑、重要探索和成就；
- 剪辑造成的跨帧/跨集状态变化；
- 本集开始与结束时能够明确观察到的任务状态。

第一阶段禁止直接做：

- 联盟路线是否适合当前五个血精灵圣骑士；
- 联盟任务到部落任务的替换；
- 经验/分钟、路线优劣、任务取舍；
- 与当前实时Questie人物历程混合推断；
- 35—55最终路线定案。

这些工作统一留到全部视频提取完成后的第二阶段，见`POST-EXTRACTION-PLAN.md`。

## 2. 新对话最小读取顺序

用户说“继续处理第N集”时，只读：

1. `docs/video-extraction/README.md`
2. `docs/video-extraction/CURRENT.md`
3. 上一集的`.ai-bridge/wow-video-extraction/episode-(N-1)-extraction.md`
4. 如需机器结构，再读上一集对应`episode-(N-1)-events.json`

不要预先加载全部已完成集、整份NEAT、全部路线候选或实时Questie历程。

## 3. 每集固定流程

### 3.1 定位视频

- 从合集DOM或上一集页面取得下一集标题、BVID和时长。
- 只定位用户指定的一集；完成后不自动进入下一集。

### 3.2 禁止自动播放

使用项目本地助手：

```text
.ai-bridge/bili-open-paused.js
```

固定顺序：

1. 创建空白标签；
2. 在导航前注入媒体自动播放抑制；
3. 导航到B站视频；
4. 确认`hasVideo=true`；
5. 确认`paused=true`；
6. 读取`currentTime`、`duration`、`readyState`。

不得先打开并播放视频，再补做暂停。

### 3.3 粗扫

使用：

```text
.ai-bridge/bili-batch-screenshots.js
```

默认间隔：

- 普通移动/战斗：60—90秒；
- 城镇、营地和任务中心：15—30秒；
- 开场、结尾和明显剪辑处：更密。

每次seek后必须再次暂停，并在manifest中保存：请求时间、实际时间、时长、`paused`、`readyState`。

### 3.4 精查

遇到下列信号必须加密到1—10秒：

- 完整任务窗口；
- 系统聊天中的接受、完成、放弃、升级；
- 任务日志数量变化；
- 追踪目标突然变化；
- 区域、等级、任务链阶段变化；
- 视频剪辑前后状态不连续；
- 同名任务或同链多阶段容易混淆。

OCR工具：

```text
.ai-bridge/ocr-directory.swift
.ai-bridge/ocr-image.swift
```

优先用原始整帧；只有数字或系统聊天难读时才制作局部裁剪。裁剪图不计入原始证据帧数。

### 3.5 Questie校准

用`_sandbox/sources/Questie-v11.32.3.zip`和`lib.questie_source.load_questie`校准：

- 中文任务名；
- 任务ID；
- 同名任务的链阶段；
- 前后续关系；
- NPC和任务物品名称。

Questie只用于名称和结构校准，不能替代视频证据证明某动作发生。

### 3.6 写检查点

每集完成后立即写：

```text
/Users/chat/claude/.ai-bridge/wow-video-extraction/episode-N-extraction.md
/Users/chat/claude/.ai-bridge/wow-video-extraction/episode-N-events.json
```

原始截图、OCR和中间筛选保存在：

```text
wow-quest-route/.ai-bridge/video-epN/
```

完成后更新`CURRENT.md`，并关闭本轮为定位和处理该集而打开的B站标签。

### 3.7 NEAT阶段归档与恢复状态同步

阶段性历史统一归档到：

```text
docs/archive/video/
```

NEAT归档只保存阶段结果、证据边界、错误修正和下一次约束，不复制整份单集时间轴。每次做NEAT归档时必须同步核对：

- `docs/video-extraction/CURRENT.md`；
- `/Users/chat/claude/.ai-bridge/wow-video-extraction/progress.json`；
- `/Users/chat/claude/.ai-bridge/wow-video-extraction/CURRENT.md`；
- `tasks/todo.md`。

这些状态不得指向不同的下一集。项目`CURRENT.md`仍是唯一人类主状态，`progress.json`用于机器恢复。

当前最新NEAT归档：

```text
docs/archive/video/neat/2026-08-07-episode34-neat.md
```

## 4. 证据优先级

从高到低：

1. 完整任务接取/交付/放弃窗口；
2. 系统聊天中的接受、完成、物品、经验、升级提示；
3. 任务日志中的任务名、目标和数量；
4. 追踪栏中的目标变化；
5. 视频标题、NPC对白和环境信息。

关键规则：

- 右侧`目标(N)`是当前追踪目标数量，不是完整任务日志数量。
- 任务出现在日志里，只能证明当时持有；没有接取画面时不得虚构接取时间。
- 剪辑前后状态变化可以记录为`off_camera`或`cut_gap`，但不能补写未展示顺序。
- 任务目标完成不等于已经交付；必须区分`objective_complete_not_turnin`和`complete`。
- 查看任务窗口后点击“拒绝”不算接取。
- 精确等级数字读不清时，保留不确定性；跨集连续性推定必须明确标注为推定。
- 追踪栏未显示某任务，不能据此断定已经放弃或完成。

## 5. JSON事件约定

常用`action`：

- `accept`
- `complete`
- `abandon`
- `objective_progress`
- `objective_complete_not_turnin`
- `complete_and_accept_off_camera`
- `accept_off_camera`
- `view_and_reject`
- `level_up`
- `level_up_inferred`
- `achievement`
- `learn_spells`
- `mount_added`
- `discover`

每条事件至少保存：

- `time_range`
- `action`
- `quest_id`/`quest_name`（任务事件）
- `confidence`
- 必要的`basis`、`objective`、`exact_time_known`

## 6. 完成定义

一集只有在以下条件全部满足时才算完成：

- 已覆盖完整视频时长；
- 所有粗扫和精查manifest中的截图均确认暂停；
- 关键任务中心和任务日志变化已精查；
- 中文名和ID已用Questie校准；
- 剪辑缺口和无法确认项已显式记录；
- Markdown与JSON检查点已写入并通过基础验证；
- `CURRENT.md`已推进到下一集；
- 本轮B站标签已关闭；
- 没有自动开始下一集。