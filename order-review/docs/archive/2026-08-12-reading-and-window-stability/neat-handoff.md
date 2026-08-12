# 读取、拆分结果与悬浮窗稳定性阶段归档

归档日期：2026-08-12

本文件记录已完成阶段的根因、实现和验收证据。当前状态以
`../../CURRENT.md` 为准，长期业务规则以
`../../2026-07-23-package-rule-foundation.md` 为准。

## 用户可见结果

- Chrome 151 应用脚本错误报告没有窗口时，审单工具仍能保守识别唯一的快麦待审核页。
- 浮窗贴在 Chrome 主浏览器左侧，随主窗口移动和最小化；其他应用前台时隐藏。
- Stage Manager 切回 Chrome 时，浮窗能加入当前画面，但不会把 Chrome 和其他窗口
  切走、只留下浮窗。
- Chrome 内出现售后执行确认框等临时窗口时，浮窗仍跟随主浏览器，不吸附到弹窗。
- 拆分结果读取使用规划层稳定身份，结果对象缺少 `match_key` 时不再直接中断。

用户在全部窗口修复部署后确认“现在非常好”，本阶段界面稳定性收口。

## 根因与最终实现

### Chrome 读取失败

Chrome 151 的应用脚本接口在真实窗口可见时仍可能返回 `0` 个窗口。订单页识别在
无法取得活动标签 URL 时，回退到 macOS 辅助功能窗口标题，但仍要求 CDP 中只有
一个待审核页；回退不点击、展开或提交 ERP。

机器同时存在自动化 Chrome 和无窗口的普通 Chrome 进程。辅助功能读取不再按
同名进程取第一个，而是枚举拥有窗口的 Chrome 进程。

### 浮窗位置和调度画面

旧实现用 Tk `withdraw/deiconify` 加 1.5 秒主线程 AppleScript 轮询，切换响应慢，
并且不能表达 Stage Manager 的跨应用浮动窗口语义。最终实现为：

- `NSWorkspace.frontmostApplication` 每 `100ms` 读取前台应用。
- 慢速 Chrome 边界读取移到后台线程，避免阻塞 Tk。
- 原生窗口使用附件应用、浮动层、跨空间和
  `NSWindowCollectionBehaviorCanJoinAllApplications`。
- 显示使用普通 `orderFront_`；禁止 `orderFrontRegardless` 和
  `unhideWithoutActivation`。后两者会让 Stage Manager 把审单浮窗作为独立场景
  呈现，出现 Chrome 已获焦点但所有 Chrome 窗口被切走、桌面只剩浮窗的问题。

### Chrome 临时确认框

旧辅助功能脚本读取 `front window`。确认框停留超过下一次 1.5 秒边界采样后，会被
误认成主浏览器，浮窗因此移动到确认框旁边。最终实现会读取全部 Chrome AX 窗口，
优先选择标题带 Chrome 主窗口身份、面积最大的标准浏览器窗口；对话框只影响焦点，
不影响跟随坐标。

### 拆分结果身份

拆分后的 ERP 原始 `OrderSnapshot/Product` 在结果核对前转换成规划层
`SourceSnapshot/SourceProduct`，统一使用稳定商品和平台子订单身份。接口成功不等于
结果确认；目标行、逐包明细、平台子订单号全集和商品数量仍须全部通过才继续审核。

## 验证

- 窗口问题在修复前通过真实 Stage Manager 切换和屏幕截图稳定复现。
- 修复后同样切换步骤保留 Chrome 主窗口和浮窗并排显示，连续切换 3 轮未复现抢场景。
- Chrome 主窗口与前台确认框双窗口回归证明浮窗坐标只取主浏览器。
- 完整测试：`241 passed`。
- 正式悬浮窗按精确旧 PID 替换，验收后只保留一个运行实例；测试无新增残留进程。

## 相关代码

- `src/order_review/macos_companion.py`
- `src/order_review/window_position.py`
- `src/order_review/ui.py`
- `src/order_review/erp_reader.py`
- `src/order_review/split_result.py`
- `tests/test_macos_companion.py`
- `tests/test_window_position.py`

下一阶段不继续扩展窗口功能，转入纸箱与商品尺寸数据收集以及拆分推荐算法讨论。
