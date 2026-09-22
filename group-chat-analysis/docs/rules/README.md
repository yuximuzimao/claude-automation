# 永久规则路由

本文件只保存最小公共规则与路由，不展开具体实现。

## 公共规则

1. 官方 QQ 是消息源；采集只读。
2. 采集控制、消息重建、存储、GPT分析必须分层。
3. 确定性工作由代码负责；GPT只做内容理解、筛选和摘要。
4. `runtime/` 是私密运行数据，不进 Git。
5. `runtime/inbox/current.md` 是 GPT/CodexPro 唯一默认分析入口。
6. v1 只承诺文字消息；其它媒体不阻塞项目。
7. 群内说法默认是未核验信息，不自动提升为其它项目规则。

## 路由

| 当前任务 | 只需再读 |
| --- | --- |
| QQ全屏/窗口定位、滚动、截图、Vision OCR | `capture.md` |
| 原文保存、current.md、批次与清理 | `storage.md` |
| OCR文字如何组成消息、顺序和去重 | `normalization.md` |
| GPT怎么筛选/总结、结果怎么使用 | `analysis.md` |
| 是否允许某权限/技术路线、隐私判断 | `privacy-and-safety.md` |

跨两个以上模块的结构变更再加读 `../ARCHITECTURE.md`。
