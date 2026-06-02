# 售后系统快递行动待入库为空 - Claude Code 交接

## 背景

用户反馈：售后工单系统里“快递行动”为空，但应当显示“待入库”。

Codex 已完成只读排查，未修改售后系统代码，未重启服务，未执行任何真实业务操作。

## 根因

后端推理已经把退货退款未入库工单判为等待重查：

- 队列状态：`waiting`
- 决策：`decision.action === "reject"`
- 等待标记：`decision.waitingRescan === true`
- 退货快递：`ticket.returnTracking` 存在
- 当前 reason 示例：`仓库未收到退货，剩余24.9h，等待下次扫描自动重查`

但前端“快递行动”的退货待入库筛选条件只认 reason 文案关键词：

- `拆包`
- `尚未入库`
- `在途`

当前 reason 不包含这些词，所以本应进入“退货待入库”的工单被前端过滤掉。

## 当前证据

只读脚本检查当前 live 数据，发现 7 个工单满足“有退货快递 + waitingRescan”，但全部不匹配当前快递行动筛选：

| 工单号 | 退货快递 | 状态 | reason |
| --- | --- | --- | --- |
| `100001779713165352896` | `YT7623311742742` | `waiting` | 仓库未收到退货，剩余24.9h，等待下次扫描自动重查 |
| `100001779361636142812` | `JDX054452047901` | `waiting` | 仓库未收到退货，剩余28.2h，等待下次扫描自动重查 |
| `100001779577812753496` | `YT2588224345204` | `waiting` | 仓库未收到退货，剩余41.6h，等待下次扫描自动重查 |
| `100001779794359850991` | `YT2547527490772` | `waiting` | 仓库未收到退货，剩余41.7h，等待下次扫描自动重查 |
| `100001779938653602115` | `SF0224647068343` | `waiting` | 仓库未收到退货，剩余43.0h，等待下次扫描自动重查 |
| `100001779878460665088` | `73710498335376` | `waiting` | 仓库未收到退货，剩余42.3h，等待下次扫描自动重查 |
| `100001779856305228079` | `73710524359195` | `waiting` | 仓库未收到退货，剩余44.4h，等待下次扫描自动重查 |

队列状态汇总：

```json
{
  "done": 880,
  "waiting": 7
}
```

## 建议修改

修改 `aftersales-automation/public/app.js`，不要只靠 reason 文案判断退货待入库。

建议抽出 helper：

```js
function isReturnWaitingAction(ticket, decision) {
  if (!ticket || !ticket.returnTracking || !decision) return false;
  const reason = decision.reason || '';
  return decision.waitingRescan === true ||
    decision.reasonCode === 'WAREHOUSE_NOT_RECEIVED' ||
    reason.includes('拆包') ||
    reason.includes('尚未入库') ||
    reason.includes('在途') ||
    reason.includes('仓库未收到退货');
}
```

然后同步替换两处筛选：

1. `loadActionBadge()` 中退货待入库计数逻辑。
2. `loadActionList()` 中 `returnsWaiting` / `dismissedReturns` 分类逻辑。

注意：待拦截快递逻辑不要改。无 `returnTracking` 的发出包裹仍然按现有“拦截/在途”逻辑进入待拦截区。

## 验证标准

实施后验证：

- “等待重查”Tab 仍显示 `7`。
- “快递行动”徽标应显示 `7`。
- “快递行动 → 退货待入库”应列出上述 7 个退货快递单号。
- 已标记处理逻辑仍然生效：如果 `data/action-dismissed.json` 中存在对应 tracking，则进入已处理折叠区，而不是主列表。
- 只改前端展示归类，不改变后端推理，不执行退款、拒绝、入库或任何真实业务操作。

## 重启说明

Codex 这边暂时没有配置售后系统重启方式。

本次建议只改 `public/app.js`，原则上刷新浏览器页面即可验证。如果 Node 服务或浏览器缓存导致静态文件未生效，请 Claude Code 按现有售后系统重启方式处理。
