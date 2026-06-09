# 退货入库项目 - 经验教训

## L1: execCommand 在此输入框失效
快递单号输入框 execCommand('insertText') 返回空值不报错。
**解决**：JS click 聚焦 + Input.insertText 通过 CDP typeText。

## L2: 关联弹窗"继续关联"JS click 可能误判成功
点击时弹窗可能已消失（前一次点击残留），JS click 返回 true 但实际无效。
**解决**：先等弹窗出现（waitFor），再点击。

## L3: 退货仓库每次创建后重置
每次成功"创建并收货"后，退货仓库回到"默认仓库"。
**解决**：processOne 每次都调用 selectWarehouse，无条件重新选锦福仓。

## L4: 创建并收货后有二次确认弹窗
"该快递单号被工单xxx关联过N次，确定继续创建工单吗？"
**解决**：点击后先等 1.5s，检查是否有此弹窗，有则点确定再继续。

## L5: querySelector 必须过滤可见元素
ERP 同一 selector 存在多个隐藏元素。必须 querySelectorAll + getBoundingClientRect 过滤。

## L6: "未发货仅退款"类型会残留"提示" el-dialog（2026-06-09）
ERP 搜索"未发货仅退款"快递单号时，除了弹出 `el-message-box`（触发 error 路径）外，还会额外出现一个 `el-dialog__wrapper`（标题"提示"），里面只有"取消"按钮。旧代码的 error 路径只关闭 el-message-box，该 el-dialog 未被关闭，导致弹窗残留。
**修复**：error 路径关闭 el-message-box 后，额外检查 `.el-dialog__wrapper` 中标题含"提示"的弹窗，点击其"取消"或"关闭"按钮（`catch(() => {})` 保证无弹窗时不报错）。
**规则**：error 路径返回前，必须清理所有可见的"提示"类 el-dialog，不能只关 el-message-box。
