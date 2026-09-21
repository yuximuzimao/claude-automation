# ERP 新版页面兼容 — 完成记录

日期：2026-09-22

## 范围

只处理 ERP 页面升级影响，不改商品匹配业务规则、库存分配算法或售后推理逻辑。

涉及页面：

- 商品档案V2：`#/prod/parallel_next/`
- 库存状态：`#/stock/newstatu_next/`

涉及项目：

- `product-mapping`
- `sku-calculator`
- `aftersales-automation`

## 商品档案V2最终结构

旧页面的三个关键锚点已变化：

1. 旧 `handleQuery()` 不再存在；新版查询区域 `.search-wrap` 的 Vue 组件提供 `search()`，可作为原直接 Vue 查询触发方式的一对一替代。
2. 旧 `dataList` 不再存在；当前页完整结果从可见 `.el-table.__vue__.store.states.data` 读取。
3. 旧 `a.ml_15` class 已彻底移除；“子商品信息”列中的数字仍是 `<a>`，因此先按表头精确定位“子商品信息”列，再只在该列内匹配预期数字链接。

子商品弹窗仍按表头 `商品名称 / 商家编码 / 组合比例` 读取。

## 修改

### product-mapping

- `lib/archive.js`
  - 查询触发改为 `.search-wrap.__vue__.search()`
  - 档案结果改读可见表格 Vue store
  - 子商品链接改为按“子商品信息”表头定位
- `lib/fetch-archive-names.js`
  - 同步新版查询和表格数据源
  - 旧表头“普通商品”筛选入口已不存在；改为遍历新版分页并按 ERP 行 `type === "0"` 精确保留普通商品
- `SKILL.md`、`docs/INDEX.md` 同步现行操作规则

### sku-calculator

- 无需修改 `lib/query-stock.js`
- `resolve-components` 继续复用 `../product-mapping/lib/archive.js`，不复制第二套档案逻辑
- 库存状态新版仍使用现有可见 Element UI 表格 Vue store 读取方式

### aftersales-automation

- `lib/erp/navigate.js` 商品档案V2路由更新为 `#/prod/parallel_next/`
- `lib/product/archive.js` 同步新版 `search()`、表格 store、子商品列定位
- `docs/erp-query.md`、`docs/ops-erp.md`、`docs/ops-tech.md`、`SKILL.md` 同步现行规则

## 真实验证

### 商品匹配

- `yx005`：正式档案查询成功，返回“悦希舒缓焕颜精华乳100ml”，`type=0`
- `919zh5`：套装查询成功，`subItemNum=18`
- `919zh5` 子商品弹窗成功打开并读取 8 行组成明细
- 全量名称读取：新版页面共 954 条商品，20/20 页读取完成，按 `type=0` 得到 193 条普通商品

### 库存状态

执行正式 `node cli.js resolve-stock`：

- 页面总记录：193
- Vue store 实际读取：193
- 读取数与分页总数完全一致
- 当前 product-columns 映射：38
- warnings：0

因此 `lib/query-stock.js` 不需要额外修改。

### 售后

- 真实套装 `919zh5`：成功返回 8 行子商品明细
- 特殊规格编码 `6940079096228`：成功按“规格商家编码”分支返回主编码 `yx005`
- `test/product/archive-subitems.test.js`：6/6 通过
- 全项目 `npm test`：487/487 通过
- 按项目规则安全重启：PID `22944 → 42994`，3457 正常监听；重启前后 live 工单总数均为 1695，没有自动重跑历史工单

## 边界

- 本次没有修改库存分配算法。
- 本次没有对懋业执行商品匹配写入。
- 懋业首次 check 仍未在兼容修复后重跑；下一步回到 `tasks/todo.md` 的懋业商品匹配待办继续。
