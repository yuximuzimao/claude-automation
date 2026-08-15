# 全部视频拆解完成后的第二阶段

## 1. 触发条件

只有在以下条件全部满足后才进入本阶段：

- 第13—53集均有独立`episode-N-extraction.md`；
- 第13—53集均有可解析的`episode-N-events.json`；
- `docs/video-extraction/CURRENT.md`明确写为“第一阶段完成”；
- 每集剪辑缺口、不确定等级和未确认任务均已保留，而不是被静默补齐。

在此之前，不把零散视频结论直接写成最终35—55路线。

## 2. 第二阶段目标

把联盟圣骑士视频从“逐集观察记录”转换为可审计的路线参考证据，并与当前血精灵五开35—55数据体系合并，最终生成玩家可执行路线。

视频不是最终答案。它提供：

- 实际任务顺序；
- 任务中心往返和交通节点；
- 同区任务的组合方式；
- 视频作者实际跳过、放弃和延后的任务；
- 某些任务在真实升级过程中的阶段位置。

视频不能直接证明：

- 联盟任务适用于部落；
- 单人打法适用于五开；
- 视频路线是经验/分钟最优；
- 剪辑省略的时间和任务可以忽略；
- 旧版本/当前时光服机制完全一致。

## 3. P1：合并为标准化视频事件库

新增计划产物：

```text
data/video-route/master-events.json
data/video-route/episode-boundaries.json
docs/archive/analysis/video-route-master-audit.md
```

处理：

1. 合并全部`episode-N-events.json`；
2. 统一`action`、置信度、时间格式和任务字段；
3. 保存`episode`、集内秒数、全系列累计时间；
4. 区分接取、目标完成、交付、放弃、剪辑外变化；
5. 保存原检查点路径和证据帧目录；
6. 生成输入文件哈希，保证可复算。

验收：

- 每个事件能追溯到单集检查点；
- 同一任务链阶段不会因为同名而合并；
- `objective_complete_not_turnin`不会误算成`complete`；
- 推定等级与明确等级分开统计。

## 4. P2：跨集一致性与缺口审计

新增计划产物：

```text
data/video-route/cross-episode-gaps.json
docs/archive/analysis/video-route-cross-episode-audit.md
```

检查：

- 上一集结束任务与下一集开场任务是否连续；
- 剪辑外接取、交付、击杀和移动；
- 同一任务重复接取/完成；
- 任务日志存在但缺少接取事件；
- 视频标题等级与明确/推定等级冲突；
- 任务ID、中文名和前后续关系是否符合Questie。

缺口只分为：

- 可由明确前后状态唯一确定；
- 可确定动作存在但顺序/时间未知；
- 无法确定。

不得为了得到完整路线而把第三类强行补齐。

## 5. P3：构建联盟视频路线骨架

新增计划产物：

```text
data/video-route/alliance-route-blocks.json
docs/archive/analysis/video-route-block-audit.md
```

按实际地理和交通切成任务块：

- 任务中心接取/交付块；
- 同怪、同物品来源、同小区域目标块；
- 飞行、船、炉石、传送和长途移动块；
- 副本、精英、组队和作者借助大号的特殊块；
- 剪辑时间未知块。

每块保存实际视频耗时区间，但把“画面时长”“明确战斗时长”“剪辑缺失”分开。不能把剪辑后视频长度当真实总耗时。

## 6. P4：映射到部落/血精灵候选

读取现有基础：

```text
docs/archive/analysis/2026-08-04-35-55-data-contract-and-requirements.md
data/routes/horde/blood-elf/35-55-candidates.json
data/routes/horde/blood-elf/35-55-overlap-blocks.json
data/routes/horde/blood-elf/35-55-priority-task-audit.json
data/route-specs/35-55-speedrun-constraints.json
```

映射分四类：

1. 同一中立任务：任务ID相同，可直接比对；
2. 同地图同目标的阵营变体：任务ID不同，目标实体/物品/区域高度对应；
3. 只能复用交通或任务块结构，任务本身不可用；
4. 联盟专属且无合理部落替代。

输出计划：

```text
data/video-route/horde-mapping.json
docs/archive/analysis/video-route-horde-mapping-audit.md
```

每条映射必须保存任务ID、共同实体、地图、前置差异、阵营限制和置信度。名称相似不能作为唯一映射依据。

## 7. P5：接入现有35—55优化工作

现有状态：

- D0—D3基础数据已经完成；
- Codex C1任务重叠图/候选块已经完成；
- Codex C2高优先任务覆盖层已经完成；
- ChatGPT G1动态等级模拟器、G2边际成本合并、G3交通边、G4最终路线仍需完成或复核。

视频数据进入优化器时只增加以下证据：

- 实际任务组合候选；
- 实际交通顺序；
- 真实路线中出现的等待、困难、借助大号和放弃信号；
- 某任务块在具体等级附近被执行的实例。

视频不能覆盖：

- 当前最低角色等级/经验；
- 部落任务可接性；
- Questie前置闭包；
- 五开共享/个人拾取实测；
- C2覆盖层中的`needs_live_test`；
- 交通边的当前实测值。

## 8. P6：动态路线求解与人工复算

沿用当前`docs/verified-routes/ROUTE-DESIGN-PROCESS.md`的人工核验顺序；历史35—55优化器结果仅作为候选与差集证据：

1. 读取C1任务块，不修改其原始输出；
2. 应用C2覆盖层；
3. 读取视频任务块和部落映射；
4. G1按实际交付等级计算逐任务经验；
5. G2合并同怪、同路、同NPC和个人掉落增量；
6. G3显式加入飞行、船、飞艇、炉石和骑行；
7. 输出多套Pareto候选；
8. 对最优候选逐任务人工复算前置、经验和时间；
9. 加入真正顺路的边际任务；
10. 才能进入G4最终玩家路线。

不允许仅因为视频作者做了某任务，就强制把它加入最终路线。

## 9. P7：最终交付

最终35—55玩家路线必须按分区任务块输出，每段包含：

- 起点与最低角色等级/经验；
- 交通方式和飞行点；
- 出发前必须接的任务；
- 同一区域目标顺序；
- 五号共享击杀、逐号拾取/点击和跟随操作；
- 逐任务经验与本块预计分钟；
- 难点、等待上限、止损和替代任务；
- 离开等级/经验；
- 下一地区第一批任务。

同时更新：

```text
docs/verified-routes/CURRENT.md
docs/rules/README.md（仅将稳定规则路由到对应子文档）
docs/verified-routes/ERROR-BOOK.md（视频审计发现的新增错误类型）
docs/verified-routes/segments/*.md
```

## 10. 后续实跑闭环

视频整合与优化完成仍不是终点。玩家实跑时继续记录：

- 最低/最高角色经验；
- 实际分钟；
- 五号同步情况；
- 个人掉落额外击杀；
- 死亡、跑尸、跟随卡点；
- 接不到、交不了、位面异常；
- 与视频路线和优化器预测的偏差。

实跑事实优先于视频和静态数据库。稳定后再冻结路线段。
