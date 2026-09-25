# 当前恢复点

## 当前角色 / 实跑状态

- **当前执行组是第二组五开：兽人双手鲜血DK×5。** 第一组是2026年8月的圣骑士五开；两组时间对比、路线结论和历史描述不得再混称。
- **2026-09-20→09-21北风苔原第二次实跑已全部处理。** 本轮22:46开始，23:50—00:02暂停，用户约01:56在战歌要塞附近暂停；有效活动时间约2小时58分。
- 当前已知任务状态：69级；《使者》《纳萨姆平原》已完成；已接《立即前往博古洛克前哨站！》《危在旦夕》。Questie最后任务事件为01:53:59完成《使者》；“战歌要塞附近”来自用户现场描述，不伪造Questie坐标。
- 从第二组DK出生区、地狱火、赞加、纳格兰、68级泰罗卡兜底到本次北风暂停点的已提供实跑反馈，都已经按SOP分类进Task Card / Route Profile / Observation / Selection；下次不要重新从原文整理。

## 当前正式路线状态

- Route Lifecycle / Publisher已经正式cutover；当前共有**15个Route Profile**。Stage 14项目级审计为`cutover_status=pass + cutover_ready=true`，15个Profile均`cutover_publishable=true`；正式页面仍由当前Publisher链生成。旧candidate/compare/旧builder只作历史考古。
- 60→68路线已经闭合：地狱火DK速度版 → 赞加DK速度版 → 纳格兰v2；不恢复9/18慢赞加补经验组。仍不足68时，可单独执行`terokkar-dk-68-fallback`三任务小路线，交完后经沙塔斯奥格瑞玛传送门到奥格瑞玛。
- “依次交互”不新增fivebox标签：任务目标不共享、需要五号分别完成时统一归`not_shared`；连续切号、等待刷新等真正有执行价值的细节留在备注；混合机制继续用`special`。
- 固定10任务日常采样已经关闭，默认按33分钟/轮；除非任务集合或路线改变，不再重复采样。
- 真实经济数据 / G小时体系目前降为长期可选项，不要求后续每次实跑主动记录金币、泰坦碎片等数据。

## 当前工作入口

- 当前未完成事项：`../../tasks/todo.md`
- 实跑反馈 / Route Lifecycle分类：`ROUTE-DESIGN-PROCESS.md`
- 文件与规则导航：`../INDEX.md`
- DK职业配置：`DK-COMBAT-NOTES.md`
- 本轮阶段归档：`../archive/neat/2026-09-25-dk-live-run-closure-and-group-comparison-neat.md`
- 架构迁移考古：`../archive/analysis/2026-09-21-route-lifecycle-migration-history.md`

## 下一次继续时

1. 若继续游戏，从上述69级北风状态接新的实跑原文 / Journey；只处理01:56之后的新内容。
2. 做到仍为`pending`的fivebox任务时自然验证并回写Task Card，不为清清单专门补跑。
3. 若做项目维护，当前最高优先仍是Todo中的Route Atlas正式页逐图前端审计。
4. DK出生区独立HTML、路线前置准备提示、Leatrix接入和经济/G小时体系都是独立后置事项，不阻塞继续实跑。
