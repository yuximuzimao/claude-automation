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
- F 列：任务类型（`捕捉`、`技能`、`进化`、`首领`、`果实`、`炫彩`、`天分`、`奖牌` 等）

**JSON 来源**：`~/claude/lkwj/data/tasks.json`  
- key 格式：`pet_1`，值为任务数组，每条任务有 `type` 字段

**核对全部精灵**：对每只精灵，数出表格的任务行数 vs tasks.json 的任务数组长度，记录所有不一致。

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

## 核对项目四：果实任务（全量）

**Excel 来源**：sheet「果实进度」  
- A 列：精灵编号范围（如 `N.011` 或 `N.002-N.004`）  
- C 列：果实获取方式  
- D 列：备注

**JSON 来源**：`~/claude/lkwj/data/tasks.json` 中 `type` 为 `"fruit"` 的任务

**核对所有家族**：
1. 果实进度表中每个编号范围内的精灵，在 tasks.json 中是否有 `type: "fruit"` 任务
2. 以下家族**不应有**果实任务（表格标注无果实）：
   - N.150-152（里奥家族）
   - N.293-295（小帕尔家族）
   - N.313-316（果冻家族）
   - N.317-319（星尘虫家族）
   - N.348-350（钨丝贝贝家族）

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

### 四、果实任务
- 应有果实的精灵总数：xxx
- 实际有 fruit 任务：xxx
- 缺失列表：
  - pet_xx（N.xxx）：应有果实但 tasks.json 中无 fruit 任务
  - ...
- 无果实精灵误填：有/无（列出误填的 pet_xx）
```
