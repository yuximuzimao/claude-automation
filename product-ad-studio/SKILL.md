# 商品宣传图工作台 SKILL.md

## DO FIRST
1. 读 `tasks/todo.md` — 确认当前阶段与未完成事项。
2. 读 `docs/INDEX.md` — 需求拆解、素材管理、制作与修改规则的权威入口。
3. 读目标品牌的 `data/brands/<brand>/brand-profile.json` 与 `asset-catalog.json`。
4. 处理具体任务时，读 `jobs/<job-id>/brief/` 和 `jobs/<job-id>/revisions.jsonl`。
5. 核心入口：`python3 cli.py --help`。

## ENTRY MAP
| 文件 | 用途 | 何时读 |
| --- | --- | --- |
| `cli.py` | 素材导入、Excel Demo 解析、任务创建、校验 | 执行本地操作时 |
| `lib/assets.py` | 图片指纹、去重、目录归档、素材登记 | 导入或查重时 |
| `lib/demo.py` | Excel 文案、合并单元格和相对布局提取 | 收到原始 Demo 时 |
| `lib/jobs.py` | 创建任务包和默认设计状态 | 新单开始时 |
| `docs/INDEX.md` | 全部工作原则、边界和失败模式 | 每次进入项目 |
| `schemas/` | 素材、设计意图、修改指令的数据约束 | 新增字段或集成时 |
| `data/brands/` | 品牌长期资产与已确认经验 | 分析品牌和历史素材时 |
| `jobs/` | 每次设计任务的输入、brief、过程和输出 | 制作或修改具体图片时 |

## CORE FLOWS

### 新品牌首次接入
1. 把原始产品图、Logo、品牌资料放入本地临时目录。
2. 使用 `cli.py import-assets` 导入；完全重复文件只登记来源别名，不保存第二份。
3. GPT 查看需要理解的图片，输出简短人话对齐说明和结构化品牌资料。
4. 将确认后的长期规则写入品牌目录；不得只留在聊天记录中。

### 新设计任务
1. 创建任务目录：`cli.py new-job`。
2. 导入 Demo Excel：`cli.py parse-demo`，文字以 Excel 为真值，截图仅辅助理解布局。
3. GPT 结合 Demo、产品资产、参考图和用户短要求，输出：
   - `human-alignment.md`：设计师可快速判断的简洁复述；
   - `design-intent.json`：机器执行规格；
   - `render-plan.json`：本次分层制作方案。
4. 生成或编辑图片时，产品真实性、准确文字和已声明不变量优先于风格接近。
5. 每轮只改明确指出的问题，并把“改什么 / 什么保持不变”追加到 `revisions.jsonl`。

### 历史素材复用
1. 先按素材 ID、别名、品牌和标签查 `asset-catalog.json`。
2. 已有可靠描述和指纹时，不要求用户重新解释素材身份。
3. 涉及新的构图判断、局部问题或结果质检时，仍需重新查看当前图像；历史描述不能替代对当前输出的检查。

## NON-NEGOTIABLES
- 默认画布：未指定时使用 `1080 × 1920`，9:16 竖版。
- Demo 的单元格位置通常表示信息层级和大致关系，不等于最终绝对坐标。
- 所有宣传文字必须确定性保存和渲染，不允许生成乱码、错字、漏字或数字错误。
- 产品轮廓、比例、SKU 相对大小、Logo 和标志性特征必须保持真实。
- 产品允许缩放、移动、轻微旋转、前后交错和适度遮挡；通常避免透视，遮挡不得覆盖 Logo 或标志性特征。
- 参考图只提取布局、色调、光影、材质和气质；不得复制水印、账号、他牌 Logo、他牌产品或原文案。
- 图片生成/编辑只能在用户明确要求制作或修改图片时触发。分析、归档、拆解、建项目不得触发生图。
- 原始资产不覆盖；所有输出使用版本号。

## FAILURE PATTERNS
- 把 Demo 当严格线框稿，导致产品与文字互相挤压。
- 让生图模型重绘完整包装，造成瓶型、Logo、包装文字漂移。
- 每轮修改未声明不变量，导致构图和已确认内容一起变化。
- 只保存聊天总结，不保存本地结构化资料，换账号或换电脑后无法恢复。
- 仅按文件名判断重复，忽略同图不同名称；或仅按感知哈希删除近似但实际不同的素材。
- 在用户仅要求分析时错误调用生图工具。

## PATHS
- 品牌资产：`data/brands/<brand>/assets/`
- 品牌素材目录：`data/brands/<brand>/asset-catalog.json`
- 品牌规则：`data/brands/<brand>/brand-profile.json`
- 历史案例：`data/brands/<brand>/cases/`
- 案例图片索引：`data/brands/<brand>/cases/<case-id>/visual-index.json`
- 任务：`jobs/<job-id>/`
- Schema：`schemas/`
- 当前待办：`tasks/todo.md`
- 稳定规则：`docs/INDEX.md`
