# 商品匹配当前有效待办

> 2026-07 状态收口：本文件不再作为 2026-04 模块化测试计划台账。历史 L1/L2/P3 测试细节已由代码、测试和 git 历史保留；当前只列仍会影响下一次实战活动的待办。

## P0：下次实战前必须看

- [ ] **HEE 新品待补资料**
  - 先读 `data/products/hee/pending-products.json`；当前 6 个新品必须识别为“已知待补”，不能归为未知或复用旧版外观。
  - 收到商品图或焕颜乳 2.0 最终条码后，按 `docs/brand-onboarding.md` 完成迁移和验收。

- [ ] **长批次期间保持 ERP 锁有效**
  - 当前 `lib/erp-lock.js` 的 5 分钟自动恢复窗口短于本轮 56 SKU 批量匹配时长。
  - 下次可能跨越售后 8/12/16/20 点扫描的真实匹配前，先实现锁续租、服务端租约或等价保护，并验证异常退出仍能恢复。
  - 在修复前，长批次必须避开定时扫描窗口；不得把一次“刚好未重叠”当成长期安全证明。

- [ ] **确认本轮店铺/品牌作用域**
  - 开始前读 `docs/preflight-brand.md` 和 `docs/brand-onboarding.md`。
  - 当前运行态仍是 one-brand-per-run：`check` 会自动清空 `data/imgs/`、`data/reports/` 并全量重写 `data/sku-records.json`。
  - 不要为了“已有 KGOS/HEE 两个品牌”主动做 `data/brands/{brand}/` 架构重构；只有出现并行品牌处理、长期保留多品牌运行态、或高频切换且不能接受重跑 `check` 时再启动。

- [ ] **按稳定性手册执行状态门禁**
  - 开始自动匹配或处理中断前读 `docs/matching-stability.md`。
  - 首次 check 明确指定品牌；后续记录、报告和命令品牌必须完全一致。
  - 任一 SKU 写入异常立即停止；先判断 `erpCode` / “复制为套件”中间状态，再恢复。
  - 最终必须满足全部 SKU `comparisonMatch`，且 mismatch/pending/pendingVisualReview 都为 0。

## P1：值得在下次相关改动时完成

- [ ] **统一套件页面操作实现**
  - 触发条件：下一次需要修改 `auto-match2.js`、`mark-suite.js` 或 `ops/create-suite.js` 任一套件流程。
  - 目标：搜索、单选、hover 标记、中间态恢复、弹窗清理和结果验证只保留一个权威实现。
  - 原因：相似逻辑分散会造成一处已修、其他入口继续复现旧问题。

- [ ] **补未覆盖的连续状态 live smoke**
  - 连续组合装、同比例套件换绑和单品重映射已有真实活动覆盖。
  - 仍需覆盖：已标记后中断恢复、筛选/页码残留、异常释放 ERP lock。
  - 不为测试单独制造无业务授权的 ERP 写入；在下一次已确认的真实活动中覆盖。

- [ ] **HEE 品牌建档质量复核**
  - `readCorrWithoutDownload` 已完成，不再作为待办。
  - 仍需在下一次 HEE 建档时确认图片列断言、品牌验收脚本价值，以及 preflight/SOP 是否覆盖当前页面。

## P2：下次实战覆盖项

- [ ] **L2-remap-single 边界场景**
  - 基础单品重映射已在真实活动通过；仍需覆盖搜索无精确结果、重复候选、中断和回读不一致等边界。
  - 不单独为了补测试跑破坏性页面操作；在后续已授权的真实 remap 场景中覆盖。

- [ ] **L2-verify-archive**
  - 性质：等待下次需要 `match-one` / 档案 V2 回读验证的真实活动覆盖。
  - 当前 `auto-match2` 主流程不直接调用 `verify-archive.js`，所以它不是当前开发阻塞项。

- [ ] **L2-match-one**
  - 性质：等待下次单品活动覆盖 remap 路径。
  - 已有套件路径在 2026-05-20 共途/KGOS 39 套件实战中覆盖；后续重点看单品 remap 和断点续跑。

## P3：观察后再决定

- [ ] **特殊订单“提示”弹窗**
  - 当前 stop-on-error 会在不确定状态下停止，不会自动确认。
  - 只有该提示再次进入常规活动路径，才纳入自动状态机；单次特例不提前扩展。

## 已转历史，不再作为当前开发待办

- [x] **T1 ERP「下载平台商品」按钮**：已被 `check` 主流程和 `lib/correspondence.js` / `lib/ops/download-products.js` 吸收；若 ERP 按钮文案变化，按实际报错修。
- [x] **T2 check.js 报告格式验证**：已被当前 check/compare/report 流程吸收；改报告字段时再单独验证。
- [x] **T3 match 命令可访问**：已成为常规入口；下次实战前按需做 `--limit 0` 连通性 smoke，不列为开发任务。
- [x] **2026-04 L1/L2 测试基础设施台账**：测试框架、L1 单测、L2 基础设施和已完成页面操作测试均归档，不再占据当前待办主线。
- [x] **stop-on-error 实战观察**：2026-07-24 澜泽批量中多次异常均在 ERP 最终确认前停止，没有继续写后续 SKU。
- [x] **Vue 隐藏选择清理**：已验证必须 `clearSelection()` + `updateCheckRows([])` 并等待 watcher 稳定，规则已进入稳定性手册。

## 长期架构票据

- [ ] **品牌作用域隔离重构（暂缓）**
  - 触发条件：第二个以上品牌需要并行处理、长期保留多品牌运行态，或频繁切换且不能接受重跑 `check`。
  - 目标架构仍是：

```text
data/brands/{brand}/
  imgs/
  sku-records.json
  sku-map.json
  check-report.json
  ref-imgs/
```

  - 未触发前，不作为当前必须开发项。
