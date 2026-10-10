# 2026-10-10 悦希活动批量拆单与 SKU 清单发现

状态：本阶段定义与调查已收口；未接入 ERP 批量写操作。

## 这次确定的事实

- `data/packing-campaign-split-notes-09-22.md` 是 2026 年 9 月 22 日悦希活动的现役原始资料，继续留在 `data/`，不移入历史归档。
- SKU ID 是人工批量筛选同组合订单的精准条件；第一批公式决定从筛选结果中拆出哪些商品和数量。
- 公式、SKU ID、赠品状态和 ERP 子订单身份各自承担不同职责，不能互相替代。
- 悦希 3 月、9 月大促才启用“主品先处理、赠品转异常订单挂起、后续单独拆单”；普通活动按正常商品处理。
- 商品匹配项目的稳定链接身份是 `productCode + platformCode`。相同 `platformCode` 的不同链接、不同店铺必须分开保留。

## ERP 对应表调查结论

商品对应表界面没有显示数字 SKU ID，但 Vue 表格数据中存在：

- `itemPlatform.numIid`：平台商品 ID；
- `itemPlatform.subTableData[].skuItemPlatform.skuId`：复合 SKU ID；
- `skuItemPlatform.outerId`：平台规格编码；
- `skuItemPlatform.propertiesNameReal`：规格说明。

例如 `133460944sdw260922-4` 可拆为数字 SKU ID `133460944` 与平台商品 ID `sdw260922-4`。当前页面显示 133 条记录，每页 20 条；商品匹配项目已有对应表全量分页读取实现，入口为 `product-mapping/lib/correspondence.js` 的纯读取流程。

## 当前自动化方向

浮窗仍是唯一用户入口，批量处理以“SKU ID + 公式配置 + 活动策略”为批次任务。活动前先生成清单，运行时由脚本循环筛选 SKU ID、只读预检查、生成拆分计划、执行受控批量操作并记录异常。未知组合、店铺范围冲突、数量不守恒和赠品历史不明时进入异常队列。

活动清单必须保留：店铺、`productCode`、`platformCode`、平台规格编码、数字 SKU ID、ERP 商品身份、公式编号、份数规则、赠品策略和来源证据。不能只保存数字 SKU ID。

## 尚未实施

- 尚未新增对应表隐藏 Vue 数据的审单侧提取器；当前只完成页面调查和数据结构确认。
- 尚未生成完整 133 条活动 SKU 清单并与商品匹配结果合并。
- 尚未接入浮窗批量执行、ERP 批量写操作或新的活动级授权协议。
- 2026-09-22 活动的 `133460944` 仅作为真实回放样本，不代表全部活动清单。

## 现役入口

- 原始活动资料：`data/packing-campaign-split-notes-09-22.md`
- 当前状态：`docs/CURRENT.md`
- 后续待办：`tasks/todo.md`
- 商品匹配身份规则：`../../../../product-mapping/docs/matching-stability.md`
- 商品对应表读取实现：`../../../../product-mapping/lib/correspondence.js`
