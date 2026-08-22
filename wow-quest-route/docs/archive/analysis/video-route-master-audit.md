# 视频路线参考索引 P1 审计

用途：只为本项目自己的路线顺序/邻接对照和遗漏审计提供可查询输入；不是联盟最终路线，也不是五开时间模型。

## 构建结果

- 单集输入：53/53。
- 标准化事件：1381。
- 不同任务键：891。
- 全系列视频画面时长：185084秒；只作累计定位，不当真实墙钟。
- 早期异构JSON兼容：3集（第1—3集采用synthetic-normalized查询层，不改原检查点）。
- Questie名称校准已加载：True；名称不一致候选：3。

## action类别

- `abandon`：9
- `accept`：376
- `complete`：796
- `discover`：25
- `level`：59
- `objective`：82
- `other`：23
- `state`：8
- `uncertain`：3

## 证据边界

- 原始`original_action`、raw事件和单集JSON路径全部保留，标准化只增加查询字段。
- `objective_complete_not_turnin`与奖励窗口未证明状态不会进入complete类别。
- 同名不同Quest ID以ID分开索引，不按中文名合并任务阶段。
- 视频累计秒数不能替代真实玩家墙钟，也不能进入五开估时。

输入哈希已保存在`data/video-route/master-events.json`，后续可复算。
