# 冰冠 repeat-clone audit 职责迁移（2026-09-11）

`audit_icecrown_repeat_clones.py` 不是发布门禁：它只读取 `icecrown-task-foundation.json`，对11组已知首轮/后续重复任务打印名称、目标、前置和80级收益差异；没有输出审计状态、没有失败条件，也没有现役消费者。

逐项核对后，这11组的正式路线决策都已经由 foundation 自身持有：13093、13261、13276、13281、13331、13353、13357、13365、13368、13406均有明确的“后续重复/日常版，不作为第二个首跑任务”排除原因；13376则因长途轰炸没有一次性解锁价值而走 `exclude_route_economics`。因此正确路线不依赖这个脚本的运行结果。

该工具仍有诊断价值，例如能看到13092→13093虽然同名但Questie结构数量不同，13279→13281与13313→13331虽然任务名不同但结构目标相同，以及13373→13406/13376的目标数量和目标集确实不同。这些信息适合人工检查，不应伪装成 audit gate。

处理：原实现原样迁到 `scripts/inspect_icecrown_repeat_clones.py`；旧 `scripts/audit_icecrown_repeat_clones.py` 仅保留 RETIRED guard。迁移不改变 foundation、路线任务池或任何首跑/日常选择规则。
