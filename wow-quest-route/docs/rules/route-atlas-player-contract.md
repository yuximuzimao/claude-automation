# Route Atlas 玩家前端规则入口

用途：这是Route Atlas玩家前端规则的**总路由**，不是一份大而全的规则正文。玩家前端被拆成三个互不重叠的owner；任何其它文档只能引用这些owner，不能复制第二套规则。

## 第一目标

Route Atlas是跑任务时直接看的执行工具，不是知识库、审计报告或实测记录。

玩家可见内容共同服从：

**让玩家以最低脑力、最快速度，一眼知道现在去哪、做什么、怎样避免做错。**

如果一条文字删掉后，玩家凭当前步骤和游戏插件仍能同样正确、同样快地执行，就不应出现在玩家前端。

## 三个唯一owner

### 1. 路线结构与动作

读：[`route-atlas-route-display.md`](route-atlas-route-display.md)

负责：

- 地点 / NPC；
- `接 / 做 / 交`与交通动作；
- 步骤标题 / 摘要；
- `stepGroups`分段；
- 路线动作的语义颜色与层级；
- Route Profile如何形成HUD动作结构。

不负责任务机制备注。

### 2. 任务标签与备注

读：[`route-atlas-task-presentation.md`](route-atlas-task-presentation.md)

负责：

- Task Card事实如何压缩成玩家信息；
- `共享 / 不共享 / 依次拾取 / 待实测`标签；
- 任务备注；
- 备注角标 / 危险强调语义；
- 用户确认的人工推荐备注override；
- 标签与备注独立，不互相推导。

不改变路线顺序。

### 3. 页面、地图与资源工程

读：[`route-atlas-ui-and-assets.md`](route-atlas-ui-and-assets.md)

负责：

- 页面布局与视窗；
- HUD/状态卡容器；
- 地图底图与中文标签；
- 路线动画线、线宽与CSS实现；
- 控件；
- 离线资源与构建技术契约。

不定义任务/路线业务语义。

## 加载规则

- 只改任务标签/备注：只读Task Presentation；若需要核验任务事实再读Task Mechanics。
- 只改路线步骤/接做交/地点/NPC：只读Route Display；若改变真实路线顺序再读Route Optimization。
- 只改地图/控件/CSS/离线资源：只读UI & Assets。
- 同时改多个领域：加载对应多个owner，不因为“Route Atlas改动”就默认读取全部规则。
- 完整发布/重新生成时，由Route Lifecycle SOP根据实际变更组合对应owner与测试。

## 禁止形成第二套前端规则

本文件只拥有“前端第一目标 + 三owner边界”。

具体颜色、角标、共享标签、备注模板、步骤分段、CSS参数和发布测试都必须只在其对应owner定义；SOP、ERROR-BOOK、Builder、测试和历史页面不得复制成另一套可独立演化的规范。
