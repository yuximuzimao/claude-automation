# Todo

只记录尚未完成事项。

## Runner V2

- [x] **V2-0 清理旧路线**
  - 8 个 V1 整田视觉/复杂恢复模块已删除。
  - 旧模块现役引用为 0。
  - 173 项保留测试全部通过。

- [ ] **V2-1 QQ 空田检查器：离线完成，live EMPTY 终验待授权**
  - [x] 固定 4×6 网格 + 两个 5×5 ROI 已实现。
  - [x] `check-empty --platform qq` 只读命令已实现。
  - [x] 真实历史空田 / 当前24格月见草 / 遮罩 / 残留作物离线回放符合事实。
  - [ ] 新的 QQ 真空田出现后，由用户在当前 Chat 明确授权再做 live EMPTY 终验。

- [ ] **V2-2 QQ 完整种植：纯事务层完成，live 接线待校准**
  - [x] Phase 只从 EMPTY 起步，之后 Runner 维护 `known_occupied`。
  - [x] 四格只验证 preview / confirm / 目标 2×2 ROI。
  - [x] 普通剩余格由计划直接计算；picker 验证 ON 后只点一次已验证槽位。
  - [x] 删除 checkpoint / 崩溃自动续播；异常 DIRTY/STOP。
  - [x] QQ 固定格点击坐标已由历史实测固化。
  - [x] live adapter 的 phase-start EMPTY 与指定 cells 占用验证已实现为只读 ROI。
  - [x] 当前全项目 157 项测试全部通过。
  - [x] one-key ON 正例已用实机截图校准，OFF / ON / UNKNOWN 三态可判。
  - [x] 四格 preview/confirm 视觉已用历史实机样本离线校准。
  - [ ] 接 open_plot / confirm CGEvent；确认后目标 occupied ROI 等新现场终验。
  - [ ] 当前 Chat 明确授权后再做真实完整种植验收。

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
