# 退货入库自动化 - 任务进度

## Phase 0: DOM 探索 ✅
- [x] 找到各步骤选择器和交互方式
- [x] 确认三路搜索结果触发条件
- [x] 确认成功信号（inputEmpty && rows===0）
- [x] 确认退货仓库每次重置（需每单重新选择锦福仓）
- [x] 确认继续创建下一笔单据默认未勾选

## Phase 1: 项目骨架 ✅
- [x] 目录结构（lib/ data/ tasks/）
- [x] lib/cdp.js（移植自 aftersales-automation）
- [x] lib/wait.js（移植自 aftersales-automation）
- [x] lib/result.js（移植自 aftersales-automation）
- [x] lib/navigate.js（精简版，保留 erpNav/checkLogin/recoverLogin）
- [x] lib/workflow.js（核心10步流程）
- [x] cli.js（入口）
- [x] package.json

## Phase 2: 端到端测试 ✅（2026-05-13）
- [x] 测试"未出库无需入库"路径（假单号）
- [x] 测试完整入库路径（真实单号）— SF0220494895377 + SF0223834815442 均已入库
- [x] 批量测试通过（3+ 单号混合，串行处理，SSE 实时推送正常）

## 关键设计决策
- 无 isFirst：每单都检查弹窗和筛选项
- waitFor 优先，sleep 最小化
- 提交锁：创建并收货点击后等明确成功/失败，不重试
- results.txt 启动时清空，逐条 append
