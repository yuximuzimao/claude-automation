# 冰冠第二组DK续跑与《夺取钥匙》机制纠正 NEAT

日期：2026-11-04—2026-11-05

## 本轮实跑事实

- 执行组：第二组兽人双手鲜血DK×5。
- 开始：2026-11-04 23:06。
- 00:01：完成飞艇上的任务，随后接上此前提前接取的暗影拱顶任务链。
- 结束：2026-11-05 00:20。
- 本轮有效墙钟：74分钟。用户评价本轮较简单，未报告额外等待或路线错误。
- 本轮覆盖的是冰冠续跑中的飞艇任务与此前已接取的暗影拱顶任务衔接段；不将其冒充为完整冰冠步骤或整图实测。

## 已确认的任务事实

### 12949《夺取钥匙》

**当前结论：依次拾取（fivebox.status = sequential_loot）。**

- 同一来源可由五个角色依次拾取任务物。
- 不应按共享任务处理。
- 本次第二组DK实测覆盖此前首组实跑的“共享”判断。
- Task Card guide补充五开执行方式；旧判断保留为已被新实测覆盖的历史证据，不再参与当前分类。

## 已写回的现役真源

1. data/task-cards/12949.json
   - fivebox状态改为sequential_loot。
   - guide明确同一来源由五个角色依次拾取。
   - 旧共享证据标记为历史并记录被新实测覆盖；新增2026-11-05用户实测证据。
2. data/observations/fivebox-task-types.json
   - task 12949类型更新为same_source_sequential_loot_confirmed。
   - 记录第二组DK实测并明确覆盖首组旧判断。
3. data/observations/route-timing-runs.json
   - 新增run 2026-11-04-05-icecrown-second-dk-2306-0020。
   - 保留23:06至00:20的74分钟真实墙钟、飞艇任务与暗影拱顶衔接信息。
   - 不用于单一步骤Timing校准：本轮是跨任务块续跑，尚无可比的单一正式步骤同终点范围。

## 对路线与模型的影响

- 本轮只纠正12949任务自身的五开机制事实。
- 不据此调整冰冠正式Profile的任务顺序，也不把本轮现场衔接顺序复制为从零路线。
- sequential_loot会让引用该Task Card的当前消费者读取到正确执行分类；Timing仍以Task Card显式timing_rule_ref和Timing owner规则为准，不因标签变化擅自重算或更改规则。
- 00:20停止时的精确任务栏与下一动作没有从本轮文字反馈中推断；后续恢复时以用户已更新的游戏历程/当前客户端任务栏为准。

## 分析与边界

用户原始反馈确认了三个事实：飞艇任务于00:01完成、随后衔接此前提前接取的暗影拱顶任务、本轮于00:20结束；并明确要求《夺取钥匙》改为依次拾取。

本次分类判断是：12949属于TASK_FACT，74分钟记录属于OBSERVATION。没有证据表明正式路线动作顺序需要改写，因此不改Route Profile。由于没有报告异常，实跑记录标记为未发现路线错误；这不等于证明本轮每一步都已与正式Profile完全同序。

## 验证与提交边界

- Task Card / Route Profile schema契约：13项通过。
- Task Presentation契约：7项通过。
- Task Presentation输出已确认badge=sequential_loot、note为空。
- Icecrown Route Display增量更新通过；Publisher payload重建通过，status=pass、publishable=true。
- Task Card、fivebox观察、Timing runs、Display、Publisher与manifest共6份JSON全部解析通过。
- 仅提交本次魔兽项目相关文件；工作区其它项目已有未提交修改，不纳入本次提交。
