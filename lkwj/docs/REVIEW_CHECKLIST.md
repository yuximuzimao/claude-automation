# 洛克王国数据核对任务

**你的任务**：对照 Excel 表格，全量核对 JSON 文件中的数据是否正确。**只输出核对结果，不做任何修改。**

---

## 文件位置

| 文件 | 路径 |
|------|------|
| Excel 表格 | `~/Downloads/` 目录下，文件名含"图鉴"或"课题"的 .xlsx 文件 |
| pets.json | `~/claude/lkwj/data/pets.json` |
| tasks.json | `~/claude/lkwj/data/tasks.json` |
| evolution-chains.json | `~/claude/lkwj/data/evolution-chains.json` |

---

## 读取 Excel 的方法

openpyxl 版本不兼容，用以下方式读取：

```python
import zipfile
from xml.etree import ElementTree as ET

def read_xlsx(path):
    with zipfile.ZipFile(path) as z:
        strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            tree = ET.parse(z.open('xl/sharedStrings.xml'))
            for si in tree.getroot().iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t'):
                strings.append(si.text or '')
        wb = ET.parse(z.open('xl/workbook.xml'))
        sheets = {}
        for s in wb.getroot().iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet'):
            sheets[s.get('name')] = s.get('{http://schemas.openxmlformats.org/relationships}id')
        rels = ET.parse(z.open('xl/_rels/workbook.xml.rels'))
        rid_map = {r.get('Id'): r.get('Target') for r in rels.getroot()}
        result = {}
        for name, rid in sheets.items():
            target = rid_map[rid]
            ws = ET.parse(z.open('xl/' + target))
            rows = []
            for row in ws.getroot().iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row'):
                r = {}
                for c in row:
                    col = ''.join(filter(str.isalpha, c.get('r', '')))
                    t = c.get('t', '')
                    v = c.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
                    if v is not None and v.text:
                        r[col] = strings[int(v.text)] if t == 's' else v.text
                if r:
                    rows.append(r)
            result[name] = rows
    return result
```

---

## 核对项目一：精灵名称和系别（全量）

**Excel 来源**：sheet「课题进度」  
- A 列：编号（如 `N.001`、`N.056`）  
- B 列：精灵名称  
- C 列：系别，多系别用逗号分隔（如 `火,龙`）

**JSON 来源**：`~/claude/lkwj/data/pets.json`  
- key 格式：`pet_1` 对应 N.001，`pet_56` 对应 N.056，以此类推  
- 字段：`name`（名称），`element`（系别数组，如 `["火","龙"]`）

**核对全部精灵**：
1. 表格中每个 N.xxx（跳过 A 列为空的行）→ 检查 pets.json 中是否有对应的 `pet_N` key
2. 名称是否一致
3. 系别是否一致（表格 `火,龙` 对应 JSON `["火","龙"]`）
4. JSON 中 `element` 数组的每个值必须是完整字样（正确：`普通`；错误：`普`）

**已知例外**：N.351、N.352 在表格中是空白行，pets.json 中正常不存在这两个 key。

---

## 核对项目二：任务数量（全量）

**Excel 来源**：sheet「课题进度」  
- A 列有值（如 `N.011`）：新精灵开始  
- A 列为空：该精灵的后续任务行  
- F 列：任务类型（`捕捉`、`技能`、`进化`、`首领`、`果实`、`炫彩`、`异色`、`天分`、`奖牌` 等）
- F 列为 `异色` 的行属于世界图鉴课题任务，导入为 `capture_shiny`

**JSON 来源**：`~/claude/lkwj/data/tasks.json`  
- key 格式：`pet_1`，值为任务数组，每条任务有 `type` 字段

**核对全部精灵**：对每只精灵，数出表格的任务行数 vs tasks.json 的任务数组长度，记录所有不一致。

### 异色专项口径

1. `tags.shiny`、`capture_shiny` 和 `shiny_progress` 分别表示世界定义、官方课题、用户收集进度，三者不得互相反向生成。
2. `capture_shiny` 只按官方课题行录入，固定挂在进化链终点；分支进化的两个终点分别核对。
3. 通行证异色不应存在 `capture_shiny`，除非后续官方课题资料明确增加。
4. 异色页只展示最终进化物种；基础和中间进化阶段不重复展示。
5. 最终物种存在多形态时，异色收集项只拆为所有非 `basic`、非 `leader` 的实际可收集形态；`basic` 不额外计数。没有额外形态时才保留一个默认外观收集项。
6. 无额外形态的异色进度键为 `petKey`，形态异色进度键为 `petKey::formKey`。旧结构中多形态精灵遗留的 `petKey` 进度必须人工确认具体形态，不能自动迁移。
7. S3 常驻异色和奇遇异色的筛选标签统一为 `S3「铅字幻梦」`；S3 通行证使用 `S3通行证`。
8. “常驻”表示当赛季常规捕捉机制常驻，不等于跨赛季永久可获取。

---

## 核对项目三：进化链（全量）

**Excel 来源**：sheet「课题进度」中 F 列 = `进化` 的行  
- I 列：进化条件（如 `32级进化`、`40级+使用15次【流星火雨】`）
- 该行所属精灵 = 往上找最近一个 A 列有值的行

**JSON 来源**：`~/claude/lkwj/data/evolution-chains.json`  
- 数组，每条链有 `baseSpeciesId`（起始精灵）、`nodes` 字典  
- nodes 中每个精灵有 `evolvesTo` 数组，内含 `toSpeciesId`（进化目标）和 `condition`（进化条件）

**核对**：对表格中每只有进化任务的精灵：
1. 在 evolution-chains.json 中找到包含该精灵的链
2. 验证 `evolvesTo` 不为空（能进化的精灵必须有进化目标）
3. 验证进化级别与表格 I 列描述一致（`condition.level` 对应表格中的级数）

---

## 核对项目四：精灵果实课题任务（全量）

**Excel 来源**：sheet「课题进度」  
- F 列：任务类型为 `果实`
- G 列：课题内容，一般对应“捕捉20只”
- I 列：备注/达成方式

**JSON 来源**：`~/claude/lkwj/data/tasks.json` 中 `type` 为 `"fruit"` 的任务

**严格口径**：
1. fruit 是“精灵果实课题任务”，说人话就是“捕捉20只获得果实”。
2. 是否有 fruit 任务只以 `课题进度` sheet 为准；`果实进度` sheet 不是任务清单。
3. `果实进度` sheet 是家族级果实记录，可用于补充已有 fruit 任务的达成方式，不能反向给进化链每个形态生成任务。
4. 有果实不代表有 fruit 任务；有 fruit 任务一定有果实。
5. 非最终形态不要因为同家族有果实而新增 fruit 任务，例如 N.239、N.240 当前不应有 fruit 任务。

**核对步骤**：
1. 从 `课题进度` sheet 统计 F 列 = `果实` 的任务行，预期为 96 条。
2. 对每个 `课题进度` fruit 行，检查 `tasks.json` 对应 pet 是否有 `type: "fruit"` 任务。
3. 检查 `tasks.json` 中是否存在不在 `课题进度` fruit 行内的 `type: "fruit"` 任务。
4. 当前已知错误模式：`type: "fruit" && desc: "获得果实"` 是从果实图鉴/家族果实误生成的伪任务，预期应删除 256 条。
5. 对已有 fruit 任务的 `obtainMethods`，可参考 `课题进度` I 列和 `果实进度` C/D 列补充，但不得因此新增任务。

---

## 核对项目五：多形态收集与形态课题

**Excel 来源**：
- sheet「多形态进度」
  - A 列：精灵编号
  - B 列：精灵名称
  - D 列：形态名称
  - E 列：捕捉方式
- sheet「课题进度」
  - F 列：任务类型为 `形态`
  - G 列：课题内容，如“确认2种不同样子的鸭吉吉”
  - I 列：课题计入范围备注

**JSON 来源**：
- `pets.json` 的 `forms`
- `tasks.json` 中 `type: "confirm_forms"` 的任务
- `collections.json` 的 `sprite_progress[petKey].forms_collected`

**严格口径**：
1. `pets.forms` 保存全部可收集形态，不只保存课题计入形态。
2. `basic` 和 `leader` 不属于多形态独立收集项。
3. `confirm_forms.requiredForms` 只表示世界图鉴课题计入的形态。
4. 多形态完成状态来自 `collections.sprite_progress[petKey].forms_collected`，不再单独勾选 `confirm_forms` 任务。
5. 课题外形态可以出现在「多形态」Tab，但不得反向增加课题任务数量。

**核对步骤**：
1. 从 `多形态进度` sheet 统计所有形态行，检查 `pets.json` 是否有对应 `forms` 记录。
2. 对每个 form，检查 `formName` 和 `obtainMethods` 是否覆盖 Excel 的形态名和捕捉方式。
3. 从 `课题进度` sheet 统计 F 列 = `形态` 的任务行，预期 `tasks.json` 中 `confirm_forms` 为 52 条。
4. 每条 `confirm_forms.requiredForms` 必须引用同 pet 下真实存在的 form key，且不得包含 `basic` 或 `leader`。
5. `requiredForms.length` 应等于任务 `count`。如果 `pets.forms` 数量大于 `count`，多出来的是课题外独立收集项。
6. 重点检查鸭吉吉：`pets.forms` 应有 6 个独立形态，`requiredForms` 只应包含「蓬松的样子」「紧实的样子」。
7. 重点检查梦悠悠：应包含「穿旧睡衣的样子」「穿星星睡衣的样子」，且 `confirm_forms.count` 为 2。
8. 重点检查遁地鼠/加油蟹：遁地鼠只应有「储水时的样子」「枯水期的样子」；加油蟹才有「单只海葵的样子」「双只海葵的样子」。形态名称本身不额外加括号。

**可直接运行的验证脚本**：

```bash
cd ~/claude/lkwj
node scripts/validate-multiform-data.js
node scripts/validate-multiform-ui.js
```

---

## 输出格式

```
## 核对结果

### 一、精灵名称和系别
- 总检查数：xxx
- 一致：xxx
- 差异列表：
  - N.xxx 表格"A" vs JSON"B"
  - ...
- 系别缩写问题：有/无（列出）

### 二、任务数量
- 总检查数：xxx
- 一致：xxx
- 差异列表：
  - pet_xx（N.xxx）：表格 x 条 vs JSON x 条
  - ...

### 三、进化链
- 有进化任务的精灵总数：xxx
- 链中有进化目标：xxx
- 差异列表：
  - pet_xx：表格有进化但 JSON evolvesTo 为空
  - pet_xx：进化级别不一致（表格 32级 vs JSON level:40）
  - ...

### 四、精灵果实课题任务
- 课题进度 fruit 行数：xxx
- 实际 fruit 任务数：xxx
- 缺失列表：
  - pet_xx（N.xxx）：课题进度有 fruit 任务但 tasks.json 中无 fruit 任务
  - ...
- 伪 fruit 任务：有/无（列出不在课题进度 fruit 行内的 pet_xx）

### 五、多形态收集与形态课题
- 多形态收集项：xxx
- 有额外形态的精灵：xxx
- confirm_forms 任务数：xxx
- requiredForms 引用错误：有/无（列出 pet_xx 和 form key）
- 课题外独立形态：有/无（列出典型项，如鸭吉吉）
- 已运行验证脚本：是/否
```
