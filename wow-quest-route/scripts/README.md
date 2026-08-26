# 现役脚本边界

`scripts/`只放仍属于当前实现链、能依据当前权威数据/规则重新计算结果的构建器、审计器和维护工具。

以下内容不得继续留在本目录：

- 只为某次阶段迁移服务的一次性脚本；
- 从固定Git提交、旧路线或旧P级方案恢复/覆盖当前路线的脚本；
- 已被现役规则替代的P0/P1/P2/P3/P4筛选、删除优先级或阶段性release脚本；
- 需要读取`docs/archive/`中的旧方案才能决定当前路线事实的脚本。

这些脚本如果仍有追溯价值，移到`docs/archive/scripts/`。历史脚本可以解释“当时为什么形成这个结果”，但不得被现役builder、默认audit、默认test或`cli.py`导入/执行。

现役脚本可以把一次性审计结果写入`docs/archive/analysis/`保存证据；“写历史输出”不等于“读取历史作为当前输入”。当前路线事实必须从CURRENT、现役rules、task foundation、observations、Journey和正式Route Atlas数据重新推导。
