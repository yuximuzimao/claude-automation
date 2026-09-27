# 存储规则

## 数据等级

### 版本化数据
允许进入 Git：
- 代码；
- Schema；
- 规则；
- 测试fixture（必须人工脱敏/合成）；
- 架构与项目文档。

### 私密运行数据
只允许进入 `runtime/`：
- 群聊原文；
- 群昵称；
- OCR原始结果；
- bbox/confidence；
- 采集锚点；
- 当前分析输入；
- GPT分析报告；
- 诊断截图。

`runtime/` 整体 Git ignore。

## 运行时目录

```text
runtime/
  raw/          # OCR批次原始结构化结果，可按策略清理
  messages/     # 规范化消息库
  inbox/        # GPT待分析输入
    current.md  # 唯一默认入口
  reports/      # GPT分析结果
  state/        # 恢复点与完成状态
  diagnostics/  # 临时诊断截图；常规运行不得使用
```

目录可在程序首次运行时创建，不需要通过占位文件进入 Git。

## raw page 契约

每次 Vision OCR 后保存的原始页面必须符合 `schemas/capture-page.schema.json`。

最小字段包括：
- `schema_version`；
- `batch_id`；
- `page_index`；
- `group_key` 与当前窗口标题得到的 `group_display`；
- `source=qq_history_window_ocr`；
- `observed_at`；
- 当前聊天记录窗口的 `window_id/title/width/height`；
- `coordinate_space=vision_normalized_bottom_left`；
- `blocks[]`，每个 block 保存 `block_index/text/bbox/confidence`。

`group_display` 是当页实际观察到的窗口标题；`group_key` 是本机配置中的稳定本地标识。两者语义不同，不能互相替代。

raw page 默认写入 `runtime/raw/<batch_id>/page-<page_index>.json`。写入成功后才允许推进持久化页号；截图仍默认不落盘。

## canonical source

规范化群聊原文的本地 canonical source 是：

`runtime/messages/messages.jsonl`

`runtime/inbox/current.md` 是派生分析包，不反向修改 messages。

## current.md

`runtime/inbox/current.md` 必须只由 **completed capture batch** 生成。

包含本批全部待分析文字，不能先让 GPT 自己从 raw/OCR碎片里猜消息结构。

建议保留：
- batch_id；
- 抓取时间；
- 群标识；
- 本批消息数；
- 大致时间范围；
- 按群、按时间排序后的正文；
- 可见昵称/稳定本地成员标识。

默认不保留 QQ号等不必要账号标识。

## 批次状态

采集必须区分：
- `incomplete`：中途中断/失败，不得生成正式 current.md；
- `completed`：达到本轮停止条件且规范化/去重完成，可以生成 current.md；
- `analyzed`：GPT已处理 current.md。

分析失败不得让 completed 消息丢失。

### `runtime/state/state.json` 最小格式

在增量锚点算法尚未完成前，不提前固化复杂状态机；v1 最小状态只需要：

- `schema_version`；
- `last_completed_batch`：没有时为 null；
- `last_successful_capture_at`：没有时为 null；
- `current_batch`：没有运行批次时为 null；运行中至少保存 `batch_id/group_key/status/started_at/last_persisted_page_index/stop_reason`；
- `groups`：按 `group_key` 保存 `last_completed_batch/last_completed_at/anchor_record_ids`。`anchor_record_ids` 只有在 Normalize 已经生成稳定消息记录后才填写。

`last_persisted_page_index` 表示已经成功写入 raw page 的最后页号；恢复时只能从这个事实状态继续，不能靠“上次大概滚到哪里”猜。

状态字段若后续需要跨版本迁移，再单独建立 state schema；当前不为尚未实测的去重阈值、滚动次数或 UI 坐标创建永久字段。

## 生命周期

- screenshot：默认不落盘；诊断截图完成后清理。
- raw OCR：至少保留到对应 batch 完成并通过基本验证；后续保留周期可再决定。
- normalized messages：长期本地保留，作为增量锚点与历史复查依据。
- current.md：可覆盖为下一 completed batch，但上一批消息仍在 messages 中。
- reports：默认本地长期保留，除非用户决定清理。

## 原子性

正式实现时，写 raw page、state、current.md 和 completed 状态都不能出现“写了一半却被视为成功”的情况。

优先：
1. 写临时文件；
2. 校验；
3. 原子 rename/replace；
4. 再推进 state 中的已持久化页号或 completed 状态。

具体技术由实现决定，但语义不得改变。
