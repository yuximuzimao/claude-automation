# lkwj 果实数据审查回复

**审查方**：Codex（只读沙箱）+ Claude（修复写入）  
**日期**：2026-06-04  
**审查结论**：部分通过（1 个阻塞问题已修复，1 个文档提示已修复）

---

## 验证输出

```
有果实: 145
有获取方式: 145
按类型: {"剧情任务":6,"课题任务":98,"智慧树苗":17,"通行证契约礼券":4,"赛季作业":16,"限时活动":4}
7个无果实家族确认无 fruit 字段 ✓
有互斥组: 10
总任务数: 1848
fruit tasks: 96
分叉终点: pet_90/pet_91/pet_297/pet_298 均有 fruit ✓
```

---

## 发现的问题

### 1. 阻塞：果实进度刷新后失真（已修复）

**严重程度**：阻塞

**根因**：
- `toggleFruit()` 写入路径：`data.sprite_progress[petKey].fruit_acquired`（collections.json 动态进度）
- 同时在内存中直接 mutate：`pet.fruit.acquired = !pet.fruit.acquired`
- `renderFruitsTab()` / 互斥组检测读取：`pet.fruit.acquired`
- `/api/game-data` 返回的是静态 `pets.json`，`pet.fruit.acquired` 始终为初始值 `false`

**影响**：页面刷新后，已获得果实数量统计回零，已完成列表为空，互斥组禁用判断失效。

**修复位置**：`lkwj/index.html:420`（`init()` 函数内）

**修复内容**（在 `gameData` 和 `data` 加载后插入）：
```javascript
// 回填果实进度：sprite_progress.fruit_acquired → pet.fruit.acquired
if (gameData?.pets && data?.sprite_progress) {
  for (const [petKey, prog] of Object.entries(data.sprite_progress)) {
    if (prog.fruit_acquired != null && gameData.pets[petKey]?.fruit) {
      gameData.pets[petKey].fruit.acquired = prog.fruit_acquired;
    }
  }
}
```

**修复状态**：已写入 `index.html` ✓

---

### 2. 提示：SKILL.md 未记录 `fruit_acquired` 字段（已修复）

**严重程度**：提示

**根因**：`sprite_progress` 字段说明只提到 `tasks` 和 `forms_collected`，未提及新增的 `fruit_acquired`。

**修复位置**：`lkwj/SKILL.md:147`

**修复状态**：已追加说明 ✓

---

## 其他验证通过项

- **pets.json 结构**：145 个 fruit，100% 有 obtainMethod + obtainType，分类全部合法
- **互斥组**：4 组 10 个成员（starter_gen1/2、pass_s1/s2），成员精确
- **7 个无果实家族**：pet_1/150/293/313/317/348/375 均无 fruit 字段
- **任务数量**：1848 条（排除异色），96 条 fruit 课题任务，口径闭合
- **分叉终点继承**：pet_91（黑羽夫人）、pet_298（盲尾八爪）均有 fruit，obtainMethod 从同链另一终点继承，合理
- **index.html 互斥逻辑**：exclusiveBlocked 检测、灰显 + disabled + "已不可获取" 标记、课题任务追加捕捉地点，均正确
- **SKILL.md 文档**：145/7 数量、6 类获取方式、互斥组通用规则均已覆盖

---

## 结论

数据层完全正确。前端存在一个刷新后状态丢失的 bug（已修复）：`init()` 缺少将 `sprite_progress.fruit_acquired` 回填到 `gameData.pets.fruit.acquired` 的步骤。修复后所有进度在刷新后应正确恢复。
