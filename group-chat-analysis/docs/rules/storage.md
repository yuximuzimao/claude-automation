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

采集必须区分：
- `incomplete`：中途中断/失败，不得生成正式 current.md；
- `completed`：达到本轮停止条件且规范化/去重完成，可以生成 current.md；
- `analyzed`：GPT已处理 current.md。

分析失败不得让 completed 消息丢失。

## 生命周期

- screenshot：默认不落盘；诊断截图完成后清理。
- raw OCR：至少保留到对应 batch 完成并通过基本验证；后续保留周期可再决定。
- normalized messages：长期本地保留，作为增量锚点与历史复查依据。
- current.md：可覆盖为下一 completed batch，但上一批消息仍在 messages 中。
- reports：默认本地长期保留，除非用户决定清理。

## 原子性

正式实现时，写 current.md 和 completed 状态应避免“写了一半就被视为完成”。

优先：
1. 写临时文件；
2. 校验；
3. 原子 rename/replace；
4. 再更新 completed state。

具体技术由实现决定，但语义不得改变。
