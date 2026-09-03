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

## Phase 3: 冷启动稳定性实测（2026-09-03）
- [x] 修复 ERP 长时间后台/已在目标页时缺少重新激活和页面就绪确认的问题
- [x] `Input.insertText` / Enter 发送前自动激活 ERP，输入单号后读回确认再搜索
- [x] Web 结果改为每条完成立即更新，并增加“当前单完成后停止”的软停止按钮
- [ ] 下次正常真实批次重点观察：ERP 闲置较久后的首 1–2 单，以及用户停留售后面板、ERP 非当前标签时是否仍稳定；不要为验证单独制造真实入库

## 关键设计决策
- 无 isFirst：每单都检查弹窗和筛选项
- 页面状态用 waitFor 验证；会触发 Vue 重渲染或网络请求的动作后保留明确稳定延时
- 等待参数集中在 workflow.js 的 TIMING；关联订单允许 45 秒慢加载，禁止回退到紧凑轮询
- 提交锁：创建并收货点击后等明确成功/失败，不重试
- results.txt 启动时清空，逐条 append
