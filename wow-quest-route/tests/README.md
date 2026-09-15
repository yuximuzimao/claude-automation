# 测试分层与选择

用途：本目录只负责**验证现役规则和机器契约**。测试不是业务真值，也不是第二份架构文档；不能因为旧测试失败就反向修改Task Card、Route Profile、CURRENT或用户实测。

## 1. 三类测试

### A. 永久契约测试

只保护跨地图、跨Profile长期稳定的业务/数据契约。

例如：

- Task Card的机器schema与禁止字段；
- Route Profile必须使用稳定task_id、不得复制Task Card事实；
- stepGroups必须完整覆盖动作且保持顺序；
- `presentation.note_override`只控制人工推荐备注、不能改机器事实或fivebox状态；
- Timing/XP等模型的公式与输入输出契约；
- Publisher只能从现役真源生成正式产物；
- archive/旧脚本不能重新成为现役写入口。

**只有对应的总规则/机器契约真的变化时，才修改这类测试。**

普通数据变化、单任务纠正、单Profile重排不应为了“让测试通过”去改永久测试脚本；它们只需要用现有永久契约验证新数据是否合法。

### B. 当前功能 / 当前迁移验证

只保护当前明确进行中的开发、迁移或兼容切换。

例如：

- 当前`hellfire-dk-speed`从旧Builder迁到Task Card + Route Profile；
- 一次性规范化脚本是否幂等；
- 迁移后10208不再从旧Builder硬编码长备注；
- 新旧路线逐action语义对账。

这类测试可以包含具体task_id、具体Profile和具体迁移脚本。对应迁移/兼容层退役后，测试应一并删除或归档，**不得因为曾经发生过一次bug就升级为永久业务契约。**

当前：

- `test_dk_task_card_presentation_migration.py`属于B类，随旧DK Builder / migration脚本退役。

### C. 快照 / 历史参考

固定点数、步骤数、某任务位于某一步、整段精确中文、某版本总分钟数等，默认属于快照。

快照用于说明“这次改了什么”，不是永久真值。用户批准的新事实/规则/路线使快照失效时，更新或退役快照，禁止为了跑绿恢复旧业务结果。

## 2. 永久测试按稳定契约边界组织

不按每个视觉元素或每个task_id建永久测试。稳定边界当前分为：

- **Task Card Contract**：schema、字段语义、unknown/partial/verified、禁止route决策、机器事实与guide/presentation的边界。
- **Route Profile Contract**：稳定task_id、动作结构、条件、entry/exit、step覆盖、禁止任务事实副本。
- **Task Presentation Contract**：显式`fivebox.status`→标签、`presentation.note_override`→备注、override scope；不测试具体任务文案。
- **Route Display Contract**：Route Profile→地点/NPC/接做交/步骤结构；不测试Task Card机制。
- **Model Contracts**：Timing、XP、Selection各自的公式/输入输出，不混成万能测试。
- **Publisher / Generated Product Contract**：真源可重建workbench/HTML，生成物不能成为反向写入口。
- **Registry / Archive Contract**：规则owner、现役脚本和archive边界。

这些边界与`docs/rules/`的现役owner一致。若owner规则没有改变，不应因为一次具体数据修改去改永久测试定义。

## 3. 修改后跑什么

先看本轮真正改了哪个owner/数据，再组合最小测试。

- 改一张Task Card事实：Task Card Contract；重新生成引用它的Profile下游；如果玩家展示变化，再跑Task Presentation + Publisher smoke。
- 改presentation override：Task Card Contract + Task Presentation + Publisher smoke；不跑XP/路线优化。
- 改Route Profile动作/步骤：Route Profile + Route Display；若顺序影响时间，再跑Timing；最后Publisher smoke。
- 改Timing规则/公式：Timing永久契约 + 实际消费者；这是修改永久测试的合法场景。
- 改UI工程：UI/Publisher相关测试；没有业务变化时不跑Task Mechanics/Selection。
- 改迁移脚本：只跑对应B类迁移测试 + 被迁数据的永久契约；不新增任务专用永久测试。

默认不使用`pytest tests`作为日常门禁。只有最终架构收尾或公共规则大改时，才按SOP扩大到完整相关契约组。

## 4. 人工冷读

以下不能由自动测试代替：

- 备注是否真的有执行价值；
- Questie已经显示的信息是否重复；
- step是否过长；
- 页面是否能一眼看到下一动作；
- UI遮挡/滚动是否影响实跑。

局部改动只冷读受影响窗口；新Profile或整图重构才完整复走。

## 5. 当前文件治理

- `test_task_card_route_profile_schema.py`：A类，必须只使用合成/通用样本验证Task Card和Route Profile稳定机器契约，不绑定10208业务内容。
- `test_task_presentation_contract.py`：A类，验证通用Task Presentation规则，不绑定具体地图/任务。
- `test_dk_task_card_presentation_migration.py`：B类，当前地狱火兼容迁移专用，切换完成后退役。
- `test_rule_routing.py`：A类，验证入口只能路由到现役owner；不得要求SKILL复制全部子规则正文。
- `test_route_atlas_workbench.py`：当前仍为混合旧测试；后续按Route Display / UI / Publisher / snapshot职责拆，不继续向里面追加新的永久规则。

其它地图测试默认属于对应Profile开发验证或快照，除非逐条确认它保护的是公共永久契约。

## 6. 测试环境

项目依赖声明在`pyproject.toml`。使用项目虚拟环境：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest <本轮最小相关测试>
```

不要修改系统Python，也不要依赖全局环境。

## 7. 失败处理

失败先分类：

1. 现役规则/数据真的错 → 修权威源；
2. 公共实现错 → 修实现；
3. 当前迁移兼容错 → 修B类迁移层；
4. 旧快照过期 → 更新/退役快照；
5. 与本轮无关 → 记录，不扩大当前修改。

一句话：**永久测试保护稳定契约；迁移测试保护当前切换；快照只记录历史形态。三者不能混。**
