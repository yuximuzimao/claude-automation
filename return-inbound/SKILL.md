# 退货入库自动化

## 项目定位

操作快麦 ERP「退货入库」功能，将快递单号批量录入入库系统。
**主要入口**：售后系统 Web 面板（port 3457）→「退货入库」Tab。
CLI（`cli.js`）保留用于调试，不用于日常业务。

## 集成架构

```
浏览器粘贴单号
  → POST /api/return-inbound/run（aftersales-automation/lib/server/routes.js）
  → op-queue.enqueue('return-inbound', ...)（与售后操作互斥串行）
  → execReturnInbound()（aftersales-automation/lib/server/op-queue.js）
      → findErpTarget() + erpNav()（本项目 lib/navigate.js）
      → workflow.processOne(targetId, tracking)（本项目 lib/workflow.js）
  ← SSE: ri-progress（每条）/ ri-done（全批完成）
```

## 文件地图

| 文件 | 职责 |
|------|------|
| `lib/workflow.js` | 核心：ERP 页面操作全流程（新建 → 填单号 → 选仓库 → 确认） |
| `lib/navigate.js` | ERP tab 定位 + 导航到「售后工单新版」页 |
| `lib/cdp.js` | CDP WebSocket 封装（eval/click/navigate/screenshot） |
| `lib/wait.js` | `waitFor(fn, timeout, interval)` 轮询工具 |
| `lib/result.js` | 导航等内部调用使用的 `{ success, data/error }` 结果封装 |
| `cli.js` | 调试用 CLI，非日常使用 |
| `test/workflow-timing.test.js` | 关联订单慢加载、超时错误和生产等待参数回归测试 |

## 核心函数（workflow.js 导出）

- `processOne(targetId, tracking)` → `'已入库' | '未出库无需入库'`，异常时抛错 — 处理单条单号
- `findErpTarget()` → `targetId` — 找到 ERP Chrome tab
- `processAll(trackingNumbers)` — CLI 入口，内部自管 targetId

## 操作流程（processOne）

1. `ensureDialogOpen` — 点击「新建售后工单」按钮，等弹窗出现
2. `ensureFilterCorrect` — 确保查询维度为「原订单运单号」
3. `fillTracking` — 填入快递单号 + 回车搜索
4. 判断搜索结果：
   - 无结果（未出库）→ 关闭 `el-message-box`；再检查并关闭残留“提示” el-dialog（如“未发货仅退款”类型）；返回 `未出库无需入库`
   - 出现关联提示 → 点击「继续关联」，等待提示消失且主弹窗订单表格加载完成
   - 订单已直接加载 → 继续
5. `selectRefusalType` — 选择「拒收退货」
6. `selectWarehouse` — 选择「锦福仓」
7. `ensureContinueNextChecked` — 勾选「继续创建下一笔单据」
8. `selectAllItems` — 勾选所有商品行
9. `createAndReceive` — 点「创建并收货」→ 处理可能的二次确认 → 等成功信号
10. 返回 `已入库`

## 关键约束

- **弹窗查找必须匹配业务特征**：主弹窗验证标题「新建售后工单」；关联弹窗同时验证「提示」标题和「继续关联」按钮，禁止依赖弹窗数组顺序
- **DOM 选择器必须限制误命中**：主弹窗输入框和表格操作限定在目标 `wrapper` 内；全局挂载的下拉选项或提示按钮必须同时验证可见性和业务文本
- **ERP tab URL 用 includes**：`t.url.includes('superboss.cc')`（ERP 重定向后子域名变化）
- **targetId 批次复用**：`findErpTarget()` 只调一次，整批 `processOne` 复用同一 targetId
- **等待参数集中管理**：`workflow.js` 的 `TIMING` 统一控制超时、轮询和稳定延时；关联订单加载最多 45 秒、每 1 秒检查一次，点击后先留 1.5 秒启动缓冲
- **状态检测与稳定延时并用**：弹窗、表格和成功状态用 `waitFor` 验证；输入、筛选、仓库和勾选等 Vue 状态切换后保留稳定时间
- **提交不重试**：「创建并收货」点击后只等待明确成功信号，不重复点击，避免重复创建工单

## 结果状态

| 状态 | 含义 |
|------|------|
| `已入库` | 成功创建并收货 |
| `未出库无需入库` | ERP 查无此单（未发货或单号错误） |
| `错误: ...` | 操作异常，附错误信息 |

## 数据说明

- Web 页面通过 SSE 实时展示执行结果，不持久化页面历史，刷新后当前结果会清空。
- CLI 可从 `data/input.txt` 读取单号，并把本次结果写入 `data/results.txt`；每次运行前会清空旧结果。

## 调试

```bash
# 单元回归（不访问真实 ERP）
cd /Users/chat/claude/return-inbound
npm test

# 调试单条单号（需 Chrome 已开 9222）
cd /Users/chat/claude/return-inbound
node cli.js run SF0220494895377

# 查看 ERP tab 状态
node -e "require('./lib/cdp').getTargets().then(ts=>ts.filter(t=>t.url.includes('superboss')).forEach(t=>console.log(t.id, t.url)))"
```

真实单号调试会执行创建并收货，必须先确认售后系统操作队列为空并取得明确授权；测试结束后检查没有残留测试进程。
