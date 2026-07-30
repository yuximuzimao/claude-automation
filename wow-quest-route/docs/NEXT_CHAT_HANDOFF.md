# 新对话交接：任务路线与坐标导航专项优化

## 当前分支

```text
feat/wow-quest-route
```

## 用户最终确认的模型

- 五个角色始终按一个主控号的移动路线处理；
- 另外四个角色只在必须逐号拾取、点击、接取或交付时提醒切换；
- 不建模五条路线，不计算五个角色的独立移动成本；
- 不安装自制游戏内插件；
- 不采集移动轨迹；
- 不使用输入广播、自动化或客户端注入；
- Questie和WTF只作为退出游戏后的只读离线数据源。

## 当前成果

### 逐日岛人工版

```text
data/routes/horde/blood-elf/sunstrider-isle-v3-navigator.html
```

V3不再显示没有底图的圆圈和路线图。页面改为：

1. 选择小区域与步骤；
2. 输入主控号当前地图X/Y；
3. 从目标的全部Questie刷新点中选最近的具体点；
4. 显示目标坐标；
5. 显示北/东北/东/东南/南/西南/西/西北方向；
6. 显示X/Y应增加或减少多少；
7. 大字号显示当前任务的前置、当前和后续任务。

### 全量自动候选版

```text
data/routes/world-candidate/index.html
```

当前统计：

- 68个户外区域；
- 2852个可定位候选任务；
- 东部王国、卡利姆多、外域、诺森德；
- 排除副本、团队、日常、周常、重复、节日和专业限定任务；
- 保留城市任务及少量血精灵圣骑士可接的中立跨区任务；
- 每个区域独立HTML并自动拆成小区块。

自动算法当前使用：

- 血精灵种族位掩码；
- 圣骑士职业位掩码；
- 任务发布NPC是否对部落友好；
- 前置任务深度；
- 5级等级波次；
- 接取、目标、交付三个阶段；
- 坐标半径聚类；
- 最近邻步骤排序；
- 多刷新点导航时选择离用户当前坐标最近的具体点。

## 关键文件

```text
README.md
cli.py
lib/questie_source.py
lib/route_builder.py
lib/navigator_renderer.py
lib/world_builder.py
data/route-specs/sunstrider-isle.json
data/observations/fivebox-task-types.json
data/journey/current-paladin.json
data/routes/horde/blood-elf/sunstrider-isle-v3-navigator.html
data/routes/world-candidate/manifest.json
data/routes/world-candidate/index.html
tasks/todo.md
```

## 已确认的逐日岛实测

- 打怪任务由主号击杀时五号同步增加；
- 山猫项圈需要逐号查看和拾取，同一尸体不保证每号都有；
- 奥术薄片需要逐号拾取；
- 索兰尼亚三个物品需要逐号点击；
- 达斯雷玛神殿只需主号交互一次，队伍同步；
- 被污染的奥术薄片五号都能触发，位置在建筑上层；
- P01人物历程确认完成8325时已达到2级。

## 当前局限

1. 全量版是自动覆盖，不是68个区域均已人工证明最优；
2. Questie基础数据库已解析，但WotLK修正层尚未完整应用；
3. 中立跨区任务可能出现在非主练级区域；
4. 自动路线不知道山体、道路、楼层和洞穴入口；
5. 没有移动轨迹，后续只能结合人物历程和用户少量反馈优化接交顺序；
6. 逐日岛步骤8、9仍需用户实际验证；
7. 全量区域的小区块标题由首个目标自动生成，部分名称可能不够直观。

## 新对话建议开场

```text
通过CodexPro打开魔兽世界任务路线项目，先阅读：
- wow-quest-route/docs/NEXT_CHAT_HANDOFF.md
- wow-quest-route/tasks/todo.md
- wow-quest-route/README.md

先检查逐日岛V3坐标导航页面是否符合“输入当前坐标→直接告诉方向和目标坐标”的需求。不要恢复抽象地图、移动轨迹或自制游戏插件。然后针对步骤8、9和全量自动路线算法做专项审计。
```
