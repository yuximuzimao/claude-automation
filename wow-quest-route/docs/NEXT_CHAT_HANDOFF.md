# 新对话交接：路线算法专项优化

## 当前状态

项目分支：`feat/wow-quest-route`

当前可运行成果：

- Questie v11.32.3原始数据库解析；
- 逐日岛候选路线V2；
- 逐日岛A–E五个小区域；
- 单文件交互HTML；
- P01人物历程；
- 五开实测规则；
- WoW Route Logger及每日匿名导出脚本。

核心文件：

```text
data/route-specs/sunstrider-isle.json
data/observations/fivebox-task-types.json
data/journey/current-paladin.json
data/routes/horde/blood-elf/sunstrider-isle-v2.html
lib/questie_source.py
lib/route_builder.py
lib/html_renderer.py
addon/WoWRouteLogger/
tools/Install-WoWRouteLogger.ps1
tools/Export-WoWRouteLog.ps1
```

## 已确认事实

- 当前未安装RXP；路线不能依赖RXP。
- Questie数据库存储AreaID下的0–100区域坐标。
- Questie将AreaID转换为UiMapID，并把坐标除以100交给HereBeDragons画世界地图/小地图图标。
- P01历程：2026-07-28，等级1→6，完成8325时已经2级；记录在接取8334时结束。
- 五个账号的Questie账号级SavedVariables几乎相同，不能用其区分五个当前角色。
- 打怪任务五号同步增加。
- 山猫项圈、奥术薄片需要逐号拾取；同一尸体不保证每号都有山猫项圈。
- 索兰尼亚三个物品需要逐号点击。
- 达斯雷玛神殿只需一次交互，队伍进度同步。
- 被污染的奥术薄片五号均成功触发，目标在建筑上层。

## 当前路线的局限

V2仍然是“数据支持的候选路线”，不是经过数学优化证明的最优路线：

1. 步骤顺序由人工根据任务依赖和坐标编排；
2. 多刷新点目标当前使用平均代表坐标，可能偏离密度峰值或实际入口；
3. 连线只表示访问顺序，不表示道路可直线通行；
4. 没有正式目标函数和路线评分；
5. 未建模五号切窗口、个人拾取、任务交互和等级门槛的时间成本；
6. P01人物历程无移动轨迹，无法验证实际道路；
7. 8334以后没有本次人物历程验证。

## 新对话应集中解决

1. 定义路线优化目标函数和权重；
2. 审计A–E分区边界；
3. 审计每个区块内部步骤顺序；
4. 为多刷新点目标选择更合理的代表点或目标区域模型；
5. 区分固定NPC/物体点、怪物分布区、掉落来源区、建筑楼层；
6. 设计任务依赖约束下的候选路线生成与评分算法；
7. 确定首次扩展范围：永歌森林第一个任务中心，还是整个永歌森林；
8. 确定是否在HTML中加入候选路线A/B比较和每区块完成按钮。

## 建议的新对话开场

```text
通过CodexPro打开魔兽世界任务路线项目，先阅读：
- wow-quest-route/docs/NEXT_CHAT_HANDOFF.md
- wow-quest-route/tasks/todo.md
- wow-quest-route/data/route-specs/sunstrider-isle.json
- wow-quest-route/data/routes/horde/blood-elf/sunstrider-isle-v2.html

这次不要继续扩展区域，先针对逐日岛路线算法、A–E分区和步骤顺序做一次专项审计。明确目标函数、约束、候选生成方式和当前V2可能不优的地方，再提出可验证的V3方案。
```
