# 审单悬浮窗

快麦 ERP 待审核订单的只读审单辅助工具。

第一阶段只做当前页面序号 `1` 订单的展开明细读取和桌面悬浮窗展示，不执行审核、合单、拆单、套件转单品、保存或提交。

当前版本会通过 Chrome DevTools `localhost:9222` 读取 ERP 当前页，找到“序号”列为 `1` 的订单；如果订单未展开，只提示先展开；如果已展开，会展示商品简称、数量、可合单标记，并把标准名、编码、SPU、SKU 放在每个商品的“展开详情”里。

## 运行

前提：Chrome 已用远程调试端口 `9222` 打开 ERP 页面。

```bash
PYTHONPATH=src python3.13 -m order_review.app
```

## 测试

```bash
python3.13 -m pytest
```

## 当前设计依据

- [第一阶段设计记录](docs/2026-07-09-order-review-floating-window-design.md)
