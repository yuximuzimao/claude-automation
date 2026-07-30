# 魔兽世界任务路线

面向国服泰坦重铸“时光”服的任务路线项目。路线只按一个主控角色计算，另外四个角色始终视为跟随；只有任务必须逐号拾取、点击、接取或交付时，页面才显示切换提醒。

## 安全边界

- 只离线读取用户已提供的Questie插件文件和退出游戏后保存的Questie人物历程；
- 不安装自制游戏内插件；
- 不采集移动轨迹；
- 不注入客户端、不读内存、不抓包、不自动接交任务；
- 不进行输入广播、同步按键或自动控制角色。

## 当前主成果与可信边界

- `data/routes/simple-leveling-route.html`是单页审阅工具，不代表整条1—80路线已经可直接照做；
- 顶部按地图切换，每张地图显示连续编号清单，可勾选并保存在浏览器；
- 需要逐号收集或点击的任务名直接标红，普通击杀、接交和简单流程的任务名标绿，不再追加独立分类标签；
- 每一步应只对应一个实际地点，炉石、飞行点和回程必须作为路线步骤明确写出；
- 逐日岛1—6级为人工编排并有部分五开实测；永歌森林鹰翼广场至晴风村已根据2026-07-31实测反馈人工修订；
- 永歌森林后半段及12—80级仍是Questie候选数据生成的待审计草稿，不能称为可用攻略，也不能据此判断最优路线；
- 历史RXP元数据只用于参考地图阶段，具体路线必须经过逐地图实跑确认。

生成：

```bash
python3 cli.py build-simple \
  --questie-source ../_sandbox/wow-quest-route/Questie.zip \
  --rxp-source /Users/chat/claude/.ai-bridge/RXPGuides.lua
```

输出：

```text
data/routes/simple-leveling-route.html
docs/NEAT_SIMPLE_LEVELING_ROUTE.md
```

历史RXP SavedVariables只包含当前指南、指南目录和衔接元数据，没有逐步`.accept/.goto/.turnin`路线正文；生成器不会虚构RXP步骤。

## 历史逐日岛V3导航器

生成：

```bash
python3 cli.py build-sunstrider \
  --questie-source ../_sandbox/wow-quest-route/Questie.zip
```

主要输出：

```text
data/routes/horde/blood-elf/sunstrider-isle-v3-navigator.html
```

使用方式：

1. 选择当前小区域和步骤；
2. 在游戏地图上查看主控号当前X/Y坐标；
3. 输入HTML顶部；
4. 页面显示“向北/东北/东/东南/南/西南/西/西北”、目标坐标和X/Y差值；
5. 多个目标分别显示，点击目标即可切换导航。

页面不再尝试用没有底图的圆圈表达怪区。

## 全世界区域候选版

生成：

```bash
python3 cli.py build-world \
  --questie-source ../_sandbox/wow-quest-route/Questie.zip
```

索引：

```text
data/routes/world-candidate/index.html
```

当前自动生成范围：

- 东部王国、卡利姆多、外域、诺森德；
- 血精灵种族与圣骑士职业条件可用的普通户外任务；
- 排除副本、团队、日常、周常、重复、节日和专业限定任务；
- 城市任务和少量可接的中立跨区任务会保留；
- 每个区域独立HTML，并自动拆为小区块。

全量版的作用是先完成覆盖，不代表68个区域都已经人工证明为最优。当前自动算法使用：任务前置深度、5级等级波次、接取/目标/交付阶段、坐标聚类和最近邻排序。

## 人物历程

Questie人物历程可用于离线复盘：

- 接取；
- 完成/交付；
- 放弃；
- 升级；
- 时间戳；
- 事件发生时的等级。

它不记录移动轨迹、目标完成坐标、打怪过程和五个角色各自的实时进度。后续只使用人物历程检查任务顺序和回头交接，不再尝试采集移动轨迹。

导出说明见：

```text
docs/JOURNEY_EXPORT.md
```

## 测试

```bash
python3 -m unittest discover -s tests
```

单页路线JavaScript另外使用`node --check`检查。

## 下一阶段

按实跑优先级继续审计，不再扩展旧导航器：

- 先人工验证逐日岛剩余卡点，再验证永歌森林和幽魂之地的接交批次；
- 按20—30、30—45、45—60、60—70、70—80分段实跑，记录断链、回头路和五开个人操作差异；
- 完整应用Questie WotLK修正层，重新核对任务前置和物品触发任务；
- 每次只修正当前实跑地图，不恢复全地图全清、坐标导航或候选页面。
