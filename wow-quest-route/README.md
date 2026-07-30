# 魔兽世界任务路线

面向国服泰坦重铸“时光”服的五开任务路线项目。Questie提供任务依赖和区域坐标，路线层负责分区与顺序，实测层记录个人拾取、逐号点击、楼层、实际轨迹和后续修正。

## 当前成果

- Questie v11.32.3 Lua数据库解析器；
- 支持读取Questie完整ZIP或已解压插件目录；
- 血精灵圣骑士逐日岛候选路线V2；
- 逐日岛拆分为5个可单独执行的小区域；
- 单文件交互HTML：坐标图、步骤链、任务链、实际历程和路线对比；
- 支持在HTML中选择本地游戏大地图截图作为底图，不上传图片；
- 五开共享、个人拾取和个人交互规则；
- WoW Route Logger只读记录插件及匿名每日导出脚本。

## 生成路线

在项目目录运行：

```bash
python3 cli.py build-sunstrider \
  --questie-source ../_sandbox/wow-quest-route/Questie.zip
```

输出：

```text
data/routes/horde/blood-elf/sunstrider-isle-v2.html
data/routes/horde/blood-elf/sunstrider-isle-v2.md
data/routes/horde/blood-elf/sunstrider-isle-v2.json
```

日常使用优先打开HTML。页面默认只显示一个小区域，可以切换：

- A：太阳之塔起步；
- B：南侧山猫与任务物品环；
- C：西侧树人与神殿环；
- D：法瑟林学院；
- E：出岛信使链。

地图坐标复刻Questie的绘制方式：数据库坐标为区域内0–100坐标，页面按百分比直接标点和连线。路线连线是候选顺序，不代表中间一定可以直线通行。

## 每日实测记录

Questie人物历程只能记录接取、完成、放弃、升级、等级和时间戳，不能记录移动轨迹、事件坐标、任务目标完成位置或五个角色各自进度。

项目附带`WoW Route Logger`，仅记录本地任务事件和移动坐标，不发送按键、不控制角色、不自动接交任务。

安装：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\Install-WoWRouteLogger.ps1
```

当天结束后完全退出游戏，再匿名导出：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\Export-WoWRouteLog.ps1 `
  -BridgePath "你的bridge目录"
```

详见：

- `addon/README.md`
- `docs/DAILY_ITERATION.md`
- `docs/JOURNEY_EXPORT.md`

## 测试

```bash
python3 -m unittest discover -s tests
```

HTML脚本另外使用`node --check`做JavaScript语法检查。

## 迭代原则

先按Questie为各区域生成候选路线，再按任务中心、前置关系和目标坐标拆成小区域。每次只执行一个小区域；跑完后用日志、轨迹和少量异常备注优化该区域，并把已确认的通用规则迁移到后续区域。
