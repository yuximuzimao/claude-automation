# 2026-10-28 焕颜水乳3.0身份同步与文档收口

本目录保存阶段证据，不是当前操作入口。当前能力与权限见[CURRENT](../../CURRENT.md)，商品目录加载契约见[装箱辅助 owner](../../rules/packing-assistance.md#商品目录与身份来源)，未完成事项仍只见[待办](../../../tasks/todo.md)。

## 名称同步事实

用户于2026-10-27确认：ERP中焕颜乳、焕颜水的商品名称及简称均从2.0改为3.0，条码、商家编码和原有尺寸不变。名称同步及相关代码、数据和测试调整已在本次NEAT之前完成，见提交 `773b22a`；本次不再修改这些文件。

| 商品简称 | ERP标准全名 | 沿用商家编码 | 沿用尺寸mm |
|---|---|---|---|
| 焕颜乳3.0 | HEE悦希舒缓焕颜精华乳（3.0） 100g | `6940079096228-1` | 52×52×182 |
| 焕颜水3.0 | HEE悦希舒缓焕颜精萃水（3.0） 120ml | `6931583616811` | 52×52×200 |

此前同步覆盖 `product-mapping/data/products/hee/features.json`、`data/packing-product-dimensions.json` 和 `data/packing-dimensions.json` 中两条当前身份记录；完整名称、简称及当前商家编码相互对应。`packing_simulator_service.py` 同时阻止已有关联当前确认身份的尺寸编码从历史快照重复加入旧名，相关目录断言保存在 `tests/test_packing_simulator_service.py`。

## 历史字段与正式资料边界

- `product-mapping/data/products/erp-identities.json` 继续保留2026-09-11时间点快照中的2.0名称，不改写成当前档案。
- 正式案例、原订单快照、ERP日志、旧档案及活动原文保留当时事实；`data/packing-campaign-split-notes-09-22.md` 中的用户原话和真实ERP对照不替换名称。
- 两条尺寸记录的 `productSpecId` 仍为 `yuexi-rejuvenating-lotion-2-package`、`yuexi-rejuvenating-water-2-package`，它们是稳定内部标识，不因显示名称变化而重命名。
- 原始测量值、尺寸取整记录、条码、商家编码及箱型适用范围不随本次名称归档改变；也不因此扩大装箱白名单或ERP执行权限。

## 此前验证证据

- 名称同步阶段已完成332项非界面回归，全部通过；这是此前完成的验证，本次NEAT没有重跑。
- 此前未运行Tk交互测试，也未因名称同步启动ERP或长期服务；本次归档同样没有启动浏览器、ERP、浮窗或服务。
- 三相精华油5ml小样缺ERP主商家编码仍是上游资料缺口，按商品匹配待办处理；不能把旧测试失败流水账继续解释为本轮332项回归结果。
- 整理前CURRENT中的API目录数量等阶段统计没有在本次重新调用API验证，不作为新的验收结果。

## 本次NEAT处置

- 全文审查17份活跃Markdown；登记41份历史Markdown，全文读取档案索引及本轮直接相关的2026-09-13身份迁移、2026-10-16资料定稿；另识别1份pytest生成说明。
- `docs/rules/packing-assistance.md` 补充与现役代码一致的身份加载契约：候选来源、同全名快照优先、当前记录补缺、尺寸关联和历史旧名回流边界；未建立平行owner。
- `SKILL.md`、`docs/INDEX.md` 和阶段计划的来源说明改为owner指针，并登记本归档入口。
- `docs/CURRENT.md` 只保留当前能力、权限、资料来源及接手约束；阶段声明、旧回归数字和worktree收口经过移入[整理前CURRENT历史快照](previous-current.md)。该文件在整理前先逐字保存，正文原样保留，包括已经失真的“hee/features.json本轮未修改”旧表述，不再作为当前事实。
- CURRENT继续保留main作为现役来源、3466实验服务按用户要求停止、与正式浮窗隔离，以及多包拆分二次确认后立即停止等有效边界。

本次只做文档同步和本地静态读回检查，不修改应用代码、数据JSON、正式案例、活动原文或旧档案内容，不执行测试、服务或真实审单操作；库存计算属于SKU项目，本归档不新增审单业务任务。
