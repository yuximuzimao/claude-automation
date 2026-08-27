# 拆分审单等待时序阶段归档

归档日期：2026-08-27

本文件记录已完成阶段的根因、实现和验收证据。当前状态以
`../../CURRENT.md` 为准，长期业务规则以
`../../2026-07-23-package-rule-foundation.md` 为准。

## 用户可见结果

混合拆分并审核的四个关键节点增加了页面稳定等待，减少因 ERP 页面未稳定就
读取或点击导致的误停：

- 点击主“确定”后，等待 `1s` 再探测二次确认弹窗；
- 拆分接口确认成功后，保持等待 `300ms` 再探测结果行（原有，未变）；
- 每次真实展开结果行后，等待从 `300ms` 延长到 `600ms` 再读取完整商品明细；
- 全部结果明细核对通过后，等待 `1s` 再探测普通审核菜单入口。

等待不能替代验证：所有等待结束后仍须重新核对目标系统订单号、勾选状态、
明细完整性和审核入口。

## 根因与最终实现

旧时序只有两段 `300ms`：拆分接口确认成功后等 `300ms`、展开结果行后等
`300ms`。实际执行中，点击主“确定”后立即探测二次确认、以及明细核对通过后
立即探测审核菜单，均未给 ERP 页面留出稳定时间，读取易落在过渡态。

最终把等待时序细化为四段，并同步更新 `AGENTS.md` 的等待时序描述：

- `SPLIT_SECONDARY_CONFIRM_SETTLE_SECONDS = 1.0`（新增）：
  点击主“确定”后等待再探测二次确认，`split_runner.py` 主流程确认点击之后。
- `SPLIT_RESULT_RENDER_SETTLE_SECONDS = 0.3`（保持）：
  拆分接口确认成功后等待再探测结果行。
- `SPLIT_RESULT_EXPANDED_SETTLE_SECONDS = 0.6`（`0.3` 改 `0.6`）：
  每次真实展开结果行后等待再读明细，`split_probe.py`。
- `SPLIT_AUDIT_MENU_SETTLE_SECONDS = 1.0`（新增）：
  明细核对通过后等待再探测普通审核菜单入口。

填写、添加包裹和两级确认之间仍保留 `300ms` 人工可见停顿（
`SPLIT_ACTION_PAUSE_SECONDS`），状态轮询间隔仍为 `100ms`，未受影响。

## 验证

- `python3.13 -m pytest -q` 全量 `295 passed`（62s），无回归。
- 测试对等待时长以常量引用断言，常量值调整后自动适配，未硬编码旧值。

## 相关代码

- `src/order_review/split_runner.py`
- `src/order_review/split_probe.py`
- `AGENTS.md`
- `tests/test_split_runner.py`
- `tests/test_split_probe.py`

下一阶段不继续扩展等待时序，按 `CURRENT.md` 转入尺寸计算接入推荐兜底。
