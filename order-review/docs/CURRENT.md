# 当前状态与接手入口

更新时间：2026-09-13

未标绝对路径的代码路径相对项目根目录。本文只维护当前状态。业务规则见[规则索引](rules/README.md)，操作命令见[使用指南](usage.md)，完整待办见[任务清单](../tasks/todo.md)。

## 装箱实验当前阶段

- 装箱实验页面、只读服务层、HTTP入口和静态前端已迁回主干；固定本地地址为 `http://127.0.0.1:3466/`。服务只允许绑定回环地址，不连接 ERP/CDP，不写正式案例。
- 页面保留“装箱实验 / 包装资料”两个入口。KGOS 当前开放单箱实验；悦希当前只展示资料，不自动开放装箱计算。手动指定纸箱失败时不能偷偷换箱；自动模式当前只在同品牌普通候选纸箱中找可行单箱。
- 产品原箱只在当前实际占空间商品为单一品种、原箱允许该商品、数量落在已确认范围且原箱尺寸已知时进入手动下拉框；缺尺寸原箱只在资料页展示。
- 历史订单只读正式案例库并折叠到同订单最新有效版本。人工保存的原方案只在算法完成后作为只读对照，不给求解器提示答案，也不改写 `cases.json`。
- 页面与正式浮窗仍保持运行隔离；正式审单浮窗尚未接入装箱实验服务。

## 商品身份与装箱资料边界

- `product-mapping` 的视觉资料不作为装箱身份键。模拟器读取 `product-mapping/data/products/*/features.json` 时只取条目中的 ERP 标准全名 `erpName`，不读取顶层识图名称、颜色、特征、别名或活动 `sku-records`。
- `product-mapping/data/products/erp-identities.json` 是 2026-09-11 的 200 条 ERP 商品档案只读时间点快照，只用于补正式简称、主商家编码和少量规格商家编码；它不是在售目录，也不能影响商品匹配原有 check/match/识图逻辑。
- 商品装箱尺寸已从 `data/packing-dimensions.json` 拆到 `data/packing-product-dimensions.json`。前者继续保存纸箱、原箱、固定规则、待补和证据；后者只保存商品尺寸、零体积配件和仓库装箱排除项。
- `packing-product-dimensions.json` 只按 ERP 标准全名与商家编码关联，不再使用商品匹配视觉 `productKey`。前端技术 `productKey` 仅作为 opaque 行标识，当前格式为 `brandId::ERP标准全名`，不会解析视觉名称。
- 黑茶茉莉花茶味说明卡片 `hcmlhckp` 与悦希雪梨纸 `6976299500122` 只在装箱侧记录为零体积配件；不要求进入商品匹配视觉目录。KGOS体脂秤 `kgostzc` 为仓库发货装箱排除项。
- 两款新版7条装咖啡的标准 ERP 名称和编码已确认，商品匹配项目只在 `tasks/todo.md` 记录“缺图片/识图特征”，不提前写入 `features.json`。装箱侧继续从 `packing-dimensions.json` 的待补资料知道这两款商品，尺寸未提供前不得进入几何计算。
- 悦希6个新品的标准名称、编码和视觉待办也统一记录在 `product-mapping/tasks/todo.md`；其中焕颜乳2.0 商家编码确认使用 `6940079096228-1`。商品匹配不再维护独立 pending 商品数据文件；本轮不修改 `features.json`、`data/sku-records.json` 或活动图片资料。
- 旧版糖果已确认删除；当前只保留糖果2.0，商家编码 `6976299500108`。不得为兼容旧资料重新引入“旧版糖果”事实。

## 算法当前状态

- 最新架构与理论来源统一见[2026-09-12装箱算法研究](2026-09-12-packing-algorithm-research.md)：完整结构为 `1～N箱外层 + 单箱几何内核`，单箱只是 `N=1` 特例。
- 当前单箱内核已完成第一阶段物件顺序搜索：保留严格 verifier，增加少量确定性排序、等价类/旋转去重和共享 deadline，并用“薄礼袋先铺底”反例闭环。
- 现有候选点与支撑模型仍需后续处理。完整底面支撑不能作为普遍几何硬条件；几何可行性、运输稳定性和摆放偏好必须分层。UNKNOWN 继续不得解释为装不下。
- 后续按算法研究和 `tasks/todo.md` 继续：候选点层/Extreme Point、完整 `pack_order()` 1～N箱外层、历史盲测。历史人工拆法和固定容量答案不得进入求解输入。

## 当前验证状态

- 主干已通过装箱模拟器、HTTP、尺寸目录和装箱算法专项回归：58项全部通过。
- 主干完整 `order-review` 回归在本轮服务迁移后为316项全部通过。
- 200条 ERP 身份快照已与 worktree 原文件做全量 JSON 语义比较，200/200 内容一致。
- `kgos/features.json`、`hee/features.json`、`product-mapping/data/sku-records.json` 本轮没有被修改。

## Worktree 收口与页面接手边界

- 历史 worktree `order-review-packing-simulator` 的 P1 文件已逐项对账：应保留内容已迁回或按当前规则重建；视觉 `productKey`、KGOS/HEE `pending-products` 等已确认错误设计不再迁入。后续开发不得再从 worktree 回抄业务数据或规则。
- 固定 3466 服务已停止旧 worktree 进程并从 main 重新启动；实际进程工作目录已核对为 `/Users/chat/claude/order-review`，`/api/catalog` 的 `dimensionCatalogPath` 指向 main 的 `data/packing-dimensions.json`，算法版本为 `single-carton-order-search-v2`。
- 当前主干 API 冒烟：2 个品牌、商品目录82条、尺寸商品19条、运输纸箱16种、待补16项、待补纸箱2种、产品原箱6种。旧 worktree 的83条目录不再作为数量目标；少1条属于纠正临时/视觉待补体系后的预期差异。
- 下一步是用户直接实测 main 页面；实测前不做无证据的前端重构。页面通过后可删除本地旧 worktree；远端旧分支只保留历史备份，不再作为开发入口。
