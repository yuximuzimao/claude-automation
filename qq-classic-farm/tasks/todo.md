# Todo

只记录尚未完成事项。

## Runner V2

- [ ] **V2-0 清理旧路线**
  - 移除正常 Runner 对整田视觉研究模块的依赖。
  - 旧 diagnostic-only 脚本退出现役链。
  - 简化/移除复杂 planting recovery；异常统一 DIRTY/STOP。
  - 清理只服务旧路线的测试。

- [ ] **V2-1 QQ 空田检查器**
  - 先用 2026-11-01 22:33 事故前已保存 QQ 全空截图采 purple-empty / gold-empty 小 ROI。
  - 固定锚点/基线 + 4×6 网格推导 24 格。
  - 实现 EMPTY / NOT_EMPTY / UNKNOWN。
  - 当前 24 格月见草现场只允许只读验证 NOT_EMPTY；新的真机 EMPTY 正例等待用户当前 Chat 明确授权后再采。

- [ ] **V2-2 QQ 完整种植**
  - 四格 placement：固定位置 → picker → 图标/数量 → preview/confirm → 记录 placement。
  - 普通：剩余格数由计划直接计算 → one-key ON → 选种一次。
  - 异常不补洞，DIRTY/STOP。
  - 一个本地 phase 连续完成。

- [ ] **V2-3 QQ 完整收获**
  - 已知四格 placement 附近检查“可摘”。
  - 四格收获 → 一键收获 → V2 空田检查。
  - 一个本地 phase 连续完成。

- [ ] **V2-4 微信参数化**
  - 采微信独立空地/按钮模板与偏移。
  - 跑通微信种植、收获完整一轮。

- [ ] **V2-5 Planner / 库存**
  - 双平台 Runner 稳定后接库存同步与每天 3 轮计划。

- [ ] **V2-6 定时化**
  - 只允许稳定 Runner 被定时调用。
  - 不恢复“每小时自主研发 Runner”的旧自动任务。

## 当前现场约束

- QQ 当前 24 格误种月见草，保持现场，不自动收获/铲除/重种。
- 微信不主动操作。
- 真机输入必须由用户在当前 Chat 明确授权；历史自动任务、Work/handoff、子代理授权全部无效。
- 当前阶段优先纯离线 V2-0 / V2-1。
