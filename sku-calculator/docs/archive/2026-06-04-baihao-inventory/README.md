# 2026-06-04 百浩库存分配交接

> 历史现场：后续批次已经完成。本文件只用于追溯当时的人工补丁背景，不代表当前待办或运行数据。

## 当前目标

给百浩店铺做本次活动库存分配。

- 店铺：百浩 / ERP 店铺名 `百浩创展`
- 供应商 ID：`41698`
- 本次活动：无满赠，`data/gift-sku-config.json` 已确认为 `{"giftSkus":[]}`
- 加购表：`/Users/chat/Desktop/预热期间实时监控-SKU加购_20260604_22.xlsx`
- 项目目录：`/Users/chat/claude/sku-calculator`

## 已完成

1. 已读取项目规则：
   - `CLAUDE.md`
   - `docs/INDEX.md`
   - `tasks/todo.md`
   - `SKILL.md`
2. 已解析加购表：
   - 命令：`node cli.js parse /Users/chat/Desktop/预热期间实时监控-SKU加购_20260604_22.xlsx`
   - 结果：53 个 SKU，53 个都有加购数，0 个冷门 SKU
   - `cart-adds.json` 中 `_meta.supplierId` 为 `41698`，映射到 `百浩创展`
3. 已重跑 `resolve-components`：
   - 第一次页面正常但缺 5 条。
   - 第二次因 ERP 商品对应表页面残留搜索条件，读成 0 条。用户已手动刷新页面。
   - 刷新后重跑正常读取：对应表 100 条产品、146 个 SKU、图片 135 张。
   - 当前 `data/sku-components.json` 状态：`matchedSkus=51/53`，`resolvedSkus=48/53`。

## 当前阻塞项和用户确认

当前本地 `data/sku-components.json` 还没有打人工补丁，仍缺 5 条。下一会话要先补齐这 5 条，再继续查库存。

### 1. `0409fs::防晒＊5支`

问题：加购表 SKU 名和对应表 SKU 名不一致。

- 加购表：`防晒＊5支`
- 对应表：`防晒＊5支（赠1个小蓝包）;悦希`
- ERP 编码：`260605- 8`
- 用户已确认：这两个是同一个 SKU，可以忽略名称错误。
- 用户确认明细：`防晒 ×5 + 小蓝包 ×1`

建议下一步：

- 优先单独查 `queryArchive("260605- 8")` 获取小蓝包的 ERP 精确单品名。
- 如果查不到，就按用户确认补：`HEE悦希悦美水漾光盾防晒精华 30g ×5` + 小蓝包精确库存名 ×1。
- 注意 `product-columns.json` 当前已经有 `HEE悦希悦美水漾光盾防晒精华 30g`，但还没有小蓝包列。

### 2. `0605zh-1::悦颜3件组*2套+眼膜*2盒`

问题：加购表 SKU 名和对应表 SKU 名不一致。

- 加购表：`悦颜3件组*2套+眼膜*2盒`
- 对应表：`悦颜3件组*2套+眼膜*2盒（(赠1个小蓝包）;HEE悦希`
- ERP 编码：`260605- 6`
- 用户已确认：这两个是同一个 SKU，实际查到的组合明细是正确的，只是名称更新。

建议下一步：

- 优先单独查 `queryArchive("260605- 6")` 并读取子品明细，直接使用实际组合明细。
- 如果查不到，按用户确认和现有 SKU 反推：
  - `yyzh4::悦颜3件组` 的全部组件 ×2
  - `HEE悦希焕颜紧致淡纹眼膜 3g*5袋 （白） ×2`
  - 小蓝包精确库存名 ×1

现有 `yyzh4::悦颜3件组` 明细：

```json
{
  "HEE悦希印花礼袋-白": 1,
  "HEE悦希雪梨纸": 1,
  "HEE悦希玻色因淡纹悦颜霜 50g": 1,
  "HEE悦希玻色因淡纹悦颜霜 8g 体验装": 1,
  "HEE悦希抗皱悦颜精粹水 100ml": 1,
  "悦希玻色因悦颜微珠精华液 30g": 1,
  "HEE悦希印花礼盒（天地盖）白色": 1
}
```

现有 `yxyt2.0-ms::眼膜2.0*4盒` 明细：

```json
{
  "HEE悦希焕颜紧致淡纹眼膜 3g*5袋 （白）": 4
}
```

### 3. `yxjm-zl::洁面膏 1支`

问题：档案 V2 单独复查仍为 `null`。

- ERP 编码：`6975183893203`
- 用户确认：这是特殊规格商家编码，允许本次按同货号 2支 SKU 反推。

应补组件：

```json
{
  "悦希氨基酸表活焕颜洁面膏100g": 1
}
```

### 4. `yxs-zl::精粹水 1瓶`

问题：档案 V2 单独复查仍为 `null`。

- ERP 编码：`6940079096211`
- 用户确认：这是特殊规格商家编码，允许本次按同货号 2瓶/4瓶 SKU 反推。

应补组件：

```json
{
  "悦希舒缓焕颜精粹水100ml": 1
}
```

### 5. `yxr-zl::精华乳 1瓶`

问题：档案 V2 单独复查仍为 `null`。

- ERP 编码：`6940079096228`
- 用户确认：这是特殊规格商家编码，允许本次按同货号 2瓶/4瓶 SKU 反推。

应补组件：

```json
{
  "悦希舒缓焕颜精华乳100ml": 1
}
```

## 下一会话建议执行顺序

1. 进入项目：

```bash
cd /Users/chat/claude/sku-calculator
```

2. 先读规则和本交接：

```bash
sed -n '1,220p' CLAUDE.md
sed -n '1,220p' docs/INDEX.md
sed -n '1,260p' tasks/2026-06-04-baihao-inventory-handoff.md
```

3. 对 `260605- 8`、`260605- 6` 单独查档案 V2，优先拿 ERP 精确组合明细。

4. 给 `data/sku-components.json` 补 5 条人工确认明细，并同步 `data/product-columns.json` 增加任何新增单品列，尤其是小蓝包。补完后读回验证：

- 53 个加购 SKU 在 `sku-components.json` 都有 key。
- `_meta.resolvedSkus` 应改成 53。
- 保留一个 `_manualOverrides` 或类似字段，记录这 5 条是用户确认/反推，不要让来源丢失。

5. 查库存：

```bash
node cli.js resolve-stock
```

6. 计算并生成报告：

```bash
node cli.js calculate
node cli.js report
```

7. 验证：

- 读回 `data/allocation-result.json`，确认 53 个 SKU 都进入分配。
- 读回桌面最新 `库存分配-*.xlsx` 路径。
- 最终向用户说明：
  - 报告路径
  - 5 条人工确认/反推项
  - 是否有库存瓶颈 warning

## 注意事项

- 不要再直接跑 `resolve-components` 覆盖当前人工补丁，除非用户明确要求重新全量解析。
- `resolve-components` 会先清空 `sku-components.json` 和 `product-columns.json`。
- 商品对应表页面如果残留搜索条件，会出现 `第1页 展开: 1/0`、累计 0 条的假失败；必须先刷新/清条件/确认在商品对应表全量视图。
- 这次“无满赠”是活动规则；小蓝包是 SKU 自身组合明细里的随货组成，不应配置到 `gift-sku-config.json`。
