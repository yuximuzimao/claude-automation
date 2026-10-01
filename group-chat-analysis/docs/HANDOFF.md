# 群聊分析交接

## 当前完成

阶段 2-2 已完成一个可执行的相邻屏连续序列去重原型，文件为 `tests/test_normalize_overlap.py`。阶段 2-3 已完成 batch/state 契约原型，文件为 `schemas/batch-state.schema.json` 与 `tests/test_batch_state.py`；两者都暂不进入正式 `src/`，因为 QQ capture 的头像定位/指纹实现和真实采集端到端门禁尚未完成。

已新增合成端到端 dry-run 门禁原型 `tests/test_dry_run_gate.py`：它串起相邻页合并、消息记录字段校验、batch `incomplete/completed/analyzed` 状态，以及 `current.md` 的原子生成。该测试用于先固化状态与文件边界，不代表真实 QQ capture 已通过验收。

当前默认契约：

- 比较相邻捕获页，不做全局 `sender+text` 去重。
- 匹配最长的左页尾部到右页序列，允许右页从保留的页边缘候选之后开始重叠。
- 默认最小连续重叠为 2 条消息；两条消息还需昵称、时间或长正文精确锚点。
- 正文 OCR 模糊匹配阈值为 `0.90`；昵称不使用全局相似度身份规则。相似昵称必须规范化后同长度、恰好一个字符差异，并且当前批次头像圆圈局部指纹一致；单符号昵称只做精确匹配。
- 头像圆圈指纹只在当前批次内存中使用，不写入 Schema、长期状态或昵称别名；头像不一致或无法可靠裁剪时不确认相似昵称。
- 合并重叠记录时优先较高 OCR 置信度，其次选择正文更完整的版本；没有可靠重叠就原样保留两页。

## 验证

`python3 -m unittest tests/test_normalize_overlap.py` 当前通过 16 项测试，覆盖精确重叠、单条重复拒绝、不同发送者同文、可靠/不可靠当前批次头像证据、带相同头像的受控 OCR 差异、相似昵称头像冲突/缺失、单符号昵称、长度/多字符差异拒绝、页内偏移、canonical 选择和无重叠保留。

`python3 -m unittest tests/test_batch_state.py` 当前通过 8 项测试，覆盖 batch-level 页索引 Schema 契约、incomplete 恢复、未完成批次保护、批次级页索引连续性、每群捕获页门禁、completed 锚点门禁、跨批次携带已完成锚点和 analyzed 状态。

`python3 -m unittest tests.test_normalize_overlap tests.test_batch_state tests.test_dry_run_gate` 当前通过 29 项测试；新增 5 项 dry-run 检查覆盖：incomplete 不生成或覆盖 current.md、completed 才开放 inbox 门禁、相邻页重叠只保留一次、非法记录不覆盖上一份 current.md、analyzed 重建相同输入且不包含头像指纹或昵称别名。

30 页真实诊断扫描的校准结果已写入 `docs/CURRENT.md`。原始 OCR block 签名只作为阈值证据，不能替代规范化消息 batch 的最终复核；runtime 原文、昵称、bbox 和日志不应提交。

## 下一步

执行 `tasks/todo.md` 顶部的阶段 2-3：在 capture/normalize 边界接入当前批次头像圆圈指纹，并定义正式 dry-run 门禁。之后再把去重和 batch/state 原型迁移到正式 `src/normalize`、`src/store` 入口，用端到端 dry-run 复核误去重、漏去重、恢复点、跨页顺序和 `current.md` 生成条件。
