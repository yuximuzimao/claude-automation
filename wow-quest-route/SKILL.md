# 魔兽世界任务路线 SKILL.md

用途：把用户请求路由到**最小必要真源、规则owner和固定流程**。本文件不是规则目录，也不复制业务算法。

## DO FIRST

1. 先读`tasks/todo.md`，确认当前工作流/未完成迁移；不要默认加载历史。
2. 需要找文件/数据位置时读`docs/INDEX.md`；INDEX只负责导航。
3. 涉及长期规则/模型时从`docs/rules/README.md`选择唯一owner，不在SKILL里维护子规则清单。
4. 涉及新建、修订、实跑写回、发布或架构迁移时，按`docs/verified-routes/ROUTE-DESIGN-PROCESS.md`对应分支执行。
5. ERROR-BOOK和archive都只按当前风险定向检索，不全文加载。

## 请求路由

### 继续当前实跑 / “下一步去哪”

读`docs/verified-routes/CURRENT.md`。

- CURRENT是当前角色runtime overlay/恢复点；
- 只在CURRENT明确需要背景时读取对应最近NEAT或执行数据；
- 当前现场反馈如果证明长期任务事实/正式路线错误，再按SOP转入对应分支。

### 查或纠正单任务机制

读：

1. Task Card规范与对应Task Card；
2. `docs/rules/README.md`路由到Task Mechanics owner；
3. 必要时Questie/observations/公开资料；
4. 按SOP的`TASK_FACT`写回与传播。

不要先在HTML、semantic脚本或Route Profile备注里保存任务事实。

### 只改人工推荐备注

从`docs/rules/README.md`进入Task Presentation owner，并按SOP的`TASK_PRESENTATION`执行。人工备注允许明确为空；不要从共享标签自动生成备注。

### 改共享 / 不共享 / 依次拾取 / 待实测状态

这是Task Card的fivebox机器事实，按SOP的`TASK_FACT`执行；前端标签只是读取该变量。只有需要改变人工推荐备注时才另外进入`TASK_PRESENTATION`。

### 改路线任务集合 / 顺序 / 步骤 / 交通

1. 从`docs/rules/README.md`选择Task Selection / Route Optimization / Route Profile等真正命中的owner；
2. 按SOP的`PROFILE_TASK_SET`或`PROFILE_STEPS`执行；
3. 只重放真实受影响窗口；
4. 玩家可见内容变化时再进入前端owner和最小测试。

### 新建正式路线

按SOP的`NEW_PROFILE`完整流程；规则仍按`docs/rules/README.md`渐进加载。

### Route Atlas页面 / 地图 / 控件 / CSS

从`docs/rules/README.md`进入UI & Assets owner。

如果同时改变路线动作或任务备注，再组合对应Route Display / Task Presentation流程；纯UI工程不加载Selection/XP/路线算法。

### DK职业/战斗配置

读`docs/verified-routes/DK-COMBAT-NOTES.md`。只有处理55—80全世界候选母版时再读`docs/DK_55_80_WORLD_TASKS.md`和对应生成数据。

### 视频拆解

读`docs/video-extraction/README.md`与`docs/video-extraction/CURRENT.md`；视频事实和当前角色路线保持分离。

### 测试 / 脚本治理

- 测试选择：`tests/README.md`；
- 顶层脚本现役性/退役：`scripts/README.md`；
- 不用旧快照测试反向恢复旧业务结果；
- 不让archive脚本回到现役实现链。

## 架构契约入口

冻结后的架构契约只读：

- `docs/analysis/2026-09-15-architecture-governance-acceptance.md`：第一目标、验收清单与最终双模型复审结论；
- `docs/analysis/2026-09-15-architecture-governance-migration-matrix.md`：17份核心文档及新增owner的最终职责。

当前数据迁移、Publisher切换和旧消费者退役进度只看`tasks/todo.md`，不在SKILL复制。普通迁移遗漏或中文转换bug不得重开架构；只有可复现的真实业务表达缺口才允许重新评估架构。

## 根本纪律

- 用户当前服务器实测优先于旧路线/历史推论；但只修改实测真正证明的字段。
- 已验证/可复用路线的未受影响部分默认冻结；额外发现先报告或记todo，不自行扩大业务修改。
- 任务事实、规则、Route Profile、CURRENT、Generated Product各有单一职责；禁止双写成两份可独立演化真源。
- 渐进式读取：只加载当前任务真正需要的owner/Task Card/Profile/历史案例。
- 原始Questie/WTF/账号登录数据不提交；只保存必要的脱敏结构化结果。

## 导航与实现入口

具体路径只读`docs/INDEX.md`。代码/生成入口先查`cli.py`与`scripts/README.md`；不要因为脚本存在就默认它仍是现役权威入口。
