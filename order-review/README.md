# 审单悬浮窗

快麦 ERP 待审核订单的桌面辅助工具，用于查看原订单、编辑包裹方案、复用历史，
并在用户逐单点击后执行受保护的审核或拆分。原订单信息与包裹决策分开保存。

## 开始使用

```bash
PYTHONPATH=src python3.13 -m order_review.app
```

审单浮窗需要已有Chrome调试连接和正确的待审核页面；独立装箱实验页面不连接ERP/CDP。
两类入口、刷新、审核、恢复与诊断的完整说明见[使用指南](docs/usage.md)。已有浮窗实例时不要重复启动。

## 接手开发

- Agent 从 [SKILL.md](SKILL.md) 开始。
- [当前状态](docs/CURRENT.md)区分已实现能力、未验证场景和实验进度。
- [装箱实验计划](docs/2026-09-08-packing-simulator-plan.md)记录P1已完成骨架与下一阶段1～N箱算法研究；本地实验页不等于已接入正式审单浮窗。
- [待办](tasks/todo.md)与[文档索引](docs/INDEX.md)给出具体入口；当前接手先做算法来源/成熟实现研究，不继续扩前端。
- [根本规则](docs/2026-07-23-package-rule-foundation.md)规定方案语义；[安全边界](AGENTS.md)约束真实ERP操作。

包装尺寸和原箱资料见 `data/packing-dimensions.json`；正式案例保存在应用数据目录，
不与实验记录混用。活动拆单简写保持原文，等待匹配后人工对应。

[历史档案](docs/archive/README.md)只用于追溯，不替代当前计划与业务规则。
