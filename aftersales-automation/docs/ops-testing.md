# 技术测试指南

> 适用场景：修改 CLI、采集、ERP 或物流逻辑后的分步验证。完整单元测试仍使用 `npm test`。

`npm test` 必须同时覆盖 `test/*.test.js` 和 `test/**/*.test.js`。不要把脚本改回只跑递归 glob；部分 shell/Node glob 组合会静默漏掉 `test/` 根目录用例。

> 框架入口：`node test.js`，代码在 `test/schemas.js` + `test/runner.js`

## 1. 触发时机（以下情况必须跑）

- 修改了 `lib/` 任意文件或 `cli.js` 之后
- 某个 CLI 步骤连续出错 ≥2 次
- 新增了 CLI 命令（必须先写 schema，再上线）

## 2. 步骤速查

| 步骤ID | 对应命令 | 说明 |
|--------|---------|------|
| JL-1 | `list` | 读工单列表 |
| JL-2 | `read-ticket <工单号>` | 读工单详情 |
| JL-5 | `logistics <工单号>` | 读鲸灵物流（flow-5.3 核心） |
| PM-1 | `product-match <货号> [attr1]` | 商品对应表 |
| PA-1 | `product-archive <specCode>` | 商品档案V2 |
| ERP-1 | `erp-search <子订单号>` | ERP搜索订单 |
| ERP-2 | `erp-logistics <行号>` | ERP物流详情 |
| ERP-3 | `erp-aftersale <退货单号>` | ERP售后入库 |
| JL-3 | `reject`（预检，不提交） | 拒绝退款 |
| JL-4 | `approve`（预检，不提交） | 同意退款 |

## 3. 典型用法

```bash
# 1. 修改了任何代码前，先跑基础设施检查
node test.js l0

# 2. 修改了 logistics.js → 验证 JL-5
node test.js step JL-5 <工单号>

# 3. 修改了 erp-search 相关 → 验证 ERP-1 + ERP-2
node test.js step ERP-1 <子订单号>
node test.js step ERP-2 <子订单号>

# 4. 数据链路验证（步骤间衔接，需有退货快递单号的工单）
node test.js chain <工单号>

# 5. 全量稳定性测试（各只读步骤跑10次，约30分钟）
node test.js all <工单号>
```

## 4. 验收标准

- **单步骤**：≥ 9/10 次成功
- **全量**：所有步骤均 ≥ 9/10
- **新命令上线前**：至少跑对应 step × 3次 + 相关 chain 一遍

## 5. 单元测试隔离

单元测试只能使用模拟依赖，禁止触发真实平台或修改生产运行状态：

- CDP、页面读取、登录、提醒和 `data/` 写入函数必须通过依赖注入进入业务编排；测试 fixture 必须显式提供替身。
- 禁止在被测函数尾部临时 `require()` 带副作用模块，这会绕过 fixture。默认生产依赖统一在 `loadDefaultDependencies()` 装配，业务流程只调用 `dependencies.*`。
- 涉及现有生产缓存的回归，测试前后必须比较文件校验值；发生变化即视为测试失败，即使断言全部通过。
- 测试临时文件只放系统临时目录，并在 `finally` 中清理；浏览器测试还要按本次精确 `targetId` 验证零新增标签页。

平台提醒专项回归：

```bash
shasum data/jl-alerts-cache.json
node --test test/jl/alerts-cache.test.js test/jl/process-single-account-fixed-batch.test.js
shasum data/jl-alerts-cache.json
```

两次校验值必须一致。

---
