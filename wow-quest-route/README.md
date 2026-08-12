# 魔兽世界五开打金任务路线

面向国服泰坦重铸“时光”服的五开任务与打金路线项目。路线只按一个主控角色计算，另外四个角色始终视为跟随；只有任务必须逐号拾取、点击、接取或交付时，页面才显示切换提醒。

## 当前项目目标

当前唯一主线是**先把首组五个血精灵圣骑士连续练到80级**；死亡骑士计划暂缓，等圣骑士80级以后再决定。

50级以后路线方法改为“按成熟地图主轴依次推进 + 单地图全清”：安戈洛约50—58；达到外域进入条件后，外域各地图依次全清；约68级进入诺森德后继续按地图弧线推进。单地图内部优先解决接取/交付链和地形顺序，目标是最少转圈、最少重复横穿，而不是为了少量任务频繁换地图。

`data/routes/dk-55-80-world-tasks.html`继续保留为死亡骑士历史/后续母版，但不再是当前主页面或当前玩家决策依据。

首组圣骑士的当前玩家执行入口不使用HTML或自动候选页。继续实跑时先读`docs/verified-routes/CURRENT.md`，再打开其中指定的唯一攻略。生成或修订路线必须遵循`docs/verified-routes/ROUTE-DESIGN-PROCESS.md`，优先复用`docs/task-library/`的逐任务核验资料；脚本只提供基础数据，不能替代前置、地形、任务链和实际五开机制判断。

## 安全边界

- 只离线读取用户已提供的Questie插件文件和退出游戏后保存的Questie人物历程；
- 不安装自制游戏内插件；
- 不采集移动轨迹；
- 不注入客户端、不读内存、不抓包、不自动接交任务；
- 不进行输入广播、同步按键或自动控制角色。

## 当前主成果与可信边界

- `docs/verified-routes/CURRENT.md`及其唯一执行稿是当前圣骑士1—80主线真值；50级后的任务路线逐地图重新人工排序，不再受旧55级停止线约束。
- `data/routes/simple-leveling-route.html`继续保留为圣骑士早期历史参考；50级以后以“单地图全清、最少转圈”的分区任务单为主。
- `data/routes/dk-55-80-world-tasks.html`保留为死亡骑士后续母版，当前不执行、不因55级到达而自动切换。
- 两份页面都按地图切换，显示连续编号清单，可勾选并独立保存在浏览器；不同路线使用不同本地存储键，不会互相覆盖进度。
- 红色只表示会被“五个角色分别收集 × 多个数量 × 随机掉落/重复点击”显著放大的高负担任务；单个命名怪必掉物和单次固定点击仍标绿。
- 任务名可展开查看基础经验、前置、重点目标、地点和流程；地图步骤继续保留距离档位与“标记过远”反馈。
- Questie提供任务、前置和静态坐标；自动排序不能识别洞穴入口、建筑楼层、封闭城门、动态位面和服务器特有限制，必须由第一轮实跑修正。
- 历史RXP元数据只用于参考地图阶段，不含逐步路线正文，不能替代Questie任务库和实跑反馈。

生成当前死亡骑士主母版：

```bash
python3 cli.py build-dk-world \
  --questie-source /Users/chat/claude/.ai-bridge/Questie.zip
```

输出：

```text
data/routes/world-candidate-dk/
data/routes/dk-55-80-world-tasks.html
docs/DK_55_80_WORLD_TASKS.md
```

重建首组圣骑士参考页：

```bash
python3 cli.py build-simple \
  --questie-source /Users/chat/claude/.ai-bridge/Questie.zip \
  --rxp-source /Users/chat/claude/.ai-bridge/RXPGuides.lua
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
- `build-world --profile paladin`生成血精灵圣骑士候选库，`build-world --profile death-knight`生成血精灵死亡骑士候选库；
- 排除副本、团队、日常、周常、重复、节日和专业限定任务；
- 城市任务和少量可接的中立跨区任务会保留；
- 每个区域保留候选JSON与历史导航页，新的死亡骑士全任务母版把55—80级任务合并到一个现有样式的单页中。

全量候选库的区域数量会随角色和阵营过滤变化：历史圣骑士候选库为68个区域，当前死亡骑士候选库为65个可用区域。它们用于先完成覆盖，不代表区域都已经人工证明为最优；洞穴入口、楼层、封闭区域和动态位面仍由实跑补正。

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

按新的打金循环目标继续推进：

- 当前首组圣骑士只要求安全、稳定地到55级；继续记录任务接不到、城门或位面阻断、洞穴死亡和明显折返，但不再要求先把1—55路线优化到速通标准。
- 创建第一组死亡骑士后，从`dk-55-80-world-tasks.html`开始逐图全清。每张地图记录实际耗时、任务金币、掉落收益、死亡次数、逐号操作次数和必须跳过的阻断任务。
- 根据第一轮数据确定“主要打金图”，将其提升为固定主流程；低收益、高死亡、长等待或动态位面不稳定的任务移入跳过清单。
- 第二组及后续死亡骑士重复同一轮次，用人物历程验证任务顺序和回头交接，直到主要地图流程稳定。
- 完整应用Questie WotLK修正层，重新核对任务前置、物品触发任务与死亡骑士职业任务。
