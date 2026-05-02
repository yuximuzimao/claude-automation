# 鲸灵售后自动化

## Session 启动（必做，按顺序）

1. 读 `tasks/todo.md` — 确认当前待办和进度
2. `node cli.js list` — 获取实时工单，**禁止沿用历史工单号**
3. 读 `docs/INDEX.md` — 所有处理规则的权威入口

## 规则文档（渐进式，按需加载）

| 文档 | 加载时机 |
|------|---------|
| `docs/INDEX.md` | **每次必读**：错误处理、红线、工单路由、通用规范 |
| `docs/flow-5.1.md` | 工单类型 = 退货退款 |
| `docs/flow-5.2.md` | 工单类型 = 仅退款（未发货） |
| `docs/flow-5.3.md` | 工单类型 = 仅退款（已发货） |
| `docs/flow-5.4.md` | 工单类型 = 换货 |
| `docs/erp-query.md` | 涉及退货核验，需查商品对应表/档案V2 |
| `docs/ops-tech.md` | ERP 操作报错/页面异常 |

> 工单类型确认后只加载对应 flow 文档，不全量加载。

## 进入工作前确认（开工前过一遍，详细规则见 `docs/INDEX.md §1.2`）

- ERP 命令必须 `&&` 串行，禁止 `&` 并行
- 赠品子订单号禁止推算，必须从 `giftSubBizOrderDetailDTO.subBizOrderId` 读取
- 截图只用于上传凭证，禁止截图判断操作结果

## 相关项目

商品匹配核查（`../product-mapping/`）与本项目操作**同一套 ERP 和鲸灵**：

| 我需要参考 | 去哪里找 |
|-----------|---------|
| ERP 对应表/档案V2 操作规范 | `../product-mapping/docs/INDEX.md §5` |
| el-table Vue state 恢复问题（clearSelection vs DOM click） | `../product-mapping/docs/INDEX.md §6` |
| 多层嵌套 dialog 确定按钮查找（getBoundingClientRect） | `../product-mapping/docs/INDEX.md §6` |
| 对应表图片列 class 动态变化（懒加载处理方式） | `../product-mapping/docs/INDEX.md §5` |

## 教训沉淀流程

- `tasks/lessons.md` — Session 级新发现，先记这里
- `docs/INDEX.md §6` — 沉淀后的永久坑位，稳定后从 lessons 迁入，不在两处重复维护

## Git 存档规则

改动验证通过后立即 commit + push，不攒到 session 结束。
暂存：`git add lib/ cli.js server.js collect.js scan-all.js public/ tasks/ docs/`
不提交：`data/`、`*.log`、`.server.lock`

## 主要文件

| 文件 | 用途 |
|------|------|
| `cli.js` | 主命令（list / approve / reject / erp-* 等） |
| `server.js` | HTTP 服务（队列 + SSE），`node server.js` 启动 |
| `scan-all.js` | 14账号批量扫描，配合 `run-scan.sh` |
| `public/` | 前端管理界面 |
