# 新对话交接：1—80级极简任务路线实跑审计

## 当前分支

```text
feat/wow-quest-route
```

## 用户最终确认的目标

- 最终用户入口只有`data/routes/simple-leveling-route.html`；
- 页面只展示一条从血精灵出生点到80级的推荐路线；
- 顶部按实际地图名称切换，一次只显示当前地图的编号清单；
- 一个主控号负责移动和普通击杀，另外四个角色始终跟随；
- 只有接交、个人拾取、点击或技能必须逐号执行时才显示简短提醒；
- 不恢复坐标导航器、68区域页面、抽象地图、任务链图、候选评分或全地图全清目标。

## 当前成果

```text
data/routes/simple-leveling-route.html
docs/NEAT_SIMPLE_LEVELING_ROUTE.md
data/route-specs/simple-leveling-route.json
lib/simple_route.py
tests/test_simple_route.py
```

生成命令：

```bash
python3 cli.py build-simple \
  --questie-source ../_sandbox/wow-quest-route/Questie.zip \
  --rxp-source /Users/chat/claude/.ai-bridge/RXPGuides.lua
```

当前生成结果：

- 42个非空连续地图阶段；
- 831个可勾选步骤，773个选入任务；
- 60个唯一`【打怪掉物·必做】`任务；
- 197个唯一`【打怪掉物·可跳】`任务；
- 所有257个掉落任务均能反查到用户页面中的对应标签；
- 前置闭包补入10个任务，删除143个前置不可达任务，最终未满足前置为0；
- 13项单元测试通过；页面JavaScript通过`node --check`。

## 数据边界

### Questie

- v11.32.3是任务存在、血精灵/圣骑士条件、前置关系和任务目标类型的主要依据；
- 当前仍使用基础数据库，WotLK Quest/NPC/Object/Item修正层尚未完整应用；
- 68区域候选JSON只作为任务清单和接取/目标/交付顺序来源，旧HTML界面未复用。

### RXP

主工作区文件：

```text
/Users/chat/claude/.ai-bridge/RXPGuides.lua
```

已确认：

- 当前指南组为`RestedXP 部落 1-30`；
- 当前指南为`01-06 永歌森林`；
- 有213项指南元数据，可参考等级段、地图顺序和下一指南；
- 没有`.accept/.goto/.turnin/.complete`或步骤表，不能虚构完整RXP路线；
- 当前AddOns没有安装RXP，该文件仅是历史SavedVariables。

## 人工验证状态

- 逐日岛1—6级：人工编排并有部分五开实测；西侧树人/神殿顺序与菲伦德雷徽记仍需确认。
- 永歌森林6—12、幽魂之地12—20：RXP地图顺序约束下的Questie自动推导，尚未人工逐步审计。
- 20—80级：均为自动推导，尚未完整实跑；不能宣称已验证最优或绝对不断链。

## 下一步

1. 实际打开单页HTML，先验证字号、标签切换、勾选保存和逐日岛步骤是否直观。
2. 将永歌森林、幽魂之地升级为人工审计版，优先检查接交批次和可跳掉落任务。
3. 按20—30、30—45、45—60、60—70、70—80逐段实跑并记录断链、回头和经验不足。
4. 完整应用Questie WotLK修正层后重新生成并比较差异。
5. 只修正当前实跑地图，不继续扩展旧导航器。
