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
| `lib/result.js` | 结果状态常量（`STORED`/`NOT_SHIPPED`/`ERROR` 等） |
| `cli.js` | 调试用 CLI，非日常使用 |

## 核心函数（workflow.js 导出）

- `processOne(targetId, tracking)` → `{ status, elapsed }` — 处理单条单号
- `findErpTarget()` → `targetId` — 找到 ERP Chrome tab
- `processAll(trackingNumbers)` — CLI 入口，内部自管 targetId

## 操作流程（processOne）

1. `ensureDialogOpen` — 点击「新建售后工单」按钮，等弹窗出现
2. `ensureFilterCorrect` — 设置筛选：「退货入库」类型 + 快递公司
3. `fillTracking` — 填入快递单号 + 点搜索
4. 判断搜索结果：
   - 无结果（未出库）→ 关闭弹窗，返回 `NOT_SHIPPED`
   - 有结果 → 继续
5. `selectWarehouse` — 选择仓库（第1个 el-select 默认值）
6. `ensureContinueNextChecked` — 勾选「继续下一单」
7. `selectAllItems` — 勾选所有商品行
8. `createAndReceive` — 点「创建并收货」→ 等成功信号
9. 返回 `STORED`

## 关键约束

- **弹窗查找必须精确匹配标题**：所有 `.el-dialog__wrapper` 查找必须验证 `.el-dialog__title` 包含「新建售后工单」，防止多弹窗并存时取到错误弹窗
- **DOM 选择器必须作用域限定**：所有操作在 `wrapper.querySelector` 内进行，禁止 `document.querySelectorAll` 全局查
- **ERP tab URL 用 includes**：`t.url.includes('superboss.cc')`（ERP 重定向后子域名变化）
- **targetId 批次复用**：`findErpTarget()` 只调一次，整批 `processOne` 复用同一 targetId
- **Vue 状态需等待**：filter 变更、仓库选择等操作后需 sleep 等 Vue re-render（见 workflow.js timing 注释）

## 结果状态

| 状态 | 含义 |
|------|------|
| `已入库` | 成功创建并收货 |
| `未出库无需入库` | ERP 查无此单（未发货或单号错误） |
| `错误: ...` | 操作异常，附错误信息 |

## 数据说明

- `data/` 目录：无持久化数据（CLI artifacts 已删除）
- 所有执行结果通过 SSE 实时推送，由售后系统前端展示
- 历史记录不持久化（刷新页面清空），如需记录请在售后系统 history tab 查看 op-queue 日志

## 调试

```bash
# 调试单条单号（需 Chrome 已开 9222）
cd /Users/chat/claude/return-inbound
node cli.js SF0220494895377

# 查看 ERP tab 状态
node -e "require('./lib/cdp').getTargets().then(ts=>ts.filter(t=>t.url.includes('superboss')).forEach(t=>console.log(t.id, t.url)))"
```
