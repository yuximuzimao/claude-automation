# NEAT阶段归档：2026-08-15 Route Atlas 高清地图资源与中文参考标签

状态：本轮只闭合 Route Atlas 地图资源基础设施与可携带调用契约，不改变当前68级玩家路线、诺森德恢复点或任务顺序。长期规则已经上提到`docs/ROUTE_ATLAS_RULES.md`；本文保存本次资源处理结果、验证口径和剩余回退项。

## N — 当前状态

- `data/routes/maps/manifest.json`当前登记68张任务宇宙地图。
- 其中65张已有实际存在的高清底图，统一尺寸`4008×2672`，高清资产总量约`215.95 MiB`。
- 3张保持原低清/本地化回退图，不强行套不精确高清源：
  - `139` 东瘟疫之地：WotLK需要`ScarletEnclave1–4`探索覆盖层，ClassicTBC高清源缺失；不拿后世`RuinsOfTheScarletEnclave`纹理混用。
  - `1519` 暴风城：WotLK新增港口，TBC高清地图不是精确替代。
  - `4395` 达拉然：现有高清源为特殊地图tile布局，不能安全使用通用4×3/12块拼接器。
- 经典旧世界+外域已生成中文参考地名库：`data/routes/maps/labels-zhcn.json`，当前覆盖50张地图、790个中文区域小标。
- 诺森德高清底图可以正常使用，但当前没有可靠的WotLK zhCN AreaTable区域名源，因此不机器直译，不伪装成客户端本地化真值。
- 当前外域工作台`data/routes/outland-route-atlas.html`已经使用高清赞加/纳格兰底图，并内嵌完整中文小标；赞加自动区域标注25个，纳格兰20个。

## E — 本轮形成的实现与证据

### 1. 高清地图构建方法

新增/固化：

- `scripts/build_hd_route_maps.py`
- `scripts/build_uprez_zone_map.py`
- `scripts/finalize_hd_map_manifest.py`
- `scripts/audit_hd_route_maps.py`

构建源分层：

- 经典旧世界/外域：`keyboardturner/WoWMapUprez_png`的`ClassicTBC`资源。
- 诺森德/死骑区：同仓库`Retail`资源，仅在与当前WotLK低清地图高相关且近零偏移时接受。
- 探索区域叠加坐标：3.3.5 `WorldMapArea.dbc` + `WorldMapOverlay.dbc`。

赞加最初只拼12块基础地图时出现“很多地形缺损”，已确认原因不是高清源丢地形，而是漏掉探索区域overlay。最终构建统一采用：

`12块基础地图 + 当前MapArea对应的全部WorldMapOverlay探索层`

赞加补齐18个探索区域后与低清完整图的结构相关度明显提升，现行高清图已经是完整探索状态。

### 2. 验收分两种模式

最终65张HD中：

- `fallback-correlation`：26张。高清候选缩回现有低清尺寸后，满足结构相关度阈值且最佳对齐偏移接近`(0,0)`；外域/诺森德主要走这一模式。
- `pre-cata-source-trust`：39张。经典旧世界当前Wowhead低清图与pre-Cata地图时代不同，不能拿低相关度误判高清源；改为要求ClassicTBC资源+3.3.5 overlay完整、无缺失piece，并在manifest明确标记来源信任模式。

没有降低阈值来“凑数量”；特殊或缺资源的地图直接回退。

### 3. 中文参考标签数据化

新增：

- `scripts/build_route_map_labels.py`
- `data/routes/maps/labels-zhcn.json`

中文名来源：

- `shagu/pfQuest db/zhCN/zones.lua`
- `shagu/pfQuest db/zhCN/zones-tbc.lua`

位置来源：3.3.5 `WorldMapOverlay.dbc` 的hit rectangle中心；若极少数行没有命中框才退回overlay纹理中心。

这套方法不是按图片OCR或机器翻译，而是用客户端区域ID的中文名称与游戏地图overlay坐标绑定。赞加因此自动补齐了此前漏掉的`环礁湖`、`双塔废墟`等区域，并进一步得到菌杆沼泽、死亡泥潭、血鳞浅滩、蛮沼村、暗泽村等完整参考小标。

### 4. 可携带HTML调用逻辑保持不变

这是本轮用户再次明确要求保留的核心契约：

- 最终HTML运行时仍然只引用同级资源：`maps/<实际地图文件名>`。
- 玩家复制到另一台电脑时，只需保持攻略HTML与`maps/`文件夹的相对目录关系即可离线使用。
- 目标电脑不需要Python、manifest、JSON、网络请求或项目源码。
- `lib/route_map_assets.py`仅用于项目机器“生成HTML时”按`zone_id`选择`hd_file`或回退图；最终HTML必须写死静态相对路径。
- `labels-zhcn.json`同样只用于生成阶段；页面需要的中文小标必须在生成HTML时内嵌，不能要求游戏电脑运行时读取JSON。

为防后续刷新低清缓存破坏成果，`scripts/download_route_map_assets.py`已改为刷新普通地图字段时保留既有`hd_*`元数据和`hd_summary`。

### 5. 统一地图解析层

新增`lib/route_map_assets.py`：

- `route_map_filename(zone_id)`：默认优先manifest中可用的HD文件；
- `route_map_href(zone_id)`：生成`maps/<file>`便携相对路径；
- `route_map_status(zone_id)`：返回HD/回退状态；
- `route_map_labels(zone_id)`：返回可用的zhCN参考小标。

该模块是“构建期工具”，不是浏览器运行时依赖。

## A — 本阶段判断

### 1. 高清地图方向成立

外域与诺森德样板均得到约0.88–0.96的低清结构相关度且零偏移；实际批处理后26张进入严格配准模式。赞加地形缺失问题在补全overlay后解决，说明“高清基础纹理+完整探索层”是正确方法。

### 2. 不应追求形式上的68/68

东瘟疫、暴风城、达拉然各有明确版本/资源结构差异。当前3张回退比错误高清图更安全；未来只有找到与WotLK时代严格匹配的高清源后再替换。

### 3. 中文小标是辅助层，不是底图真值

经典旧世界/TBC已有可靠中文AreaTable来源，因此可批量生成；诺森德没有可靠中文区域表时允许只显示英文高清底图。中文提示是否存在不能阻塞高清地图使用。

### 4. 地图资源已经从“赞加特例”升级为全项目基础设施

后续制作泰罗卡、地狱火、诺森德等Route Atlas页面时，不再单独寻找地图或手写`*-hd`路径。生成器应按`zone_id`消费统一manifest与中文标签库，把最终静态相对路径和需要的小标直接写入HTML。

## T — 下一恢复点

1. 玩家当前主线仍以`docs/verified-routes/CURRENT.md`为唯一恢复入口；本轮地图资源处理不改变68级、奥格瑞玛、下一窗口才设计诺森德地面路线的状态。
2. 新建任何Route Atlas页面时，生成阶段优先使用`lib/route_map_assets.py`选择地图资源，最终HTML仍直接写`maps/<actual-file>`静态路径。
3. 经典旧世界/TBC页面可直接复用`labels-zhcn.json`中文小标；诺森德暂不自动生成中文区域名。
4. 若未来找到可靠WotLK zhCN AreaTable/区域名数据库，再扩展诺森德中文小标；不要先用机器翻译补齐。
5. 若未来找到严格WotLK时代的东瘟疫、暴风城或达拉然高清地图源，只处理这3张回退，不重做已验收的65张。
6. 搬到游戏电脑测试时仍按旧方式复制攻略HTML和同级`maps/`目录；不复制Python/lib也不影响运行。
