# 装箱实验 worktree → main 对账收口

归档日期：2026-09-13

## 结论

`order-review-packing-simulator` worktree 的业务内容已逐项对账完成。后续以 main 为唯一当前事实，不再从 worktree 回抄代码、商品身份、尺寸或规则。本阶段没有 raw merge，而是按文件和字段重建到当前 main，因为 P1 分支同时包含后来确认错误的跨项目 pending 与视觉 `productKey` 设计。

## 已保留的正确内容

- `order-review` 保留商品尺寸拆表：`packing-dimensions.json` 负责纸箱、原箱、规则、pending 与证据；`packing-product-dimensions.json` 负责单品尺寸、零体积配件和仓库排除项。
- P1 的本地装箱页面、只读 service/web、静态前端、固定 3466 启动器和测试已迁回 main。
- `dimension_catalog.py` 支持拆分商品尺寸文件，并兼容旧 inline `products`。
- 单箱求解器保留严格 verifier，并完成物件顺序搜索第一阶段；完整算法仍按 `1～N箱外层 + 单箱几何内核` 推进。
- 2026-09-11 ERP 商品档案 200 条只读身份快照已迁回 `product-mapping`，与 worktree 原件做全量 JSON 语义比较，200/200 一致。
- `brand-onboarding.md` 已恢复到 2026-08-31 之前的原始商品匹配 SOP；HEE 6 个新品和 KGOS 两款七条咖啡的视觉待办统一放在 `product-mapping/tasks/todo.md`。

## 明确废弃的 worktree 设计

- 不迁 `product-mapping/data/products/kgos/pending-products.json`。
- 不迁 worktree 对 KGOS `features.json` 的 P1 补丁；没有实际图片/识图特征前不建视觉条目，也不复用旧 12 条装咖啡视觉。
- 删除 `product-mapping/data/products/hee/pending-products.json`。该文件是 2026-08-31 为“先记录几个新品”额外创建的结构化中间层，后来又被错误扩展到审单尺寸/箱规；现行必要身份和视觉待办已转 TODO。
- 装箱尺寸不再使用 `brandId::视觉标签` / `productKeys`；只按 ERP 标准全名和商家编码关联。前端 `productKey` 仅作 opaque 行 ID。
- 删除“阻断片 → 糖果2.0”等视觉标签特判；旧糖果也不再保留，只剩糖果2.0 `6976299500108`。
- 黑茶说明卡不进入商品匹配视觉目录，只在审单侧按 `hcmlhckp` 作为零体积配件保留。

## Worktree 最终对账

P1 提交 `ee54804` 的文件已全部分类：应保留内容已迁回或按当前规则重建；KGOS features/pending、HEE pending、视觉 productKey 已明确废弃；根级入口只吸收仍成立的当前规则，不照搬旧 `{brand}/pending-products.json` 机制。

worktree 当前的未提交代码中，`usage.md`、`carton_packing.py`、`packing_simulator_service.py`、两份对应测试和启动器均与 main 字节级一致。唯一不同的 `packing-product-dimensions.json` 仍保留旧视觉 `productKeys`，而 main 已全部换成 ERP 标准身份链，因此不是遗漏，而是 main 的纠正版。

结论：后续不需要再从 worktree 取任何业务内容。本地 worktree 只保留到 main 页面完成一次用户实测，之后可删除；远端旧分支仅作历史备份。

## main 接管与验证

固定 3466 服务已停止旧 worktree 进程并从 main 重新启动；实际工作目录和 `/api/catalog` 数据路径均已核对为 main。当前 API 冒烟为：2 个品牌、商品目录 82 条、尺寸商品 19 条、运输纸箱 16、pending 16、待补纸箱 2、产品原箱 6。旧 worktree 的 83 条目录不再作为验收目标。

抽查确认：糖果只剩2.0；两款七条咖啡保留正式名称/编码但缺尺寸；黑茶说明卡为零体积配件；悦希新品按正式 ERP 身份命中尺寸。

验证结果：

- `order-review` 装箱专项：58 passed。
- `order-review` 全量回归：316 passed。
- `product-mapping`：18/18 passed。
- `product-detect`：14/14 passed。

## 下一会话

直接从 main 的 3466 页面实测，不在实测前预防性重做前端。重点检查品牌切换/搜索/卡片布局、ERP正式全名与简称、七条咖啡待补尺寸、悦希6个新品、糖果2.0、零体积配件、产品原箱下拉条件、历史人工方案只读对照和三视角摆放。发现具体问题后只改受影响处。

页面实测通过后删除本地旧 worktree。算法后续仍按 `2026-09-12-packing-algorithm-research.md` 与 `tasks/todo.md`：支撑模型拆层 → Extreme Point 候选点层 → `pack_order()` 1～N箱外层 → 历史盲测。
