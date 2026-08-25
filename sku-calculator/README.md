# SKU 库存计算器

根据活动加购数据、ERP SKU 组合明细和云仓实时库存，计算每个 SKU 的建议库存，并生成带联动公式的 Excel 报告。

## 输入方式

### Excel 加购表

```bash
node cli.js parse <加购表.xlsx> --supplier-id <商家ID>
```

`--supplier-id` 必须使用本次页面实时读取的商家 ID；任一行不一致都会停止。

### 鲸灵商品数据页

无法导出 Excel 时，可从已打开的鲸灵「商品数据 → SKU 明细」页读取当前时间范围的数据，直接生成 `data/cart-adds.json`。完整字段、分页和支付过滤规则见 [页面加购数据抓取](docs/page-cart-scraping.md)。

## 标准流程

```bash
# 1. 准备加购数据（二选一：parse Excel，或按页面抓取文档生成 cart-adds.json）

# 2. 有满赠时先写货号和目标数量；无满赠则保持 giftSkus=[]
# data/gift-sku-config.json

# 3. 串行读取 ERP
node cli.js resolve-components
node cli.js resolve-stock

# 4. 计算并生成报告
node cli.js calculate
node cli.js report --output <报告路径.xlsx>
```

`resolve-components` 会根据 `cart-adds.json._meta.supplierId` 自动推导 ERP 店铺，并把满赠货号展开为真实 SKU。匹配率不足 100% 时立即停止，禁止带缺失组合明细进入计算。

## 安全边界

- 每轮都重新读取加购、组合明细和库存；运行时 JSON 只代表当次快照，禁止复用。
- `resolve-components` 必须先于 `resolve-stock`，两者操作同一 ERP 标签页，禁止并行。
- 库存计算与售后系统共享 ERP 标签页。开始 ERP 查询前须获得用户允许，临时停止 `com.heizong.aftersale-server`；结束后恢复 LaunchAgent，并验证 3457 端口和 `/health`。
- 本工具只生成本地 Excel，不向 ERP 或鲸灵提交库存。

## 输出与数据

- 默认报告：桌面 `库存分配-*.xlsx`
- 当前运行数据：`data/*.json`
- 手动维护配置：`data/gift-sku-config.json`
- 历史实战证据：[docs/archive/](docs/archive/README.md)

运行时数据和本地赠品配置不提交 Git；归档只保存可复核的批次摘要、验证结果和报告指纹。
