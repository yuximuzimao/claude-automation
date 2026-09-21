# ERP 新版页面兼容复验

日期：2026-09-22

## 结论

库存分配项目不需要为本次 ERP 页面升级修改库存读取核心逻辑。

- 商品档案V2组合明细继续复用 `../product-mapping/lib/archive.js`；该共享实现已完成新版兼容，并用真实套装 `919zh5` 验证档案查询和子商品读取。
- 库存状态路由继续使用 `#/stock/newstatu_next/`。
- `lib/query-stock.js` 现有“只读当前可见 Element UI 表格 Vue store”的实现与新版页面兼容，无需修改算法或字段映射。

## 正式库存读取验证

执行 `node cli.js resolve-stock`：

- ERP 分页总记录：193
- 实际从 Vue store 读取：193
- 当前每页：500
- 当前 product-columns 映射：38
- warnings：0
- 输出成功写入 `data/warehouse-stock.json`

当前数据中其余 155 条 ERP 商品不属于本轮 product-columns，按既有规则忽略。

## 说明

尝试直接以当前运行态执行 `resolve-components` 时，默认路径先被 `cart-adds.json` 的供应商 ID `43259` 未注册门禁拦截；这是运行输入/店铺映射门禁，不属于本次 ERP 页面兼容。未为通过测试而修改 `shop-map`。共享档案函数已通过真实编码单独实测，因此不扩大本次范围。
