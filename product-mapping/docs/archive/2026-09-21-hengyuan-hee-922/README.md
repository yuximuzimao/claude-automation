# 悦希 9.22 蘅圆商品匹配归档

日期：2026-09-21

## 最终结果

- 店铺：蘅圆
- 品牌：hee
- 活动范围：48 个货号 / 94 个 SKU
- final check：
  - recognitionDone = 94
  - comparisonMatch = 94
  - comparisonMismatch = 0
  - comparisonPending = 0
  - pendingVisualReview = 0
  - matchedSkuCount = 94
  - unmatchedAwaitingMatch = 0

结构化摘要见 `final-check-summary.json`。

## 识图快照

`recognition-snapshot.json` 保存 94 个 SKU 的：

- `productCode + platformCode`
- SKU 名
- 当次平台原图 `imgUrl`
- 最终 `recognition`

用途：同一活动切换到其他店铺时，若目标店铺出现相同 `productCode + platformCode`，可直接复用已经人工核对通过的 recognition；**不得复用蘅圆的 ERP 对应结果**，目标店铺仍必须实时 check。

## 本轮关键纠错

1. 平台原图中的实际商品实物是识图最高依据；SKU 名、图片文字和活动文案只能辅助核对。
2. HEE 收单王部分 SKU 出现“SKU 名的套组编号”和平台原图实际展示组合不一致，最终按 SKU 自己绑定的平台原图处理并报告源数据差异。
3. 用户提供的清晰参考图默认只说明商品/套组外观，不代表具体 SKU 的绑定真值。
4. 需要重新确认具体 SKU 图片时，直接使用 `sku-records.json imgUrl` 获取该 `productCode + platformCode` 的平台原图；这是本轮验证过的原图直链渠道。
5. 自动匹配中“换对应商品”残留弹窗曾在 10 秒门限误停，现行等待已调为 15 秒；仍超时则 fail-fast。
6. 人工完成 SKU 后应先 check 回读 ERP 再续 match，不能通过手改自动匹配进度代替真实回读。

当前稳定规则已同步到 `../../INDEX.md`，本归档只保留本批次事实。
