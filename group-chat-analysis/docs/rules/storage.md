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

批次状态使用 `schemas/batch-state.schema.json` 描述，正式运行时保存到 `runtime/state/`。采集必须区分：

- `incomplete`：中途中断/失败，保留批次下一页恢复位置和各群最近页，不得生成正式 current.md；
- `completed`：达到本轮停止条件且规范化/去重完成，可以生成 current.md；
- `analyzed`：GPT 已处理 current.md，但不改变已完成消息，也不能用另一组记录改写现有 current.md。

批次页恢复位置按 `capture-page.schema.json` 的全局 `page_index` 严格递进，不能跳页、重复记录或用新 batch 覆盖未完成 batch；群级只保存该群最近页和增量锚点。每群增量锚点必须是连续消息序列；只有 completed batch 才能更新为新的已完成锚点。

状态只保存 batch 标识、状态、时间、页恢复位置和脱敏结构化锚点所需字段；不得保存截图、头像圆圈指纹或长期昵称别名。分析失败不得让 completed 消息丢失。

## 生命周期

- screenshot：默认不落盘；诊断截图完成后清理。
- raw OCR：按 `schemas/capture-page.schema.json` 保存单页 records，至少保留到对应 batch 完成并通过基本验证；后续保留周期可再决定。
- normalized messages：长期本地保留，作为增量锚点与历史复查依据。
- current.md：可覆盖为下一 completed batch，但上一批消息仍在 messages 中。
- reports：默认本地长期保留，除非用户决定清理。

## 原子性

正式实现时，canonical messages、completed 状态和 current.md 必须避免“写了一半就被视为完成”。错误成本以**completed state 绝不能领先于 canonical messages**为最高优先级。

现役提交顺序固定为：
1. 先校验本批全部 message records；
2. 用临时文件 + `fsync` + 原子 replace 更新 `runtime/messages/messages.jsonl`；同一 batch 重试必须幂等，内容不同则拒绝；
3. canonical messages 已持久化并回读校验后，才允许把 batch state 从 `incomplete` 更新为 `completed`；
4. `current.md` 是可重建派生物，completed 后再原子生成。若崩溃发生在 state completed 与 current.md 之间，重启后从 canonical messages 重建；若发现 state 已 completed 但 canonical messages 缺失/不一致，视为数据损坏并停止，禁止静默补写。

因此允许短暂存在“messages 已落盘但 state 仍 incomplete”的可恢复窗口；禁止出现“state completed 但 messages 尚未可靠落盘”的伪完成。
