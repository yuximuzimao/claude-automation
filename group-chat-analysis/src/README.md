# 正式代码模块边界

本文件只定义正式代码职责，避免实验代码与现役实现混在一起。

## 当前正式模块

```text
src/
  normalize/    # 相邻页保守去重、capture 顺序转聊天顺序
  store/        # batch/state 原子状态 + message-record 契约校验
  inbox/        # completed batch 的 current.md 原子生成
```

当前已有：

- `normalize/overlap.py`：只对高置信相邻页连续序列去重。相似昵称不归并；一侧昵称缺失时宁可保留重复；`message_type` 与双方可见时间必须兼容。`merge_capture_order_pages()` 明确接收 `page_index` 递增的“新→旧”采集页并输出“旧→新”消息。
- `store/batch_state.py`：`incomplete/completed/analyzed` 状态、批次级页恢复位置、连续增量锚点和原子 state replace。
- `store/message_record.py`：从 `schemas/message-record.schema.json` 读取字段、枚举和 const 真值，统一做持久化边界校验；不再在测试或 inbox 各维护一份 Schema 副本。
- `inbox/builder.py`：只有 completed/analyzed batch 才能生成 `runtime/inbox/current.md`；全部记录先过正式 message-record 校验，非法输入不得覆盖上一份 current.md。

尚未正式落地：

- `capture/`：真实 QQ / ScreenCaptureKit / Vision / AX 窗口准备适配器；旧 capture worktree 只能作为参考，不能直接 merge。
- bbox → 消息候选的正式重建实现。
- `runtime/messages/messages.jsonl` 的正式持久化与跨文件崩溃恢复编排。
- 唯一 app/CLI 编排入口。

目录只在真正有现役代码时创建，不用空目录或占位文件污染仓库。

## 依赖方向

目标依赖方向为：

`app → capture → normalize → store → inbox`

app 负责调用各模块；底层模块通过明确数据结构传递，不允许：

- capture 调用 GPT；
- normalize 操作 QQ；
- store 判断消息价值；
- inbox 修改 canonical messages；
- 任一模块直接写魔兽或其它项目。

## 去重安全优先级

v1 的错误成本不对称：**漏掉真实消息 > 多保留一条重复消息**。

因此：

1. 不做全局 `sender+text` 去重。
2. 不做相似昵称身份归并；头像指纹不再是 v1 正式入口门禁。
3. 一侧 sender 缺失时不做破坏性去重。
4. 两条消息的最小重叠必须再有强锚点；匿名正文锚点至少 8 个规范化字符。
5. 同一重复消息的 canonical 选择先保留更完整正文，再比较元数据完整度与 OCR confidence。
6. 证据不足就保留两份，后续可在分析层容忍重复，不能在 Normalize 层猜删。

## 正式入口门禁

当前已经完成：

1. capture raw Schema；
2. batch/state Schema 与正式实现；
3. 相邻页保守去重正式实现；
4. capture 页方向 → 聊天时间方向的显式转换；
5. message-record 正式校验；
6. current.md 正式 builder；
7. 单元/合成 dry-run 已直接测试正式 `src`，不再测试测试文件里的实现副本。

下一门禁是把真实 QQ capture 与 bbox 消息重建接入这些正式模块，并在一个目标群上跑小范围真实 dry-run。通过之前不做首次全量抓取。
