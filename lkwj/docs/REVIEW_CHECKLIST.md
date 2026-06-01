# 洛克王国数据核对——Workbuddy 复核说明

**日期**：2026-06-01  
**复核范围**：pets.json / tasks.json / evolution-chains.json  
**数据来源**：外部玩家整理的图鉴课题进度表（xlsx，8个sheet）  
**数据规模**：373只精灵，165条进化链，~1850条任务

---

## 一、核对完成事项（6大任务）

### Task 1：精灵基础信息（编号/名称/系别）✅
- **规则**：pets.json 格式为 `{"pet_N": {"name": "...", "element": ["系别1","系别2"], ...}}`
- **变更**：39个名称修正（对照表格），51个系别缩写展开（普→普通，机→机械 等），新增20只 S2 精灵（pet_356~375），删除 pet_351/pet_352（表格 N.351/352 为空白保留位）
- **检验点**：
  - `element` 数组必须用完整系别字样，禁止缩写
  - N.351/N.352 在表格中为空行，pets.json 中不应有这两个 key
  - S2 精灵（pet_348~375，跳过 351/352）共 26 只

### Task 2：tasks.json 全量校对 ✅
- **规则**：每只精灵有一个任务数组，从 "课题进度" sheet 逐行解析
- **任务类型表**：

  | type | 含义 | 典型 count 字段 |
  |------|------|----------------|
  | capture | 捕捉 | 无 |
  | capture_gifted | 了不起天分捕捉 | 无 |
  | affection | 好感度（仅迪莫有） | 无 |
  | destined_hero | 命定勇者奖牌 | 无 |
  | skill | 使用技能 | 使用次数 |
  | evolve | 普通进化 | 无（desc 含进化条件） |
  | leader_evolve | 首领进化 | 无 |
  | capture_chromatic | 捕捉炫彩突变 | 无 |
  | confirm_forms | 确认多形态 | 种类数 |
  | fruit | 获得果实 | 无（desc 含获取方式） |

- **特殊情况**：
  - 迪莫（pet_1）只有 `affection` 任务，无捕捉任务
  - 373 只精灵全部有任务条目（含空数组：pet_353 凡鹰任务为空，这是正常的）
  - 幽冥眼（pet_56）：表格写作"幽灵眼"，属表格错别字，游戏内名字为"幽冥眼"，以 pets.json 中的名字（幽冥眼）为准

### Task 3：形态键名修正 ✅
**多形态（名称不改变）**：50只精灵在 pets.json `forms` 字段下有除 `basic` 之外的形态 key，形态名来自 "多形态进度" sheet 第 D 列。

**首领形态（名称改变）**：27只精灵新增 `forms.leader` 字段，formName = 首领进化后的新名字。

- **已确认首领名（来自表格「首领信物」模式）**：
  - pet_20 岚鸟 → 霜翼领主
  - pet_29 布克棱岩 → 迷嶂布莱克
  - pet_35 幽影树 → 幻影荆棘
  - pet_40 晶石蜗 → 钻石蜗
  - pet_43 奇丽花 → 奇丽果
  - pet_48 音速犬 → 风暴战犬
  - pet_84 花魁蜂后 → 女王蜂
  - pet_107 罗隐 → 深渊罗隐
  - pet_115 仪式巨像 → 祭礼巨像
  - pet_122 黑猫巫师 → 黑猫密探
  - pet_131 恶魔狼 → 恶魔狼王
  - pet_144 雪影娃娃 → 雪影冰灵
  - pet_189~192 棋系列 → 棋契陛下（4只精灵共同进化为1个首领）
  - pet_200 梦想三三 → 奇梦咪
  - pet_204 伊兰亚龙 → 伊兰龙
  - pet_228 爵士鹿 → 波普鹿
  - pet_233 高脚鹬 → 高帽脚鹬
  - pet_286 圣剑-X → 圣剑骑士
  - **pet_11 鸭吉吉 → 鸭吉吉国王**（进化链截图确认）

- **⚠️ 待用户确认（formName 暂填"首领形态"，实际首领名未从表格推导）**：
  - pet_4 魔力猫（首领信物名「阳光罐头」，非首领名）
  - pet_7 火神（首领信物名「熔炼之火」）
  - pet_10 水灵（首领信物名「命运钥匙」）
  - pet_110 彩蝶鲨（首领信物名「遥远之音」）
  - pet_117 白金独角兽（首领信物名「生长痛」）

### Task 4：进化链全量核对与补充 ✅
- **规则**：evolution-chains.json 数组，每条链有 `chainId`、`baseSpeciesId`、`nodes` 字典
- **变更**：
  - 修复 幽星光→曜星光→暮星辰 链（原来三只分拆为3条孤立链，现合并为 chainId:152）
  - 删除旧的错误 S2 占位链（chainId 163~170，引用了不存在的 pseudo pet ID）
  - 新增 S2 进化链 10 条（chainId 172~181）：
    - 爆焰仔→爆焰喷喷（40级+15次流星火雨）
    - 猴麦仔→音碟吼（32级）
    - 加油海葵→加油蟹（30级，形态由进化时所在世界决定）
    - 小丑豆豆→小丑兔→小丑公爵（24级+溜达/36级）
    - 烟花团→烟花伯爵（36级+溜达）
    - 咕咕帽→咕德帽帽（36级+溜达）
    - 炫光迪迪→霹雳迪迪（32级）
    - 小鼓象→巨鼓象（36级+跟随）
    - 牵线木偶→帅帅木偶（40级）
    - 学院呱呱（单只，无进化）
  - 新增 S1 晚期链（chainId 163~165）：
    - 钨丝贝贝→辉光幕机→机幕方舟（28级+1星/40级+2星）
    - 凡鹰（单只）
    - 小雪人→雪怪（40级+15次滚雪球）

- **数据完整性**：
  - 373 只精灵全部在链中 ✓
  - 无幽灵节点（链中引用的 pet ID 全部在 pets.json 中存在）✓
  - 每只精灵只出现在一条链中 ✓

### Task 5：果实进度结合任务核对 ✅
- **规则**：有果实的精灵在 tasks.json 中有 `type: "fruit"` 任务，desc 来自 "果实进度" sheet
- **变更**：新增 258 条果实任务，最终 354 只精灵有果实任务
- **无果实的精灵**（表格标注"无果实"，不应有 fruit 任务）：
  - 里奥家族（pet_150~152）：传说精灵，无果实
  - 小帕尔家族（pet_293~295）：传说精灵，无果实
  - 果冻家族（pet_313~316）：特殊奇遇，无果实
  - 星尘虫家族（pet_317~319）：特殊奇遇，无果实
  - 钨丝贝贝家族（pet_348~350）：传说精灵，无果实

### Task 6：获取方式字段补充 ✅
- 在 Task 3（形态修正）中已同步写入 `forms.{key}.obtainMethods[]`
- 数据来源：多形态进度 sheet E 列（多形态获取方式）+ 课题进度首领信物备注

---

## 二、核对方法

### 如何验证

1. 启动服务：`node server.js`（端口 8899）
2. 打开 `http://localhost:8899`，检查 Tab 显示是否正常

### 快速一致性检查命令

```bash
# 在 ~/claude/lkwj/ 目录下运行

# 检查精灵总数
node -e "const p = require('./data/pets.json'); console.log(Object.keys(p).length)"
# 期望：373

# 检查进化链数量
node -e "const c = require('./data/evolution-chains.json'); console.log(c.length)"
# 期望：165

# 检查无幽灵节点
node -e "
const c = require('./data/evolution-chains.json');
const p = require('./data/pets.json');
const ghosts = [...new Set([].concat(...c.map(x => Object.keys(x.nodes))))].filter(id => !p[id]);
console.log('Ghost nodes:', ghosts)"
# 期望：Ghost nodes: []

# 检查所有精灵都在链中
node -e "
const c = require('./data/evolution-chains.json');
const p = require('./data/pets.json');
const inChain = new Set([].concat(...c.map(x => Object.keys(x.nodes))));
const missing = Object.keys(p).filter(id => !inChain.has(id));
console.log('Missing from chain:', missing)"
# 期望：Missing from chain: []

# 检查系别不含缩写
node -e "
const pets = require('./data/pets.json');
const abbrevs = ['普','机','光','火','水','草','毒','地','虫','翼','鬼','幻','冰','龙','钢','幽'];
const abbrevSet = new Set(abbrevs);
const bad = Object.entries(pets).filter(([,p]) => p.element.some(e => abbrevSet.has(e)));
console.log('Abbrev elements:', bad.map(([id,p]) => id+' '+p.name+': '+p.element))"
# 期望：[]

# 检查不存在 pet_351 和 pet_352
node -e "
const p = require('./data/pets.json');
console.log('pet_351:', p.pet_351 || 'ok (deleted)');
console.log('pet_352:', p.pet_352 || 'ok (deleted)')"
```

---

## 三、已知遗留问题（等用户确认）

| 序号 | 类型 | 描述 | 位置 |
|------|------|------|------|
| 1 | 首领名 | 魔力猫首领形态真实名称 | pets.pet_4.forms.leader.formName |
| 2 | 首领名 | 火神首领形态真实名称 | pets.pet_7.forms.leader.formName |
| 3 | 首领名 | 水灵首领形态真实名称 | pets.pet_10.forms.leader.formName |
| 4 | 首领名 | 彩蝶鲨首领形态真实名称 | pets.pet_110.forms.leader.formName |
| 5 | 首领名 | 白金独角兽首领形态真实名称 | pets.pet_117.forms.leader.formName |

以上5只精灵的 `forms.leader.formName` 暂填"首领形态"，等用户在游戏内确认实际名称后修正。

---

## 四、数据文件位置

```
~/claude/lkwj/data/
├── pets.json              # 373只精灵定义（静态）
├── tasks.json             # 373只精灵任务列表（静态）
├── evolution-chains.json  # 165条进化链（静态）
├── collections.json       # 用户进度（动态）
├── shops.json             # 商店数据（静态）
├── wallet.json            # 货币（动态，不提交git）
└── annotations.json       # 标注日志（动态，不提交git）
```
