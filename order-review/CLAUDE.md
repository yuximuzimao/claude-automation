# 订单审核系统

项目中文名：订单审核系统

## Session 启动

1. 先读 `AGENTS.md`，其中的只读边界和 ERP 操作限制优先级最高。
2. 再读 `README.md` 和当前任务对应的 `docs/` 设计记录。
3. 修改代码后运行 `python3.13 -m pytest -v`。

## 项目定位

这是快麦 ERP 待审核订单的只读审单辅助工具。第一阶段只读取当前页面序号为 `1` 的订单并展示判断信息，不执行审核、合单、拆单、套件转单品、保存、提交或其他写操作。

## 运行入口

```bash
PYTHONPATH=src python3.13 -m order_review.app
```
