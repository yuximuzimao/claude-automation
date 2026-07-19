# Order Review Agent Notes

本项目是快麦 ERP 待审核订单的只读审单辅助工具。所有对话和说明用中文。

## 安全边界

- 第一阶段只读当前页面“序号”列为 `1` 的订单。
- 不点击审核、合单、拆单、套件转单品、保存、提交或任何会修改 ERP 数据的动作。
- 未展开订单不能用列表明面信息判断，只提示 `判断：请先展开订单`。
- 套件阻断只看展开后的商品明细，不看 ERP 标签列。

## 读取方式

- CDP 走 Chrome `localhost:9222` 直连，风格参考售后系统：HTTP `/json` 找 tab，`Runtime.evaluate` 执行页面 JS，JS 返回 JSON。
- 不使用 web-access 代理路径。
- 目标页可通过标题 `快麦ERP--待审核订单` / `快麦ERP--订单管理` 或路由 `#/trade/toaudit/` / `#/tradeNew/manage/` 识别。

## 字段约定

- 商品标题最后一个全角括号前是 ERP 标准商品名称，括号内是商品简称。
- 平台 ID 行括号外是 SPU，括号内是 SKU ID；`data-numiid` 是 SPU，不是 SKU。
- 拆分订单或特殊订单可能缺少 SPU / SKU，前端不显示空字段，但模型字段保留。
- 商品卡片默认只展示“简称 x 数量”；标准名、编码、SPU、SKU 放在“展开详情”。

## 常用命令

```bash
PYTHONPATH=src python3.13 -m order_review.app
python3.13 -m pytest -v
PYTHONPATH=src python3.13 -m order_review.app --help
```
