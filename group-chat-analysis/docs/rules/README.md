# docs/rules 目录

用途：说明本目录有哪些长期规则 owner。这里只做目录，不判断当前任务属于哪一类，也不维护第二套执行流程；任务分类和完整运行先走 `../OPERATING-SOP.md`。

| 文件 | 内容 |
| --- | --- |
| `capture.md` | QQ 定位、窗口准备、滚动、变化检测、Vision OCR 与停止边界 |
| `normalization.md` | OCR 消息重建、顺序、fragment、媒体占位、跨页去重与增量 anchor |
| `storage.md` | runtime 生命周期、batch state、canonical messages、current.md 与恢复原子性 |
| `analysis.md` | 批次分析 SOP、事实/原文/AI 分层、价值排序、页面视图、黑话与跨项目候选 |
| `privacy-and-safety.md` | 权限、QQ 操作、私密数据、模型暴露与禁止技术路径 |

跨两个以上模块的结构变更按 SOP 分类为 `ARCHITECTURE_MIGRATION` 后再读 `../ARCHITECTURE.md`。
