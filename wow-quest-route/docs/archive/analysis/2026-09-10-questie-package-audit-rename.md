# Questie package audit → inspector 迁移说明（2026-09-10）

## 结论

`scripts/audit_questie_package.py` 不执行项目正确性判定，也不生成正式路线输入。它接受任意 Questie ZIP，打印文件 SHA/大小、TOC 版本、correction 文件、地图模块，并按 `map` / `titan` 模式搜索坐标实现或 Titan/ChinaRegion 相关源码。

它的能力仍有长期用途：更换 Questie 数据包、核对 WotLK/Titan 接口版本、检查 correction 或地图实现时都可作为只读探索工具。但它不是 audit，因此不应继续占用审计命名空间。

## 迁移

- 现役工具改名为 `scripts/inspect_questie_package.py`。
- 旧 `scripts/audit_questie_package.py` 退役为 RETIRED guard，指向 inspector。
- 功能逻辑不变，仅把 CLI 描述从 Audit 改为 Inspect。

2026-09-10 用当前 `data/sources/questie/Questie.zip --mode map` 验证：

- Questie WOTLKC 版本 11.34.0；
- Interface 38002；
- correction 路径 64；
- map 模块 5；
- inspector 可正常读取并输出地图坐标实现。

这项处理不是删功能，而是把“只读探索工具”和“会决定项目 PASS/FAIL 的审计”明确分开。