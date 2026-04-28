# 临时教训暂存

Session 级新发现记在这里。稳定后迁入 `docs/INDEX.md §6`，不在两处重复维护。

---

> 本文件上次清理：2026-04-22。所有历史教训（§1-§17）已迁入 `docs/INDEX.md §6`。

---

## 待处理优化项

| 优先级 | 内容 | 状态 |
|---|---|---|
| ✅ | RULES.md 渐进式披露重构 → docs/ 文件夹结构早已就位，条目关闭 | 完成 |

---

> 新的 session 级发现从这里往下记，稳定后迁入 §6。

## 2026-04-23 session 教训（已入 memory，待迁 §6）

| # | 教训 | memory |
|---|------|--------|
| 18 | HTML data 属性嵌 JSON 必须单引号包裹 | feedback_jingling_dev.md §18 |
| 19 | batch-reprocess 含 auto_executed，禁止用于部分重查 | feedback_jingling_dev.md §19 |
| 20 | routes.js/data.js 改动后必须重启服务器 | feedback_jingling_dev.md §20 |

## 2026-04-28 session 教训（已入 memory，待迁 §6）

| # | 教训 | memory |
|---|------|--------|
| 21 | ERP trade-detail-dialog 关闭方式 | feedback_jingling_dev.md §21 |
| 22 | session 缓存跳过 reload 后必须清残留弹窗；`node -e require()` 会执行 main() | feedback_jingling_dev.md §22 |
| 23 | ERP 多行数据必须聚合读取 | feedback_jingling_dev.md §23 |
| 24 | ERP 交易关闭状态 fallback textSnippet | feedback_jingling_dev.md §24 |
| 25 | 已执行工单重处理防护（executedAt 检查） | feedback_jingling_dev.md §25 |
| 27 | 并发扫描同一账号导致 CDP 脏数据 crash | feedback_jingling_dev.md §27 |
| 28 | list.js 不点筛选标签会读到所有状态工单 | feedback_jingling_dev.md §28 |
| 29 | 驿站待取件 ≠ 已签收，两者处理方式不同 | feedback_jingling_dev.md §29 |
| 30 | collect.js 重采时必须继承 feedbackStatus/groundTruth | feedback_jingling_dev.md §30 |
| 31 | scan-all.js ok 状态必须整条覆盖，不能 Object.assign | feedback_jingling_dev.md §31 |
| 32 | 重启系统必须同时验证队列状态 | feedback_jingling_dev.md §32 |

## 2026-04-28 session 新发现（未入 memory，待稳定后迁入）

### 33. Express 路由顺序：字面路由必须在动态路由前注册

`router.post('/accounts/add', ...)` 必须在 `router.post('/accounts/:num/relogin', ...)` 之前注册。
即使路径段数不同（`/add` 是2段，`/:num/relogin` 是3段），Express 仍可能先尝试动态匹配，导致 `/add` 返回 404。
**修复**：所有字面路径（无 `:param`）统一注册到动态路由段之前。

### 34. pkill -f 杀进程不可靠，必须用 lsof 找 PID

`pkill -f "node server.js"` 可能杀不到真正监听端口的进程（存在多个同名进程时只杀其中一个）。
**修复**：重启服务器前先 `lsof -i :PORT` 拿到监听进程 PID，再 `kill <PID>`，再启动新进程。
