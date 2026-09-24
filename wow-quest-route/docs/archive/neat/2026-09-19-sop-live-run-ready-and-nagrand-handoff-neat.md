# 2026-09-19 SOP可接实跑 / 未完结总账 / 纳格兰实跑交接 NEAT

## 本轮结论

本轮不再把“所有旧路线、所有artifact、所有特殊机制都迁完”作为判断SOP是否完成的标准。用户明确当前更关心的是：**新的实跑反馈进来以后，SOP是否知道应该去哪个owner、什么时候保持UNKNOWN、什么时候必须问用户、什么时候说明SOP/schema本身有缺口，而不是模型临时拍脑袋。**

按这个标准，当前Route Lifecycle SOP已经达到**可以重新接入正式实跑**的状态：

- Stage 1–14 implementation已经闭环；
- §1.5已有统一异常/诊断路由；
- §17.5已明确“未知本身也必须有处理路径”；
- 新型问题若现有SOP/owner/schema无法容纳，必须标记为“流程表达缺口”，进入`ARCHITECTURE_MIGRATION`补SOP/owner/schema/测试，再回来处理业务；
- 证据不足保持UNKNOWN或询问用户，禁止找一个最像的字段硬塞；
- 用户要求“先存着”的实跑反馈继续进入未裁决现场输入，不自动修改正式Task Card/Profile/Timing。

本轮Rule Routing针对性回归：**17/17 passed**。

因此，后续全Profile artifact清债、Publisher切换、特殊机制建模等仍未完成，但**不再阻止继续实跑**。

## 当前尚未彻底完结的11类事项

完整总账已写入`tasks/todo.md`，概括如下：

1. 特殊机制的结构化表达：护送位移、任务载具、任务位面/镜像等；
2. Stage 5少量movement事实UNKNOWN；
3. HD-001 / HD-002两个人工决策；
4. Stage 3诊断期候选业务修改的正式验收；
5. 14张正式Route Profile最终业务验收；
6. 新Publisher正式接管、旧写入口退休、Generated Product可重建、worktree最终合并；
7. Publisher切换后的前端冷读与约240段延期备注清理；
8. DK首轮盈利路线继续实跑与G/小时删留；
9. fivebox长期验证账与冰冠第二轮自然复测；
10. DK兽人身份迁移、出生区HTML、60→68删留/经验缓冲等独立业务；
11. Leatrix/Timing/Economy成熟版。

这些事项不等价于“SOP还不能用”。其中大量内容是业务数据、实跑样本、后置验收或专项模型能力。

## Stage 5当前状态

机械迁移债已基本清完。当前：

- Profile内部：`7 movement_edge_unresolved + 5 move_action_mode_required`；
- Program边界：9/11 pass；
- 剩余两条Program requirement：
  - `nagrand → borean`：HD-002/死亡灵魂跨大陆转场；
  - `dragonblight → dalaran`：去艾萨斯影像的第一段movement mode仍UNKNOWN。

护送导致位移、玩家操纵任务载具、进入任务位面/剧情事件位移等特殊机制，用户决定后续单独讨论，不在当前阶段为了全绿强套`ride/fly/swim`。

Icecrown本轮前已完成的Stage 5结构修复继续成立：恢复晶歌系统鸟落点、两次救治链真实交通节点，并用Questie 11.34.0纠正晶歌/月光/龙眠旧占位坐标。基础合同此前保持57/57。

## 2026-09-19最新实跑封存

用户要求：**先原文保存到Todo，下个会话再依次处理。**

完整原文已写入`tasks/todo.md`，当前不拆Task Fact/Profile/Selection/Observation/Timing。

恢复锚点：

- 1:48开始一轮10个日常，本轮改试《爆炸油》；
- DK补经验段2:29开始；
- 3:40暂停；
- 4:05继续；
- 赞加补经验后转纳格兰；
- 纳格兰本轮补经验结束；
- 最终直接沙塔斯回奥格；
- 当前准备进入诺森德。

本段存在大量明确时间污染：死亡、跑尸、误操作、接早/接晚、掉下地形、未及时发现角色死亡等。下个会话处理时必须保留这些污染事实，不能直接把整段墙钟当clean baseline。

用户本轮还提供了大量待分类事实/建议，包括但不限于：

- 两个通缉任务共享；
- 多个杀怪任务共享；
- 《呼嚎之风》掉落依次拾取；
- 《证明你的力量》不共享；
- 《侦查大地》接任务后自动飞；
- 《争取时间》需要单拉怪；
- 沃舒古水晶碎片可交易；
- 《象牙生意》接取时机；
- 嘲颅废墟更适合把《证明你的力量》一次刷完；
- 主规划师实测可打；
- 需要比较“第二组少做赞加、多做纳格兰”与“第一组多做赞加、少做纳格兰”的真实效率。

以上目前都只是**Todo中的未裁决现场输入**。下个会话按SOP逐项分类后，才决定哪些可以写回正式真源。

## 下一会话恢复顺序

1. 先读`CURRENT.md`、`tasks/todo.md`、本NEAT和`ROUTE-DESIGN-PROCESS.md`；
2. 优先处理2026-09-19最新实跑原文；
3. 按§1.5逐项分类为：
   - TASK_FACT；
   - PROFILE_STEPS / PROFILE_TASK_SET / Selection；
   - OBSERVATION及污染；
   - CURRENT_RUNTIME；
   - 特殊机制/流程表达缺口；
   - 需用户裁决；
4. 对能安全落地的普通事实直接按owner处理并rebuild；
5. 遇到特殊机制不临时设计，单独提出问题与用户讨论；
6. 处理完后，游戏当前恢复点为“沙塔斯回奥格，准备诺森德”。

## 版本控制状态

本轮按用户要求做NEAT归档与恢复点更新：

- 不提交；
- 不推送；
- 不合并主干；
- 不覆盖正式Route Atlas页面；
- worktree继续保持`feat/wow-architecture-migration`隔离状态。
