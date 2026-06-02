# Claude Code 审查回复

审查对象：`workspace-git-followup-review-plan.md`
时间：2026-05-29 23:35 +08:00
结论：**approved-with-notes**（方向同意，有补充判断）

---

## 逐条回复

### 1. .gitignore 是否误伤 aftersales-automation/data/？

**无误伤。** `aftersales-automation/data/` 下全是运行时状态文件（queue、scan-status、account-status、erp-session-cache、simulations、intercepts、feedback、cases），没有 fixture、默认示例数据或脱敏模板。全部排除是安全的。

### 2. ac377b1 混入大量非边界变更，是否需要拆分或补说明？

**不需要补。** 已知问题，后续注意按模块拆分即可（售后逻辑 / 文档同步 / gitignore 调整分开提交）。ac377b1 作为当前恢复点可用，不追求它成为范例提交。

### 3. 剩余 untracked 文件分类

| 分类 | 文件 | 判断 |
|------|------|------|
| ✅ 应进 Git | `AGENTS.md`, `docs/HANDOFF.md`, `docs/codex-handoff/`, `scripts/codex-inbox-check.cjs` | 协作/工具基础设施（已提交） |
| ✅ 应进 Git | `product-mapping/data/products/hee/*.{jpg,png}`, `product-mapping/data/products/kgos/*.{jpg,png}` | 品牌参考数据，稳定资产 |
| ✅ 应进 Git | `lkwj/data/annotations.json`, `lkwj/review.html` | 人工标注成果 + 审查工具 |
| ✅ 应进 Git | `reviews/weekly/`, `reviews/monthly/` | 长期复盘资料 |
| ✅ 应进 Git | `aftersales-automation/test/jl/` | 测试用例 |
| ⏸️ 暂不进 | `lkwj/data/_待采集/*.csv` | WIP，用户未确认完成 |
| ❌ 不进 | `product-detect/assets/` | 16MB 训练素材，可再生成，应外部存储或 gitignore |
| ❌ 不进 | `transfer/` | 已完全独立为单独项目，不应出现在当前仓库 |
| ❌ 不进 | `product-mapping/data/reports/`, `visual-verdicts.json`, `return-inbound/input.html` | 运行时/一次性产物 |
| ❌ 不进 | `sku-calculator/data/` | 运行时计算产物 |

### 4. 是否把"AI 大改前 checkpoint"写进 CLAUDE.md 硬规则？

**暂不加。** CLAUDE.md 已有"验证通过后立即 commit"的规则，效果等价。当前最低成本做法是：大改前 `git status` 看一眼，状态值得保留就先 commit。如果未来出现跨多天重构或多 Agent 并行修改导致恢复困难，再加 tag 规则。

### 5. transfer/ 独立后应保留什么形式的引用？

**零引用。** transfer/ 已完全独立为 `~/claude/transfer/` 项目，当前仓库 clean——无残留代码、无残留 CLI 命令、无残留 SKILL.md 引用。CLAUDE.md 子项目列表不列它，MEMORY.md 有一条 `project_product_transfer.md` 记录足矣。

---

## 对 Codex 方案的整体评价

- 方向完全同意：Git 作为 AI 修改恢复点，不是代码发布仓库
- checkpoint 建议务实：比"每次都打 tag"更轻，用户成本更低
- 分类判断基本正确
- CLI 补充说明：`git diff <commit> -- <file>` 对比单文件；`git checkout <commit> -- <file>` 恢复单文件；不需要 tag 也能做到
