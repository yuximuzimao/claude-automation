# 2026-09 快递行动去重与工单定位完成交接

> 历史完成记录，仅供追溯。当前实现以 `public/app.js` 和 `test/server/live-toolbar-frontend.test.js` 为准。

## 用户可见结果

- “待拦截快递”和“退货待入库”分别按标准化后的运单号去重，同一运单只计数、复制、勾选和标记处理一次。
- 同一运单关联多张售后工单时，不再显示笼统的“关联 N 个工单”，而是用中文分号完整显示每个工单号。
- 只有工单号可点击；物流单号保持纯文本，不触发页面跳转。
- 点击工单号时重新读取实时 queue 状态：`waiting` 跳到“等待重查”，其他活跃状态跳到“待确认”；目标店铺筛选自动恢复为“全部”，避免卡片被旧筛选条件隐藏。
- 目标卡片加载后滚动到屏幕中间，并短暂显示蓝色轮廓。工单已归档、已进入自动执行或状态刚发生变化时只提示，不做错误定位。

## 实现边界

- 去重发生在快递行动汇总层，不改变 queue、simulation、拦截记录或业务推理。
- 同一工单内部与跨工单重复运单统一按 `trim + uppercase` 后的值识别，展示仍保留当前主记录的原始运单文本。
- 合并记录保留所有关联 `queueItemId` 和工单号；最早截止的关联项作为品牌分组、倒计时及标记处理的主记录。
- 待拦截与退货待入库是不同动作，分别去重，不跨面板合并。
- 跳转只在售后系统前端切换标签并定位现有卡片，不打开鲸灵后台、不启动浏览器自动化、不执行真实业务写操作。

## 涉及代码

- `public/app.js`
  - `dedupeActionItems()`：运单去重并保留关联工单。
  - `renderActionOrderLinks()`：完整渲染可点击工单号。
  - `jumpToActionWorkOrder()`：按实时状态切换标签、定位和高亮卡片。
  - `activateTab()`：复用原有标签切换和加载流程。
- `test/server/live-toolbar-frontend.test.js`
  - 覆盖大小写与空格归一化、最紧急主记录、关联工单保留、双工单号显示和跳转契约。

## 验证与提交

- `node --check public/app.js`：通过。
- `node --test test/server/live-toolbar-frontend.test.js`：10/10 通过。
- 去重提交：`0771637 fix(aftersales): dedupe courier action tracking numbers`。
- 工单定位提交：`13ef20e feat(aftersales): link courier actions to ticket rows`。
- 本轮只修改前端与前端契约测试，不涉及 `lib/` 决策逻辑，因此无需重启服务；刷新页面即可生效。

## 当前权威入口

- 面向用户的能力概览：`README.md`
- 前端职责导航：`SKILL.md` 的 `public/app.js` 条目
- 当前代码与测试：`public/app.js`、`test/server/live-toolbar-frontend.test.js`
- 本文只记录完成背景，不承担现役规则或待办职责。
