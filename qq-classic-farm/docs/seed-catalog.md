# 种子知识库

正式数据：`../data/seed-catalog.json`
图标：`../assets/seeds/`

## 当前覆盖

2026-10-22 从游戏仓库逐项实测采集：
- QQ：40 个当前库存种子条目。
- 微信：20 个当前库存种子条目。
- 合并名称后：43 个唯一种子图标。

种子名称、图标和资料按 `seeds[].name → seeds[].image → seeds[].observations.{qq,wechat}` 对应。

## 字段口径

- `quantity_initial_snapshot`：2026-10-22 首次仓库采集时的数量快照。
- `quantity_latest_known`：当前已知的最新数量；后续已验证的种植消耗、神秘商人购买等库存变化都继续更新此字段。
- `mature_time`：仓库详情显示的基础成熟时间。
- `harvests`：可收季数。
- `yield_per_harvest`、`exp_per_harvest`、`income_per_harvest`：当前账号/平台详情页显示值。
- `seed_price_display`、`fruit_value_display`：界面显示值；部分活动种子可能没有常规价格。
- `raw_detail_rows`：保留首次采集 OCR 的详情行，便于以后纠错。

## 使用原则

1. 选种时先按名称查 catalog，再使用 `image` 与种植选择器的图标比对。
2. QQ / 微信库存独立，不能把同名种子数量相加。
3. 数量是快照；若决策依赖准确剩余量，先重新打开仓库刷新。
4. 同名种子的成熟时间/季数通常可交叉核对，但产量、经验、收入以当前平台实测为准。
5. 活动种子优先信任游戏仓库；外部攻略只作为补充。
