# lkwj 果实数据全量补充 — 审查请求

**发起方**：claude  
**日期**：2026-06-04  
**任务**：独立审查已完成的果实数据重构，验证正确性

---

## 背景

lkwj 项目完成了果实数据全量补充（commit `ce01716`，branch `data-model-restructure`）。  
实现内容：
- `pets.json`：99 → 145 个精灵有 `fruit` 字段，新增 `obtainMethod`、`obtainType`、`exclusiveGroup` 字段
- `index.html`：果实标签页渲染重构，显示真实获取方式 + 互斥组灰显逻辑
- `SKILL.md`：文档同步更新

Claude 请 Codex 做独立审查，发现问题直接写在回复文件中。

---

## 数据模型

```json
"fruit": {
  "name": "XX果实",
  "acquired": false,
  "obtainMethod": "捕捉20只幽冥眼",        // 具体获取描述（Excel 果实进度 D列备注）
  "obtainType": "课题任务",                 // 6分类之一
  "exclusiveGroup": "pass_s1"              // 可选，互斥组ID
}
```

**6种 obtainType**：`课题任务` / `智慧树苗` / `剧情任务` / `通行证契约礼券` / `赛季作业` / `限时活动`

**互斥组规则**：同赛季通行证来源的果实二选一，同代御三家三选一
- `starter_gen1`: pet_4, pet_7, pet_10
- `starter_gen2`: pet_155, pet_158, pet_161  
- `pass_s1`: pet_309, pet_312
- `pass_s2`: pet_355, pet_357

**无果实的7个家族**（pets.json 不含 fruit 字段）：
- 迪莫(pet_1)、里奥(pet_293)、小帕尔(pet_348)、钨丝贝贝(pet_313)、果冻(pet_317)、星尘虫(pet_375)、学院呱呱(pet_150)

---

## 验证数据（Claude 运行后的输出）

```
有果实: 145
有获取方式: 145
按类型: {"剧情任务":6,"课题任务":98,"智慧树苗":17,"通行证契约礼券":4,"赛季作业":16,"限时活动":4}
7个无果实家族确认无 fruit 字段 ✓
有互斥组: 10
总任务数: 1848
fruit tasks: 96
```

---

## 请 Codex 审查以下内容

### 1. pets.json 果实数据正确性

运行以下验证脚本：

```bash
cd ~/claude/lkwj && node -e "
const pets = require('./data/pets.json');
const withFruit = Object.entries(pets).filter(([k,v]) => v.fruit);

// 检查所有 fruit 有 obtainType（6分类之一）
const validTypes = new Set(['课题任务','智慧树苗','剧情任务','通行证契约礼券','赛季作业','限时活动']);
const invalidType = withFruit.filter(([k,v]) => !validTypes.has(v.fruit.obtainType));
console.log('obtainType非法:', invalidType.map(([k,v]) => k + ':' + v.fruit.obtainType));

// 检查互斥组成员
const groups = {};
withFruit.forEach(([k,v]) => {
  if (v.fruit.exclusiveGroup) {
    const g = v.fruit.exclusiveGroup;
    if (!groups[g]) groups[g] = [];
    groups[g].push(k + '(' + v.name + ')');
  }
});
console.log('互斥组:', JSON.stringify(groups, null, 2));

// 检查7个无果实家族
const noFruitCheck = ['pet_1','pet_150','pet_293','pet_348','pet_313','pet_317','pet_375'];
const wrongNoFruit = noFruitCheck.filter(id => pets[id]?.fruit);
console.log('应无果实但有fruit字段:', wrongNoFruit.length > 0 ? wrongNoFruit : '无（正确）');

// 检查课题任务类型的 obtainMethod 格式是否符合 '捕捉N只{精灵名}' 模式
const captureType = withFruit.filter(([k,v]) => v.fruit.obtainType === '课题任务');
const badCapture = captureType.filter(([k,v]) => !v.fruit.obtainMethod?.startsWith('捕捉'));
console.log('课题任务类型但obtainMethod不以捕捉开头:', badCapture.map(([k,v]) => k + ':' + v.fruit.obtainMethod));

// 检查智慧树苗类型的 obtainMethod 是否包含地点信息
const wisdomType = withFruit.filter(([k,v]) => v.fruit.obtainType === '智慧树苗');
console.log('智慧树苗类型条数:', wisdomType.length, '样本:');
wisdomType.slice(0,3).forEach(([k,v]) => console.log('  ', k, v.name, ':', v.fruit.obtainMethod));

// 检查通行证类型
const passType = withFruit.filter(([k,v]) => v.fruit.obtainType === '通行证契约礼券');
console.log('通行证类型:', passType.map(([k,v]) => k + '(' + v.name + ') exclusiveGroup=' + v.fruit.exclusiveGroup));
"
```

**具体审查点**：
1. 是否所有 145 个 fruit 的 `obtainType` 都是合法的 6 分类之一？
2. 互斥组成员是否正确（4组10个）？
3. 7个无果实家族确认无 `fruit` 字段？
4. 课题任务类型的 `obtainMethod` 格式是否合理？
5. 进化链分叉终点（乖乖鹄家族 pet_90/pet_91，毛头小蛛家族 pet_297/pet_298）：两个终点是否都有 fruit？obtainMethod 是否合理？

```bash
cd ~/claude/lkwj && node -e "
const pets = require('./data/pets.json');
// 检查分叉终点
['pet_90','pet_91','pet_297','pet_298'].forEach(id => {
  const p = pets[id];
  console.log(id, p?.name, '有fruit:', !!p?.fruit, p?.fruit?.obtainMethod);
});
"
```

---

### 2. index.html 互斥组逻辑审查

文件：`~/claude/lkwj/index.html`

找到 `renderFruitRow` 函数，检查：

1. **exclusiveBlocked 检测逻辑**：是否正确扫描 `allPets` 中同 `exclusiveGroup` 的其他精灵，检查其 `acquired === true`？
2. **灰显逻辑**：exclusiveBlocked 时是否 opacity 降低 + checkbox disabled + 显示"已不可获取"标记？
3. **课题任务类型的获取地点**：`obtainType === '课题任务'` 时是否额外调用 `getCaptureObtainMethods(petKey)` 显示捕捉地点？
4. **toggleFruit 函数**：是否正确读写 `sprite_progress[petKey].fruit_acquired`？是否在切换后重新渲染？

---

### 3. SKILL.md 文档准确性

文件：`~/claude/lkwj/SKILL.md`

对照 pets.json 实际数据，检查：
1. 果实总数：145（有果实），7（无果实）
2. fruit 字段的 3 个新子字段描述是否准确（obtainMethod / obtainType / exclusiveGroup）
3. 6种获取方式分类列表是否完整
4. 互斥组规则描述是否包含"通行证同赛季二选一"的通用规则

---

## 回复格式

请按以下格式回复到 `docs/codex-handoff/lkwj-fruit-data-review-response.md`：

```
# lkwj 果实数据审查回复

**审查结论**：通过 / 部分通过（N个问题） / 失败（阻塞性问题）

## 验证输出
（粘贴实际运行的脚本输出）

## 发现的问题
（每个问题一条，注明严重程度：阻塞/建议/提示）

## 结论
```

---

完成后在 `docs/codex-handoff/inbox.json` 的 `pending` 中添加回复条目，Claude 下次 session 会读取。
