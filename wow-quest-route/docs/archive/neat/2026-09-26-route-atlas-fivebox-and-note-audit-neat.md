# 2026-09-26 Route Atlas备注 / Fivebox待实测专项 NEAT

## 本阶段状态

本轮完成了正式 Route Atlas 的任务备注与 fivebox 待实测专项审计。目标不是把所有 `pending` 强行清零，而是把“可以由已确认规则或既有实跑事实直接确定”的任务全部归类，只留下当前服务器机制确实未知的任务。

正式执行页仍为：

`data/routes/route-atlas-workbench.html`

本文件只保存阶段结论，不作为下一次执行入口；当前工作看 `tasks/todo.md`，当前实跑恢复点看 `docs/verified-routes/CURRENT.md`。

## 已完成：旧页面与入口清理

- 正式页面增加标题“魔兽世界五开打金任务路线”。
- 旧 `simple-leveling-route.html`、`dk-55-80-world-tasks.html` 与对应旧攻略文档退出正式入口，归入 `docs/archive/routes/2026-09-26-retired-legacy-route-pages/`。
- 旧 CLI 构建入口与相关现役测试说明同步退役。
- `data/routes/` 顶层只保留当前正式 Route Atlas HTML。

## 已完成：Fivebox基础分类规则补齐

`fivebox.status`继续只使用：

- `shared`
- `not_shared`
- `sequential_loot`
- `special`
- `pending`
- `not_applicable`

本轮新增/明确的可直接分类基础规则：

1. 纯普通击杀，没有任务物、使用动作、事件、载具、召唤、对话触发等个人阶段时，直接归 `shared`。
2. 纯接取→移动/报到→交付，没有独立完成机制时，归 `not_applicable`。
3. **护送任务已由用户确认属于稳定共享机制，统一归 `shared`，不再进入待实测。**
4. “依次交互”仍不建立新标签：总体个人完成用 `not_shared`，连续切号/刷新等操作细节写 guide；`sequential_loot`只用于同尸体/同掉落来源多人依次取得任务物。

本轮将7个仍为pending的护送任务统一改为shared：

- 9868《卡达什图腾》
- 11241《烈火冲天》
- 11664《逃离迷雾》
- 12082《喔——哒！！》
- 12512《一个也不能少》
- 12570《幸福的误会》
- 13229《我还没死！》

## 已完成：备注专项审计

正式任务备注逐项检查了“任务A备注中出现任务B”的情况，没有机械删除引用。

最终只保留确实属于当前任务执行依赖的少量跨任务引用，例如前置效果、事件共享计数或任务物来源关系；错误归属的内容迁回正确Task Card。

旧标记 `【需要单独修正优化】` 已从当前全部 Task Card 清零。

备注层继续保持：

- guide允许保存完整任务攻略事实；
- Presentation只保存现场执行真正需要的最短提醒；
- 共享/不共享标签已经表达的信息，不再用长备注重复；
- 路线编排信息不得泄漏回Task Card。

## 已完成：Pending全面审计

本阶段开始时正式 Route Atlas 有约710个唯一 `pending` 任务。

经过以下层级逐批审查：

- 纯普通击杀；
- 纯传话/转场；
- 已有Task Card实跑事实；
- 历史Observation与此前玩家实跑记录；
- Boss共同击杀；
- 任务备注中已经写明的fivebox行为；
- 旧聊天中明确给出的共享/不共享结论；
- 护送稳定共享规则；

当前正式路线剩余 **321个唯一pending任务**。

这些任务不再是“尚未看过”，而是已经审过后仍缺真实fivebox证据的任务，主要包括：

- 任务物/掉落；
- 固定物或任务物使用；
- 任务起始物/场景触发；
- event/脚本事件；
- 载具/个人脚本；
- 非标准击杀/混合机制；
- 少量任务事实本身仍需补完整的任务。

禁止为了继续降低数量而按相似任务猜共享性。

## Fivebox验证清单治理

新增：

`tasks/fivebox-pending.md`

它是当前正式 Route Atlas 全部 `fivebox.status=pending` 的唯一完整实跑验证清单。

`tasks/todo.md`不再复制一份不完整的手工任务列表，只保留到该清单的工作入口。

新增契约测试保证：

- 正式 Route Profile 中所有pending Task Card集合；
- `tasks/fivebox-pending.md`中的任务集合；

必须完全一致。以后任何一边漏同步，测试直接失败。

## 下一阶段

用户指定下一次优先处理：

**丰富正式路线已有任务的备注内容。**

方向已经写入 `tasks/todo.md`：

- 按地图逐图检查现役Task Card / 玩家页；
- 补真正影响现场执行的入口、楼层、任务物使用、失败条件、刷新、Boss/事件机制与五开操作提示；
- 优先复用现有实跑与可靠证据；
- 不为了“详细”堆背景文字；
- 不借备注专项重做路线结构。

剩余fivebox pending仍只在自然实跑做到时验证，不为清单专门补跑。

## 最终机械验收

- 正式 Route Profile：15个。
- 正式页面：`data/routes/route-atlas-workbench.html`。
- Publisher：15个Profile均可发布，本轮渲染 `publishable=true`。
- 当前唯一fivebox pending：321个。
- `tasks/fivebox-pending.md`与正式pending集合必须由契约测试保持一致。
- 当前Task Card旧备注标记 `【需要单独修正优化】`：0。
- 相关Task Card / Presentation / Display / Publisher / Player Assets / Rule Routing测试：68 passed。
- 当前没有必要重新引入旧Route页面、旧builder或旧fivebox迁移账本。

## 恢复纪律

下一次项目维护先读 `tasks/todo.md`。备注丰富专项属于Task Fact / Task Presentation组合工作：先确认事实属于Task Card guide还是玩家Presentation，再按SOP进入唯一owner。

继续游戏时仍从 `docs/verified-routes/CURRENT.md` 的第二组DK北风恢复点继续；不要因为本轮文档专项重新整理已经处理完的历史实跑原文。
