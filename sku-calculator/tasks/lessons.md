# 教训记录

## L1 产品目录不能静态维护（2026-05-14）

**背景**：product-columns.json 最初是手动维护的 KGOS 专属目录（20条）。跑百浩创展（RITEKOKO品牌）时，resolvedSkus=0，因为 ERP 子品名找不到对应的 displayName。

**根因**：静态目录与店铺强绑定，换一个品牌就要手动加条目，违背"单次用完就丢"原则。

**修复**：resolve-components 运行时动态发现 ERP 子品名，直接用 ERP 原名作 displayName，写入 product-columns.json。clearCache() 刷新同进程缓存，确保后续 resolve-stock 读到最新目录。

**铁律**：
- product-columns.json 每次 resolve-components 清空重建，不手动维护
- resolve-components 必须先于 resolve-stock（stock 查询依赖目录做名称映射）
- 所有 data/ 文件均为运行时产出，全部加入 .gitignore

## L2 ERP 对应表虚拟滚动（2026-05-14 前沿用）

全量读取（readCorrWithoutDownload）返回 0 行，因为对应表使用虚拟滚动。改用逐货号精确搜索（每次搜一个货号，只渲染1行），绕过虚拟滚动。
