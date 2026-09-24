# Route Atlas 页面、地图与资源工程规则

用途：这是Route Atlas中**页面外壳、控件、地图、动画线、视窗、CSS实现和离线资源**的唯一工程owner。

本文件不决定：任务怎么做、备注写什么、共享标签是什么、接/做/交如何编排。路线动作语义见`route-atlas-route-display.md`；任务标签/备注见`route-atlas-task-presentation.md`。

## 1. 唯一正式工作台

正式运行时只保留一份：

`data/routes/route-atlas-workbench.html`

所有Route Profile在同一工作台通过选择器切换，不为每张地图/职业生成独立正式HTML。

禁止重新建立：

- `<zone>-preview.html`；
- `<zone>-current.html`；
- `<zone>-authoritative.html`；
- 其它与正式工作台并行的玩家执行HTML。

历史版本进入archive，不作为现役页面模板。

目标游戏电脑运行时只依赖：

`route-atlas-workbench.html + maps/`

不得运行时依赖Python、项目JSON、manifest或网络资源。

## 2. 页面布局

当前稳定外壳：

`标题/状态 → 控制条 → 全宽地图 + 左上HUD → 图例/必要辅助 → 步骤列表 → 页脚`

原则：

- 地图是主要空间视图；
- HUD是当前步骤的执行信息容器；
- 页面外壳不能强迫业务规则为了布局重复/截断信息；
- 无行动价值的常驻说明/图例默认不显示。

业务字段“显示什么”由Route Display/Task Presentation决定，本文件只决定容器位置和视觉实现。

## 3. 地图视窗行为

- 地图固定以完整路线全图作为玩家视角；
- 切步骤、上一/下一段、播放、切Profile均不得自动放大；
- 现役工作台不再提供“完整路线 / 已走+当前 / 只看当前”视图模式，也不提供“跟随当前段”或其它玩家侧缩放/裁剪开关；
- 底层仍保留统一0—100坐标语义，仅用于路线点线、动画和中文地名定位，不再为已取消的视图模式维护第二套状态。

## 4. HUD容器

- HUD位于地图左上；
- 宽度保持稳定，内容高度自适应；
- 可收起；收起/展开按钮固定放在HUD自身标题栏右侧，不放到页面全局控制条，保证鼠标操作始终贴近浮窗；
- 正文超过地图卡可视高度时，HUD内部纵向滚动；
- 禁止继续向下撑出地图区域后被外层裁掉；
- 当前step切换时HUD内容同步更新；
- HUD标题固定显示当前步骤序号与总步骤数，例如 `步骤 6/12 · 标题`，步骤列表同时保留自己的序号；
- Task Presentation状态标签直接贴在对应任务名前，备注区只渲染真正的备注文本，不再为“共享/不共享/依次拾取/特殊/待实测”单独复制任务行。
- HUD正文沿用旧正式工作台的14px字号；HUD标题保持15px。页面主体、步骤列表与控制条本身不因HUD字号调整而缩放。
- 路线动作专用色：`开飞行点`使用暖橙`#ff9f68`，`绑定炉石`使用紫色`#cf9cff`；两者与接/做/交及地点色分离。
- 有有效备注时，备注区必须显示独立的“备注”标题，再按`《任务名》：备注内容`渲染；备注正文不得再次重复当前任务完整名称。

HUD内部字段结构由Route Display/Task Presentation生成；UI不得自行从旧point/note拼第二套文案。

## 5. 状态卡与时间容器

页面可以提供Route Profile级状态容器，例如：

- 炉石链；
- 预计总时间；
- 可靠实跑范围。

当前稳定布局：右上状态区直接显示值，不额外增加“炉石与时间”“当前状态”等无信息小标题。

当前步骤预计时间固定放在HUD标题栏中、紧跟步骤标题的次级位置，保持旧正式页的“标题 + 本段预计 + 收起按钮”横向结构。无论Timing是否已有数值，都必须保留“本段预计”容器：有值时显示例如 `本段预计：约25分钟（18分钟—34分钟）`，没有值时显示 `本段预计：—`。这里的破折号只是布局占位，不代表模型生成了时间。

是否有值、字段语义和文本由Route Display/Timing结果决定；本文件只固定容器/视觉层级。

没有可靠实跑值时，UI不得生成“实测：暂无”之类伪数据占位；“本段预计：—”是唯一允许的时间容器空态。

## 6. 控制行为

至少支持：

- Profile/地图切换；
- 当前段播放；
- 剩余路线播放；
- 上一段/下一段；
- 步骤列表点击跳转；
- HUD收起/展开；
- 记住上次使用的Profile，并分别记住每个Profile最后停留的step；刷新/重新打开页面后恢复该状态。

播放不再提供速度下拉；固定使用1.8×播放倍率。底层仍以普通路线边约1.4秒、炉石/固定任务传送类跳转约0.85秒作为1×基准，由唯一`PLAY_RATE=1.8`统一加速。若以后修改速度，只改这一处播放倍率，不重新增加玩家侧速度档位。

上一/下一段切换后不自动zoom；地图始终保持完整路线视角。

业务上的“步骤是什么”由Route Profile/Route Display决定；UI不重新切分stepGroups。

## 7. 地图底图

- 清晰度优先；
- 必须保持现有0—100坐标几何一致；
- 替换底图前检查边界、比例、锚点配准；
- 未配准通过不得切换；
- 不为了内嵌中文地名退回低分辨率图。

高清英文底图缺中文时，用独立HTML标签叠加；现役正式视觉以旧工作台的 `span.mapLabel` 为兼容基线，不再改用SVG `text` 重新设计字体：

- 现役工作台默认显示已有中文标签，不再提供玩家侧开关；
- 标签以同一0—100地图坐标换算为绝对定位百分比，中心锚定 `translate(-50%,-50%)`；
- 字体链固定为 `-apple-system, "system-ui", "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif`，11px / 400；
- 文字为暖白 `rgb(247,239,216)`，背景 `rgba(6,12,18,.62)`，4px圆角，`2px 5px`内边距，`0 1px 2px`黑色阴影，`white-space: nowrap`、`pointer-events: none`；
- 低干扰；
- 标签始终使用完整路线的统一viewBox；
- 标签不是坐标真值；
- 没有可靠zhCN区域数据时允许只用高清英文底图，不机器直译冒充客户端真值。

现役标签资源：

- `data/routes/maps/labels-zhcn.json`
- `scripts/build_route_map_labels.py`
- `lib/route_map_assets.py`
- 若某条正式路线只展示一组低干扰精选标签或需要视觉避让坐标，保存到`data/route-ui/<profile_id>.json`；这是UI展示配置，不进入Route Profile，也不得反向解释为路线点坐标。

## 8. 地图资源池与离线复制

- HTML固定在`data/routes/`；
- 地图固定在同级`data/routes/maps/`；
- HTML只通过`maps/<实际文件名>`引用地图；
- 中文标签等运行时数据在构建时内嵌；
- 玩家复制时只需HTML与整个`maps/`目录；
- 地图资源尽量提前缓存，不在每次跑路线时联网下载；
- 稳定命名：`<zone_id>-<slug>.<ext>`；
- `manifest.json`可以记录来源、缺失、回退、HD元数据，但不是运行时依赖。

资源生成器：

- `scripts/download_route_map_assets.py`
- `scripts/build_hd_route_maps.py`
- `lib/route_map_assets.py`

## 9. 路线动画线视觉参数

除非用户明确要求修改视觉系统，当前冻结参数：

- 普通路线线宽`1.25`；
- 当前段线宽`3.0`；
- 炉石普通`1.8`；
- 当前炉石`3.4`；
- 箭头marker `5×5`；
- `markerUnits="strokeWidth"`；
- `vector-effect="non-scaling-stroke"`。

不同Profile/地图不得无理由漂移。

## 10. 业务语义到CSS的实现边界

Route Display/Task Presentation拥有语义，例如：

- 交/接/做分别属于什么颜色角色；
- 共享/不共享/依次拾取/特殊/待实测是何种标签；
- 危险词需要高风险强调；
- 备注引用角标属于何种结构。

本文件只负责把这些语义token实现为统一CSS组件：

- 同一语义全工作台使用同一class/token；
- 地图builder不得自己复制一套颜色；
- CSS值改变不改变业务语义；
- `五开待实测`是玩家需要重点关注的未验证状态，统一使用红色高强调标签；其它状态继续按各自既定token显示；
- 业务规则改变时UI实现只消费新token/结构，不推断业务含义。

具体当前色值以工作台CSS的统一token为实现真值；后续治理数据化时应集中为单一变量区，避免散落硬编码。

## 11. 不允许的页面回退

- 不得把旧plaintext HUD作为semantic HUD缺失时的静默业务回退；
- 不得从旧HTML提取备注/共享状态填回新Profile；
- 不得通过prototype/fallback重新注入过时任务文案；
- 技术错误应明确失败或降级为“无法渲染该业务字段”，不能生成看似正常但语义过期的页面。

## 12. 技术构建门禁

UI/资源修改至少验证对应项目：

- 输入JSON/聚合数据可解析；
- HTML可重新构建；
- JS语法通过；
- 地图路径为`maps/`相对路径；
- 默认全图/跟随开关行为正常；
- HUD滚动/收起正常；
- 不产生第二份正式HTML；
- 离线资源齐全；
- 相关CSS/DOM token存在；
- 没有旧fallback重新生成业务文案。

具体“改什么跑哪个测试”由`tests/README.md`维护。本文件定义工程契约，不复制测试命令。

## 13. 正式渲染操作

- 当前Publisher payload已经fresh时，单Profile资源渲染：`python3 scripts/render_route_assets.py <profile_id> --output-dir <dir>`。
- `REPUBLISH_ONLY`只允许从当前fresh Publisher payload重渲染，不重算Task Card/Profile/Timing/XP/Economy。
- 渲染脚本不会自行选择或覆盖正式目录；正式页面替换只有Final Audit/cutover通过后才能执行。
- 地图资源需要单独刷新时使用本文件§8列出的资源生成器，不让Publisher承担地图下载/高清化。

## 14. 本文件明确不负责

- 路线怎么排：`route-atlas-optimization.md`；
- Route Profile/生命周期：`route-profile-and-lifecycle.md`；
- 路线步骤/接做交/NPC/地点语义：`route-atlas-route-display.md`；
- Task Card→共享标签/备注/角标：`route-atlas-task-presentation.md`；
- 时间公式：`timing-and-benchmarking.md`；
- Publisher payload组合：`route-atlas-player-contract.md`；人工冷读与cutover判断：`route-lifecycle-final-audit.md`。
