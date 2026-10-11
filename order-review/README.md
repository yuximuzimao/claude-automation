# 审单悬浮窗

快麦ERP审单项目，以装箱辅助验证、日常审单浮窗和活动批量处理三种工具服务不同场景。
现役浮窗支持查看原订单、编辑方案、复用历史及逐单受保护审核/拆分；批量工具仍待资料核对与逐环节验证。
原订单信息与包裹决策分开保存。

## 开始使用

```bash
PYTHONPATH=src python3.13 -m order_review.app
```

审单浮窗需要已有Chrome调试连接和正确的待审核页面；独立装箱实验页面不连接ERP/CDP。
两类入口、刷新、审核、恢复与诊断的完整说明见[使用指南](docs/usage.md)。已有浮窗实例时不要重复启动。

## 接手开发

- Agent 从 [SKILL.md](SKILL.md) 开始。
- [项目总SOP](docs/OPERATING-SOP.md)统一说明三种工具分工、现有资料核对、活动前准备与运行时操作。
- [当前状态](docs/CURRENT.md)区分已实现能力、未验证场景和实验进度。
- [装箱实验计划](docs/2026-09-08-packing-simulator-plan.md)记录页面/资料边界；[算法研究](docs/2026-09-12-packing-algorithm-research.md)保留可选1～N箱结构。装箱以按需验证为主，具体实现与浮窗接入状态见CURRENT。
- [待办](tasks/todo.md)与[文档索引](docs/INDEX.md)给出具体入口。
- [根本规则](docs/2026-07-23-package-rule-foundation.md)规定方案语义；[安全边界](AGENTS.md)约束真实ERP操作。

纸箱、原箱、规则与证据见 `data/packing-dimensions.json`；单品装箱尺寸见 `data/packing-product-dimensions.json`。正式案例保存在应用数据目录，不与实验记录混用。活动拆单简写保持原文，等待匹配后人工对应。

[历史档案](docs/archive/README.md)只用于追溯，不替代当前计划与业务规则。
