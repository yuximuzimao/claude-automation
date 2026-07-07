# 商品匹配当前有效待办

> 2026-07 状态收口：本文件不再作为 2026-04 模块化测试计划台账。历史 L1/L2/P3 测试细节已由代码、测试和 git 历史保留；当前只列仍会影响下一次实战活动的待办。

## P0：下次实战前必须看

- [ ] **确认本轮店铺/品牌作用域**
  - 开始前读 `docs/preflight-brand.md` 和 `docs/brand-onboarding.md`。
  - 当前运行态仍是 one-brand-per-run：`check` 会自动清空 `data/imgs/`、`data/reports/` 并全量重写 `data/sku-records.json`。
  - 不要为了“已有 KGOS/HEE 两个品牌”主动做 `data/brands/{brand}/` 架构重构；只有出现并行品牌处理、长期保留多品牌运行态、或高频切换且不能接受重跑 `check` 时再启动。

## P1：HEE v2 复核

- [ ] **HEE 品牌建档修复计划（v2）复核**
  - 历史计划：`~/.claude/plans/linear-percolating-crab.md`。
  - 当前判断：品牌作用域隔离暂缓，继续使用 one-brand-per-run + `check` 自动清空/全量重写来控制运行态污染。
  - 复核项只保留真正可能影响下一轮建档质量的内容：
    - `readCorrespondence` 副作用拆分是否仍需要；
    - `assertPlatformImageColumn` 断言是否已覆盖当前 ERP 页面；
    - `validate-brand-archive.js` 验收脚本是否值得保留或补齐；
    - `docs/preflight-brand.md` / `docs/brand-onboarding.md` 是否覆盖 HEE/KGOS 当前流程。

## P2：下次实战覆盖项

- [ ] **L2-remap-single**
  - 性质：等待下次包含“单品换绑”的真实活动覆盖。
  - 不单独为了补测试跑破坏性页面操作；在真实 remap 场景中验证 4 类用例即可。

- [ ] **L2-verify-archive**
  - 性质：等待下次需要 `match-one` / 档案 V2 回读验证的真实活动覆盖。
  - 当前 `auto-match2` 主流程不直接调用 `verify-archive.js`，所以它不是当前开发阻塞项。

- [ ] **L2-match-one**
  - 性质：等待下次单品活动覆盖 remap 路径。
  - 已有套件路径在 2026-05-20 共途/KGOS 39 套件实战中覆盖；后续重点看单品 remap 和断点续跑。

## P3：低优先级技术验证

- [ ] **stop-on-error 实战观察**
  - 已被 `match` 主流程吸收为“任一 SKU 报错立即停止”原则。
  - 下次真实错误发生时观察：是否停止、是否保留 done/failed 日志、人工处理后是否必须 `check → match`。

- [ ] **el-table clearSelection() 方案按需验证**
  - 只有再次出现批量勾选残留、Vue 状态和 DOM 状态不一致时再验证。
  - 验证通过后再决定是否更新 `auto-match2.js` 或写入 `docs/INDEX.md §6`；没有复现信号时不主动投入。

## 已转历史，不再作为当前开发待办

- [x] **T1 ERP「下载平台商品」按钮**：已被 `check` 主流程和 `lib/correspondence.js` / `lib/ops/download-products.js` 吸收；若 ERP 按钮文案变化，按实际报错修。
- [x] **T2 check.js 报告格式验证**：已被当前 check/compare/report 流程吸收；改报告字段时再单独验证。
- [x] **T3 match 命令可访问**：已成为常规入口；下次实战前按需做 `--limit 0` 连通性 smoke，不列为开发任务。
- [x] **2026-04 L1/L2 测试基础设施台账**：测试框架、L1 单测、L2 基础设施和已完成页面操作测试均归档，不再占据当前待办主线。

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
