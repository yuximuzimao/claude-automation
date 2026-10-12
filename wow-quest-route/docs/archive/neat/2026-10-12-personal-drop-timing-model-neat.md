# 2026-10-12 五开个人掉落 Timing 模型收口

本轮针对龙骨荒野第二组DK实跑中暴露的“随机掉落任务预计偏短”问题，收口个人掉落类任务的统一Timing计算规则，并以11999《寻找线索》作为首个实测校准样本。

## 统一规则

- `personal-drop-count`不再按“最慢角色完成窗口”估算。
- 当Task Card已明确选择该Timing规则族时，`fivebox.status`参与独立需求份数计算：
  - `not_shared`：单号需求量 × 当前队伍人数；五开即5份独立需求，符合当前自由拾取“一个号完成后切下一个号”的执行方式。
  - `shared / sequential_loot`：只计算一个掉落流。
  - `pending / special / 缺失`：保持Requirement，不猜倍率。
- 总需求量为`N_total = N × independent_streams`。
- 掉率`p = 1`时直接退化为确定性数量成本，不增加随机尾部。
- `0 < p < 1`时按负二项近似计算总成功需求对应的平均尝试数和方差，再叠加版本化尾部系数。
- 掉率只允许来自当前有效Questie/数据库可机械绑定的数据，或经证据审查后的task-id Timing Input；不得从备注、任务名或历史印象猜值。

## Questie输入链修正

现有Effective Quest Source已经读取Questie `wotlkItemDrops.lua`及掉率修正表。本轮补齐`itemDrops`物品来源链，使“任务目标物由另一个容器/物品开出”的关系不会丢失。

11999《寻找线索》现在可机械追踪为：

- 目标：眠月花园计划书（item 35783）
- 来源物：法师猎手的个人财产（item 35792）

Questie当前包没有提供“打开个人财产得到计划书”的容器产出概率，因此没有伪造插件掉率；该概率由当前服务器实测进入版本化Timing task参数。

## 《寻找线索》实测校准

用户2026-10-12实测描述：单号通常约15个法师猎手尸体左右基本能出，运气好约5个以内即可获得。

当前以`drop_rate = 0.10`作为**有效Timing校准值**，不声明其等于游戏底层真实概率。该值对应：

- 单号数学期望约10次尝试；
- 5次内至少成功一次约41%；
- 15次内至少成功一次约79%。

当前五开、不共享、每号需求1个，因此模型按总计5次成功需求计算；后续有更多clean实跑样本时可继续校准该task-id参数，不修改Questie源数据。

## 验证

- Timing / Questie Timing Source / Rule Routing相关契约：51 passed。
- 魔兽项目全量测试：311 passed。
- `dragonblight-fivebox` Timing重新构建成功；11999不再缺`drop_rate`输入。

本轮只收口个人随机掉落Timing规则、Questie物品来源链和11999任务级校准，不扩大到尚未明确选择Timing规则族的其它任务。后续其它随机掉落任务按自然实跑与已有fivebox事实逐步接入，不批量猜测分类。
