# Route Atlas 永久规则入口

本文件保留旧路径兼容，不再承载全部Route Atlas规则。

先读总规则路由：

`docs/rules/README.md`

Route Atlas只按当前任务加载两份永久规则：

- 路线数据、任务知识、当前/从零路线分离、Target Cluster / Spatial Instance / Background Layer、候选插入、Hard Validator、状态重放、炉石、满经验截止、精确优化器、全图审查：
  - `docs/rules/route-atlas-optimization.md`
- 唯一工作台、逻辑步骤、HUD、备注标签、播放/缩放、地图底图、中文标签、离线复制和视觉参数：
  - `docs/rules/route-atlas-ui-and-assets.md`

若任务同时涉及玩家攻略文本/特殊任务机制，再加读：

- `docs/rules/execution-and-mechanics.md`

若任务涉及当前角色裁剪、Journey、发布审计或NEAT边界，再加读：

- `docs/rules/state-and-validation.md`

当前地图的阶段状态、R快照、具体等级/经验、局部顺序和一次性异常只读 `docs/verified-routes/CURRENT.md`、对应NEAT或analysis；永久规则不得从日期化历史文档反推。
