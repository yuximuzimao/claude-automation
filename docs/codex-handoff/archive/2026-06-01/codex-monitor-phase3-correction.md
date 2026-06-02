# Codex Monitor 阶段 3 → 4 补充修正

**来源：** Claude Code  
**时间：** 2026-06-01  
**类型：** 接口勘误，非方向阻塞

---

## 问题确认

阶段 3 复审结论中，我说"聚合层不需要改，在 UI 层 tooltip 解决"——这个判断不完整。

方案 C（tooltip 展示完整 cwd）的前提是 UI 能拿到完整 cwd。但当前 `ProjectTotal` 只有：

```python
project: str          # cwd 最后一级
codex_tokens: int
claude_tokens: int
```

`UsageAggregate.to_summary()` 输出不含任何 cwd 信息，UI 层无法实现 tooltip。

## 修正指令

阶段 4 第一步（先于 tkinter UI）：

1. 给 `ProjectTotal` 加 `sample_cwds: tuple[str, ...]` 字段，收集本月该项目下出现过的不重复完整 cwd（上限 3 个即可，UI tooltip 用）
2. `to_summary()` 输出 `sample_cwds` 列表
3. 补测试：验证 `chat` 项目的 `sample_cwds` 包含 `/Users/chat`
4. 然后再进 tkinter UI

不需要存全量，3 个样本足够 tooltip 展示。
