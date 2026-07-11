# 服装明细与华丽魔法 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将用户提供的服装单品、套装件数、付费扩展组件和华丽魔法关系安全导入收集助手，并让页面按个人收集目标正确统计与展示。

**Architecture:** 保留 `clothing.json` 的 `sets[] + pieces[]` 边界，在套装上增加华丽魔法对应精灵和必需件数，在部件上增加分类、部件作用、获取类型与原始名称。用独立数据校验脚本守住静态数据约束，前端只根据静态定义和 `collections.clothing_progress` 动态计算进度，不新增人工维护的“华丽魔法已解锁”状态。

**Tech Stack:** Node.js 标准库、原生 HTML/CSS/JavaScript、JSON/CSV、本项目现有静态验证脚本。

---

## 文件边界

- `data/clothing.json`：正式服装静态定义；保存概念、套装和部件，不保存个人进度。
- `data/collections.json`：个人已拥有状态；本轮把用户明确列出的单品 ID 设为 `true`。
- `data/_待采集/服装图鉴.csv`：可重复核对的本轮录入底稿；保留原始名称和待核对说明。
- `scripts/validate-clothing-data.js`：只校验服装数据完整性、枚举、引用、重复项和套装数量，不修改文件。
- `scripts/validate-clothing-ui.js`：验证页面确实按新模型展示和计算。
- `index.html`：服装标签的统计、筛选、套装进度、付费标记和概念说明。
- `SKILL.md`、`README.md`、`data/_待采集/README.md`、`tasks/todo.md`：同步正式字段、录入口径、真实数量和剩余待核对项。

## 执行前置

- [ ] **Step 1: 创建隔离 worktree**

执行时先调用 `using-git-worktrees` skill，在 `/Users/chat/claude/lkwj` 对应仓库创建隔离 worktree。原因：本计划会修改超过三个文件，必须避免和当前工作区其他项目的未提交内容互相污染。

- [ ] **Step 2: 记录基线**

Run:

```bash
node scripts/validate-clothing-ui.js
node -e "JSON.parse(require('fs').readFileSync('data/clothing.json','utf8')); JSON.parse(require('fs').readFileSync('data/collections.json','utf8')); console.log('clothing baseline ok')"
```

Expected:

```text
{
  "checks": 18
}
clothing baseline ok
```

### Task 1: 建立服装静态数据契约

**Files:**
- Create: `scripts/validate-clothing-data.js`
- Modify: `scripts/validate-clothing-ui.js`
- Test: `data/clothing.json`

- [ ] **Step 1: 写静态数据失败校验**

在 `scripts/validate-clothing-data.js` 中定义以下常量和检查：

```js
const fs = require('fs');
const path = require('path');

const clothing = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'clothing.json'), 'utf8'));
const categories = new Set([
  '玩偶服/连衣', '上衣', '下装', '头饰/帽子', '发型', '手饰', '面饰',
  '鞋子', '袜子', '背包', '包挂饰', '法杖', '华丽徽章',
]);
const roles = new Set(['magic_required', 'optional']);
const obtainTypes = new Set(['standard', 'paid']);
const errors = [];
const warnings = [];
const setsById = new Map((clothing.sets || []).map(set => [set.id, set]));
const ids = new Set();
const names = new Set();

if (!clothing.definitions?.gorgeousBadge?.description) errors.push('missing gorgeousBadge definition');
if (!clothing.definitions?.gorgeousMagic?.description) errors.push('missing gorgeousMagic definition');

for (const set of clothing.sets || []) {
  if (!set.id || !set.name) errors.push('set missing id/name');
  if (!Number.isInteger(set.requiredPieceCount) || set.requiredPieceCount < 1) {
    errors.push(`${set.name}: invalid requiredPieceCount`);
  }
}

for (const piece of clothing.pieces || []) {
  if (ids.has(piece.id)) errors.push(`duplicate id: ${piece.id}`);
  ids.add(piece.id);
  if (!categories.has(piece.category)) errors.push(`${piece.pieceName}: invalid category ${piece.category}`);
  if (!obtainTypes.has(piece.obtainType)) errors.push(`${piece.pieceName}: invalid obtainType ${piece.obtainType}`);
  if (piece.collectionType === 'set' && !setsById.has(piece.setId)) errors.push(`${piece.pieceName}: orphan setId`);
  if (piece.setRole && !roles.has(piece.setRole)) errors.push(`${piece.pieceName}: invalid setRole`);
  if (piece.obtainType === 'paid' && piece.setRole === 'magic_required') {
    errors.push(`${piece.pieceName}: paid piece cannot be magic_required`);
  }
  const identity = `${piece.collectionType}|${piece.setId || ''}|${piece.pieceName}`;
  if (names.has(identity)) errors.push(`duplicate piece: ${identity}`);
  names.add(identity);
}

for (const set of clothing.sets || []) {
  const required = (clothing.pieces || []).filter(piece => piece.setId === set.id && piece.setRole === 'magic_required');
  if (required.length > set.requiredPieceCount) errors.push(`${set.name}: required pieces exceed declared count`);
  if (required.length < set.requiredPieceCount) warnings.push(`${set.name}: ${required.length}/${set.requiredPieceCount} required piece names recorded`);
}

if (errors.length) {
  console.error(errors.join('\n'));
  process.exit(1);
}
console.log(JSON.stringify({
  sets: (clothing.sets || []).length,
  pieces: (clothing.pieces || []).length,
  paid: (clothing.pieces || []).filter(piece => piece.obtainType === 'paid').length,
  warnings,
}, null, 2));
```

- [ ] **Step 2: 运行校验并确认旧示例失败**

Run:

```bash
node scripts/validate-clothing-data.js
```

Expected: FAIL，至少包含 `missing gorgeousBadge definition` 或旧部件缺少 `category`。

- [ ] **Step 3: 扩展 UI 静态契约**

在 `scripts/validate-clothing-ui.js` 增加以下检查，先让它们失败：

```js
['clothing UI explains gorgeous badge', html.includes('华丽徽章说明')],
['clothing UI computes gorgeous magic progress', html.includes('getGorgeousMagicProgress')],
['clothing UI excludes paid pieces from targets', html.includes('isClothingTargetPiece')],
['clothing UI shows paid non-target label', html.includes('付费 · 非收集目标')],
['clothing UI filters by piece category', html.includes('clothingCategoryFilter')],
```

- [ ] **Step 4: 提交测试契约**

```bash
git add scripts/validate-clothing-data.js scripts/validate-clothing-ui.js
git commit -m "test(lkwj): define clothing detail contracts"
```

### Task 2: 结构化录入用户提供的数据

**Files:**
- Modify: `data/_待采集/服装图鉴.csv`
- Modify: `data/clothing.json`
- Modify: `data/collections.json`
- Test: `scripts/validate-clothing-data.js`

- [ ] **Step 1: 扩展录入底稿列**

将 CSV 表头改为：

```csv
collectionType,setName,requiredPieceCount,gorgeousMagicPetName,pieceName,category,setRole,obtainType,obtainMethod,obtained,rawText,notes
```

规则：

- 用户“已有的单品明细”全部记为 `obtained=是`、`obtainType=standard`。
- 套装名称后明确给出的“可解锁组件”记为 `setRole=optional`、`obtainType=paid`、`obtained=否`。
- 已有单品名称能按后缀唯一归属套装时，记录对应 `setName` 和 `setRole=magic_required`。
- 无法唯一归属套装的单品保留 `setName` 为空，不猜测套装。
- `=`、中文逗号或漏写连字符只修正分隔符，`rawText` 保留用户原文。
- “回忆/追忆”“宁静星原/宁静星愿”“精灵学院/精灵学分院”“魔法徽章/华丽徽章”等文字差异不自动合并，写入 `notes=待核对名称`。
- `面妆`、`眼型`、`瞳孔`、`口罩`暂归并到 `面饰`分类，但 `pieceName` 保留原始前缀。
- `初始法杖`等无分类前缀条目归到`法杖`；`初始发型1`等归到`发型`；`面妆1`至`面妆8`归到`面饰`。

示例行：

```csv
set,熔岩布丁印象,6,熔岩布丁,连衣-熔岩布丁印象,玩偶服/连衣,magic_required,standard,待补充,是,连衣-熔岩布丁印象,
set,熔岩布丁印象,6,熔岩布丁,华丽徽章-熔岩布丁,华丽徽章,optional,paid,单独充值购买解锁,否,华丽徽章-熔岩布丁,
single,,,,初始法杖,法杖,,standard,待补充,是,初始法杖,
```

- [ ] **Step 2: 替换示例数据并建立稳定 ID**

在 `data/clothing.json` 顶层写入 `definitions`、`sets`、`pieces`。ID 只追加且不依赖数组位置：套装使用 `clothing_set_N`，部件使用 `clothing_N`。旧示例占用的 `clothing_set_1` 与 `clothing_1` 至 `clothing_6` 退役且不复用；本轮从 `clothing_set_2` 和 `clothing_7` 开始，按用户原始输入首次出现顺序递增。同一条目的稳定身份是 `collectionType + setId + pieceName`。

定义结构（正式 JSON 保留完整概念原文，页面直接读取这里，不维护第二份）：

```json
{
  "definitions": {
    "gorgeousBadge": {
      "name": "华丽徽章",
      "description": "在解锁徽章后，可在获取精灵的炫彩形态时解锁新的时装炫彩染料，在换装时对套装中的某些特定部位作炫彩染色。不同套装可染色的部位不同。并且在解锁徽章后，可在精灵树解锁全新的和精灵的亲昵互动动作。在角色待机时也有概率自动触发和队列精灵的互动。在自定义搭配时装时仍可自动触发全部华丽魔法效果，包括精灵战斗召唤与胜利动作。"
    },
    "gorgeousMagic": {
      "name": "华丽魔法",
      "description": "集齐套装指定的全部必需部件后解锁；穿着对应套装，在对战中更换对应精灵进场时触发特殊登场演出。"
    }
  },
  "sets": [],
  "pieces": []
}
```

每个套装至少包含：

```json
{
  "id": "clothing_set_2",
  "name": "快乐的果实",
  "requiredPieceCount": 3,
  "gorgeousMagicPetName": "",
  "obtainMethod": "待补充"
}
```

每个部件至少包含：

```json
{
  "id": "clothing_7",
  "collectionType": "set",
  "setId": "clothing_set_2",
  "pieceName": "玩偶服-快乐的果实",
  "category": "玩偶服/连衣",
  "setRole": "magic_required",
  "obtainType": "standard",
  "obtainMethod": "待补充"
}
```

- [ ] **Step 3: 写入个人已拥有状态**

只对用户明确列在“我已有的单品明细”中的部件写入：

```json
"clothing_progress": {
  "clothing_7": true
}
```

付费扩展部件不写 `false`；缺失键即表示未收集。保留 `collections.json` 中其他类别和进度原样不动。

- [ ] **Step 4: 运行数据校验并生成待核对清单**

Run:

```bash
node scripts/validate-clothing-data.js
node -e "const c=require('./data/collections.json'); const d=require('./data/clothing.json'); const unknown=Object.keys(c.clothing_progress||{}).filter(id=>!d.pieces.some(p=>p.id===id)); if(unknown.length) throw new Error('unknown clothing ids: '+unknown.join(',')); console.log('clothing progress references ok')"
```

Expected: 两条命令退出码均为 `0`；校验输出允许出现“已知部件名少于套装声明件数”的 warnings，但不得出现 errors。

- [ ] **Step 5: 单独提交正式静态数据**

`collections.json` 与 `_待采集/*.csv` 是本地运行数据，不进入提交；用户明确提供的正式世界定义 `clothing.json` 单独归档：

```bash
git add -f data/clothing.json
git commit -m "feat(lkwj): import clothing catalog details"
```

### Task 3: 在服装标签展示新模型

**Files:**
- Modify: `index.html`
- Test: `scripts/validate-clothing-ui.js`

- [ ] **Step 1: 增加目标判断和华丽魔法计算函数**

在服装 Tab 函数区加入：

```js
function isClothingTargetPiece(item) {
  return item.obtainType !== 'paid';
}

function getGorgeousMagicProgress(set, pieces) {
  const requiredTotal = Number(set?.requiredPieceCount || 0);
  if (!set?.gorgeousMagicPetName || requiredTotal < 1) return null;
  const acquired = pieces.filter(item => item.setRole === 'magic_required' && item.acquired).length;
  return {
    acquired,
    total: requiredTotal,
    unlocked: acquired >= requiredTotal,
    petName: set.gorgeousMagicPetName,
  };
}
```

- [ ] **Step 2: 修改顶部统计**

顶部“共 N 件 / 未收集”只统计 `isClothingTargetPiece(item)` 为真的部件；另加“付费资料 N 件”，避免付费资料消失但又不制造个人欠账。

核心计算：

```js
const targetPieces = clothing.filter(isClothingTargetPiece);
const paidPieces = clothing.filter(item => !isClothingTargetPiece(item));
const acquiredTargets = targetPieces.filter(item => item.acquired);
```

- [ ] **Step 3: 增加分类筛选**

增加状态变量：

```js
let clothingCategoryFilter = 'all';
```

筛选选项来自 `gameData.clothing.pieces` 中实际出现的 `category`，首项为“全部分类”。筛选时执行：

```js
if (clothingCategoryFilter !== 'all') {
  list = list.filter(item => item.category === clothingCategoryFilter);
}
```

- [ ] **Step 4: 修改套装卡片**

套装卡片同时展示：

- 个人目标收集进度。
- 已记录核心部件名数量与 `requiredPieceCount`；不足时显示“资料待补”。
- 华丽魔法对应精灵和自动计算的 `N/M` 或“已解锁”。
- 付费部件的“付费 · 非收集目标”标签与获取方式。
- 单件分类标签。

华丽魔法文案：

```js
const magic = getGorgeousMagicProgress(set, pieces);
const magicText = magic
  ? `华丽魔法：${magic.unlocked ? '已解锁' : `${magic.acquired}/${magic.total}`} · ${esc(magic.petName)}`
  : '';
```

- [ ] **Step 5: 增加概念说明区**

服装标签顶部增加可折叠“华丽徽章说明”，内容读取 `gameData.clothing.definitions`，不在 HTML 中维护第二份长定义。

- [ ] **Step 6: 运行 UI 校验**

Run:

```bash
node scripts/validate-clothing-ui.js
```

Expected: PASS，输出新的检查总数且不列出失败项。

- [ ] **Step 7: 提交 UI**

```bash
git add index.html scripts/validate-clothing-ui.js
git commit -m "feat(lkwj): show clothing targets and gorgeous magic"
```

### Task 4: 文档同步与全链路验收

**Files:**
- Modify: `SKILL.md`
- Modify: `README.md`
- Modify: `data/_待采集/README.md`
- Modify: `tasks/todo.md`
- Test: all clothing files

- [ ] **Step 1: 更新文档事实**

同步以下内容：

- `SKILL.md`：新字段、分类枚举、付费非目标规则、华丽魔法计算规则、`validate-clothing-data.js` 路径。
- `README.md`：真实套装/部件/付费资料数量，移除“只有示例/占位”的旧状态。
- `data/_待采集/README.md`：服装模板的新列和待核对名称清单。
- `tasks/todo.md`：服装状态改为“首批真实数据已导入”，保留缺失部件名、获取方式和名称差异核对任务。

- [ ] **Step 2: 运行完整验证**

Run:

```bash
node scripts/validate-clothing-data.js
node scripts/validate-clothing-ui.js
node -e "for (const f of ['data/clothing.json','data/collections.json']) JSON.parse(require('fs').readFileSync(f,'utf8')); console.log('clothing json ok')"
git diff --check
```

Expected: 所有命令退出码为 `0`；输出包含 `clothing json ok`；允许数据校验输出资料不完整 warnings，但无 errors。

- [ ] **Step 3: 启动本地服务做只读冒烟**

Run:

```bash
node server.js
```

浏览器检查 `http://localhost:8899`：

- 服装标签能打开。
- 熔岩布丁印象显示六件核心部件已收集、华丽魔法已解锁、对应精灵熔岩布丁。
- 四件付费扩展部件可见，但不计入个人总数。
- 搜索“熔岩布丁”和筛选“华丽徽章”均能命中正确条目。
- 刷新后已收集状态不丢失。

- [ ] **Step 4: 提交文档**

```bash
git add SKILL.md README.md data/_待采集/README.md tasks/todo.md scripts/validate-clothing-data.js
git commit -m "docs(lkwj): document clothing catalog workflow"
```

- [ ] **Step 5: 合并前数据安全检查**

Run:

```bash
git diff --diff-filter=D main...HEAD
git status --short
```

Expected: 不删除任何 `data/` 文件；`data/collections.json` 和 `data/_待采集/服装图鉴.csv` 的本地更新必须单独备份并在合并后写回主工作区，不能被 worktree 合并覆盖。

## 实施中的明确安全边界

- 不联网猜测游戏内名称或获取方式。
- 不把疑似错字直接覆盖为另一个名称。
- 不将“未列在已有单品明细中”等同于游戏中不存在。
- 不让付费扩展部件进入个人收集目标分母。
- 不为华丽魔法增加独立可勾选进度。
- 所有用户原有 `collections.json` 进度必须保留，只追加 `clothing_progress`。
