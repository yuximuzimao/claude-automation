# Questie 原始数据源

`Questie.zip` 是本项目长期使用的 Questie 原始插件包，属于人工提供的源文件，不是脚本生成产物。

- 规范本地路径：`data/sources/questie/Questie.zip`
- 用途：任务数据库、中文名称、掉落/目标、任务链与 XP 等基础数据解析。
- 更新原则：只有明确更换 Questie 原始版本时才替换该 ZIP；派生 JSON/审计结果仍写入 `data/route-atlas/` 等对应目录。
- Git：ZIP 体积较大，保留在本地工作区但不提交；README 用于记录其长期位置和用途。

`.ai-bridge/Questie.lua` 是当前角色 Journey 原始数据，继续原位保留，和本 ZIP 不是同一种数据源。
