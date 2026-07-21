# 果实导入与收集列表布局 Implementation Plan

> 状态：已完成并归档。本文保留实施过程，未勾选框不再代表当前待办。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 正确读取 Excel 果实候选记录并展示家族编号，同时让所有收集列表按固定顺序平铺且不分页。

**Architecture:** 将果实有效性、六类来源和家族编号范围集中在 `read-latest-excel.py`，同步与审计直接复用。前端保留现有 Tab 和筛选状态，只把内容渲染统一为固定顺序的单列表，并删除异色分页。

**Tech Stack:** Python 3、原生 JavaScript、HTML/CSS、现有 Node 校验脚本

---

### Task 1: 集中 Excel 果实判定并保存家族范围

**Files:**
- Modify: `scripts/read-latest-excel.py`
- Modify: `scripts/sync-latest-excel.py`
- Modify: `scripts/audit-latest-excel.py`
- Modify: `scripts/validate-s3-excel-sync.js`
- Create: `scripts/validate-fruit-excel-rules.py`
- Modify: `data/pets.json`
- Modify: `docs/REVIEW_CHECKLIST.md`

- [ ] **Step 1: 写失败校验**

`validate-fruit-excel-rules.py` 读取工作簿并断言：177 行候选、168 行有效、9 行无果实；迪莫和学院呱呱无效；未知来源抛出 `ValueError`；火神家族范围为 `[5, 7]`。`validate-s3-excel-sync.js` 断言每条 fruit 都有两个整数的 `familyNumberRange`。

- [ ] **Step 2: 运行校验并确认失败**

Run:

```bash
python3 scripts/validate-fruit-excel-rules.py
node scripts/validate-s3-excel-sync.js
```

Expected: 因共享判定函数和 `familyNumberRange` 尚不存在而失败。

- [ ] **Step 3: 写最小实现**

在 `read-latest-excel.py` 导出共享函数：

```python
NO_FRUIT_SOURCES = {"传说精灵", "特殊奇遇", "开局必送", "呱呱上学记"}

def classify_fruit_row(row):
    source = str(row.get("C") or "").strip()
    description = str(row.get("D") or "").strip()
    numbers = parse_fruit_numbers(row.get("A"))
    if source in NO_FRUIT_SOURCES or description.startswith("无果实"):
        return None
    obtain_type = map_fruit_obtain_type(source)  # 未知来源抛 ValueError
    return {"numbers": numbers, "obtainType": obtain_type}
```

同步脚本调用该函数，并写入：

```python
"familyNumberRange": [min(info["numbers"]), max(info["numbers"])]
```

审计脚本使用同一函数生成预期集合。运行 `python3 scripts/sync-latest-excel.py` 重建 `pets.json`，并把经验补入 `docs/REVIEW_CHECKLIST.md`。

- [ ] **Step 4: 运行校验并确认通过**

Run:

```bash
python3 scripts/validate-fruit-excel-rules.py
node scripts/validate-s3-excel-sync.js
python3 scripts/audit-latest-excel.py
```

Expected: 168 条有效果实、9 条无果实、fruit 差异为 0。

### Task 2: 固定排序、平铺列表并取消分页

**Files:**
- Modify: `index.html`
- Modify: `scripts/validate-tab-consistency-ui.js`
- Modify: `scripts/validate-shiny-ui.js`

- [ ] **Step 1: 写失败校验**

扩展 `validate-tab-consistency-ui.js`，断言：

```javascript
// 精灵入口显式数字排序
petEntries().map(([petKey]) => Number(petKey.replace('pet_', '')))
// 默认列表渲染源码不再调用 renderCollapsibleDoneSection
// 不存在 SHINY_PAGE、getShinyDisplayPage、renderPagination 调用
// 果实行包含 familyNumberRange 格式化结果
```

`validate-shiny-ui.js` 的真实渲染结果断言全部异色项目一次出现且按编号升序。

- [ ] **Step 2: 运行校验并确认失败**

Run:

```bash
node scripts/validate-tab-consistency-ui.js
node scripts/validate-shiny-ui.js
```

Expected: 因异色仍分页、默认状态仍拆分收集分组、果实未展示范围而失败。

- [ ] **Step 3: 写最小实现**

在 `index.html` 中：

```javascript
const petEntries = () => Object.entries(gameData?.pets || {})
  .sort((a, b) => Number(a[0].replace('pet_', '')) - Number(b[0].replace('pet_', '')));
```

- 异色和果实使用 `petEntries()`；异色按精灵编号、形态稳定顺序返回。
- 家具、称号、遗迹和通用品类按数字 ID 排序；服装保留现有稳定排序。
- 精灵、异色、多形态、果实、家具、称号、遗迹和通用品类在任何状态下都直接渲染当前过滤结果，不增加收集状态分组标题。
- 删除 `shinyPage`、`SHINY_PAGE`、`getShinyDisplayPage()`、`goShinyPage()` 和分页渲染。
- 果实行用 `No.起点-No.终点` 展示 `familyNumberRange`；单编号只显示一个编号。

- [ ] **Step 4: 运行校验并确认通过**

Run:

```bash
node scripts/validate-tab-consistency-ui.js
node scripts/validate-shiny-ui.js
node scripts/validate-search-expand-ui.js
```

Expected: 平铺、排序、无分页和单搜索自动展开校验全部通过。

### Task 3: 修复筛选区间距并完成全量验证

**Files:**
- Modify: `index.html`
- Modify: `README.md`
- Modify: `SKILL.md`

- [ ] **Step 1: 写失败校验**

在 `validate-tab-consistency-ui.js` 增加断言：拆分工具栏的 `sprite-toolbar` 与 `shiny-toolbar` 共用一个桌面间距类，果实获取方式没有手机端换行覆盖。

- [ ] **Step 2: 运行校验并确认失败**

Run:

```bash
node scripts/validate-tab-consistency-ui.js
```

Expected: 因工具栏间距类和桌面专用果实布局尚未实现而失败。

- [ ] **Step 3: 写最小实现**

```css
.split-tab-toolbar { margin-bottom: 14px; }
.fruit-method { white-space: nowrap; }
```

把类加到 `sprite-toolbar` 和 `shiny-toolbar`，删除 `.fruit-method` 的窄屏覆盖。将新果实规则校验命令补入 `README.md` 与 `SKILL.md`。

- [ ] **Step 4: 全量验证**

Run:

```bash
python3 scripts/validate-fruit-excel-rules.py
python3 scripts/audit-latest-excel.py
node scripts/validate-s3-excel-sync.js
node scripts/validate-multiform-data.js
node scripts/validate-multiform-ui.js
node scripts/validate-shiny-ui.js
node scripts/validate-search-expand-ui.js
node scripts/validate-random-task-ui.js
node scripts/validate-furniture-ui.js
node scripts/validate-clothing-data.js
node scripts/validate-clothing-ui.js
node scripts/validate-pet-badges-ui.js
node scripts/validate-tab-consistency-ui.js
node scripts/validate-title-ui.js
node scripts/validate-dungeon-ui.js
```

Expected: 全部退出码为 0；Excel 审计中未解决差异为 0。

- [ ] **Step 5: 提交实现**

```bash
git add README.md SKILL.md data/pets.json docs/REVIEW_CHECKLIST.md index.html scripts/read-latest-excel.py scripts/sync-latest-excel.py scripts/audit-latest-excel.py scripts/validate-fruit-excel-rules.py scripts/validate-s3-excel-sync.js scripts/validate-tab-consistency-ui.js scripts/validate-shiny-ui.js docs/superpowers/plans/2026-07-21-fruit-import-and-list-layout.md
git commit -m "fix(lkwj): validate fruit rows and flatten collection lists"
```
