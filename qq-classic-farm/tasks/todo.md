# Todo

只记录尚未完成事项。

## Runner V2

- [x] **V2-0 清理旧路线**
  - 8 个 V1 整田视觉/复杂恢复模块已删除。
  - 旧模块现役引用为 0。
  - 173 项保留测试全部通过。

- [x] **V2-1 QQ 空田检查器：真机终验完成**
  - [x] 固定 4×6 网格 + 两个 5×5 ROI 已实现。
  - [x] `check-empty --platform qq` 只读命令已实现。
  - [x] 真实历史空田 / 当前24格月见草 / 遮罩 / 残留作物离线回放符合事实。
  - [x] 2026-11-02 新空田在当前 1.16.1.6 版本连续 5 次 live check 均为 EMPTY 24/24。

- [ ] **V2-2 QQ 完整种植：纯事务层完成，live 接线待校准**
  - [x] Phase 只从 EMPTY 起步，之后 Runner 维护 `known_occupied`。
  - [x] 四格只验证 preview / confirm / 目标 2×2 ROI。
  - [x] 普通剩余格由计划直接计算；picker 验证 ON 后只点一次已验证槽位。
  - [x] 删除 checkpoint / 崩溃自动续播；异常 DIRTY/STOP。
  - [x] QQ 固定格点击坐标已由历史实测固化。
  - [x] live adapter 的 phase-start EMPTY 与指定 cells 占用验证已实现为只读 ROI。
  - [x] one-key ON 正例已用实机截图校准，OFF / ON / UNKNOWN 三态可判。
  - [x] 四格 preview/confirm 视觉已用历史实机样本离线校准。
  - [x] open_plot / confirm 已接单次 CGEvent，并绑定本轮 EMPTY phase。
  - [x] 普通 ON / 四格 OFF 选种权限已分流；同 seed / slot / phase 才可点击。
  - [x] 当前全项目 161 项测试全部通过。
  - [ ] 确认后目标 occupied ROI 等新现场终验。
  - [x] 普通 one-key 真机子路径完成：紫薇×24，结果 24/24 occupied。
  - [ ] 四格特殊 + 普通剩余格混合路径仍待真机验收。

- [ ] **V2-3 QQ 完整收获**
  - 已知四格 placement 附近检查“可摘”。
  - 四格收获 → 一键收获 → V2 空田检查。
  - 一个本地 phase 连续完成。

- [ ] **V2-4 微信参数化**
  - [x] 微信 1.16.1.6 独立空田 ROI 已用当前 live 空田/成熟整田重校准。
  - [x] 真机成熟整田一键收获成功；收获前=NOT_EMPTY 24/24，收获后=EMPTY 24/24。
  - [x] 625 / 627 两种已见窗口宽度支持归一化 ROI。
  - [x] 当前土地为 6 紫 + 18 金；纯紫安全四格只保留 `purple_a`。
  - [ ] 校准微信 picker / preview / confirm；种植动作继续关闭。
  - [ ] 跑通微信种植、收获完整一轮。

- [ ] **V2-5 Planner / 库存**
  - 双平台 Runner 稳定后接库存同步与每天 3 轮计划。

- [ ] **V2-6 定时化**
  - 只允许稳定 Runner 被定时调用。
  - 不恢复“每小时自主研发 Runner”的旧自动任务。

## 当前现场约束

- QQ 当前已有作物，保持现场，不为测试自动铲除/重种。
- 用户已在当前 Chat 明确授权 QQ / 微信农场真机操作；若需实测优先微信。
- 真机仍必须遵守农场禁用时段和窗口冲突门禁；历史 Work/handoff、子代理授权仍无效。
- 2026-11-02 18:xx 当前不在禁用时段；真机操作仍需每次重新读取时间与窗口状态。
