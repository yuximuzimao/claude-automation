# 鲸灵售后自动化

自动处理鲸灵平台（scrm.jlsupp.com）售后工单——扫描、采集、规则推理、退款审批/拒绝。通过 CDP 直连 Chrome 操作鲸灵 SCRM 和快麦 ERP。

## 快速启动

```bash
npm install
node server.js          # 启动 Web 面板 → http://localhost:3457
node scan-all.js        # 扫描所有账号写入队列
```

Web 面板功能：工单队列管理、推理结果确认、历史记录、统计复盘、店铺管理。

## CLI 命令（17 个）

```bash
node cli.js list                              # 读工单列表（≤48h 倒计时）
node cli.js read-ticket <工单号>               # 读单条工单详情
node cli.js logistics <工单号>                 # 读鲸灵物流信息
node cli.js erp-search <子订单号>              # ERP 订单搜索+状态解析
node cli.js erp-logistics [行号]              # 读 ERP 物流追踪
node cli.js erp-aftersale <退货快递单号>        # ERP 售后工单搜索
node cli.js product-match <货号> <attr1> <店铺> # ERP 商品对应表查询
node cli.js product-archive <规格编码>          # ERP 商品档案V2查询
node cli.js approve <工单号>                   # 同意退款（自动处理三层弹窗）
node cli.js reject <工单号> <原因> <详情> [图片] # 拒绝退款（含物流截图上传）
node cli.js add-note <工单号> <备注>            # 添加内部备注
node cli.js remind <工单号> <账号> <原因>        # 创建 Mac 提醒事项
```

## 架构

```
scan-all.js → queue.json → collect.js → simulations.jsonl → infer.js → approve/reject
   (多账号扫描)   (队列)     (数据采集)      (推理结果)     (规则引擎)   (执行)
```

- **Pipeline**（`lib/server/pipeline.js`）：scan → collect → infer → auto-execute
- **Op-queue**（`lib/server/op-queue.js`）：全局操作队列，串行化浏览器操作
- **CDP**（`lib/cdp.js`）：直连 Chrome port 9222，物理点击/JS eval/页面导航
- **常量**（`lib/constants.js`）：扫描时间点、安全边际(8h)、重试上限等共享配置

## 文档

| 文档 | 说明 |
|------|------|
| [SKILL.md](SKILL.md) | AI Agent 运行时上下文入口（必读） |
| [docs/INDEX.md](docs/INDEX.md) | 处理规则、错误分级、已知坑位 |
| [docs/flow-5.1.md](docs/flow-5.1.md) | 退货退款流程 |
| [docs/flow-5.2.md](docs/flow-5.2.md) | 仅退款-未发货流程 |
| [docs/flow-5.3.md](docs/flow-5.3.md) | 仅退款-已发货（含拦截）流程 |
| [docs/flow-5.4.md](docs/flow-5.4.md) | 换货流程 |
| [docs/erp-query.md](docs/erp-query.md) | ERP 商品对应表/档案V2 操作规范 |
| [docs/ops-tech.md](docs/ops-tech.md) | ERP 操作报错/技术排查 |
