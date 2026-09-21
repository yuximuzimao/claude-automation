# ERP 商品档案V2新版兼容 — 完成记录

日期：2026-09-22

## 修改

- `lib/erp/navigate.js`
  - 商品档案V2：`#/prod/parallel/` → `#/prod/parallel_next/`
- `lib/product/archive.js`
  - 旧 `handleQuery()` → 新版 `.search-wrap.__vue__.search()`
  - 旧 `dataList` → 当前可见 `.el-table.__vue__.store.states.data`
  - 旧 `a.ml_15` → 按“子商品信息”表头定位列，再精确匹配该列数字 `<a>`
  - 原有特殊规格编码白名单、查询字段清场、子商品弹窗表头读取、失败重试边界均保持不变

现行规则同步到 `docs/erp-query.md`、`docs/ops-erp.md`、`docs/ops-tech.md` 和 `SKILL.md`。

## 真实验证

- 套装主编码 `919zh5`
  - 查询成功
  - `subItemNum=18`
  - 成功读取 8 行子商品明细
- 特殊规格编码 `6940079096228`
  - 正确走规格商家编码查询
  - 返回主编码 `yx005`
  - 单品 `subItems=[]`
- 专项测试 `test/product/archive-subitems.test.js`：6/6 通过
- 全量 `npm test`：487/487 通过

## 服务生效

修改 `lib/` 后按 `/aftersales-restart` 规则执行安全重启：

- op-queue 重启前：running=null，pending=0
- PID：`22944 → 42994`
- TCP 3457：正常监听
- live 工单：重启前后均为 1695
- 没有自动重采或重跑已有工单

该兼容项已完成，从 `tasks/todo.md` 移除。
