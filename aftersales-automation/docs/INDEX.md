# 鲸灵售后处理规则索引（Agent 必读入口）

---

## §0 错误处理总则

### 0.1 错误分级

**可恢复错误**（retry 3次，仍失败则上报人工）：
- CDP 超时、页面加载慢、元素未出现
- ERP 页面渲染慢、搜索结果延迟

**不可恢复错误**（立即停止整个处理流程，上报人工）：
- 规则歧义：当前情况未被任何规则覆盖
- 数据矛盾：不同来源数据不一致且无法判断哪个正确
- 脚本抛错：getErpShop() 找不到映射（如澜泽店铺未建立）
- 次品：qtyBad > 0（主商品或赠品均触发）
- 任何"说不准"的情况

### 0.2 人工上报流程（满足任意一条触发）

触发条件：
- 主商品退货含次品（qtyBad > 0）
- 赠品退货含次品（qtyBad > 0）
- 退货数量与应退数量不符，且情况不明确
- 决策树未覆盖的新场景
- 任何"说不准"的情况

**上报步骤**（依次执行，不同意也不拒绝）：

```bash
# Step 1: 工单添加内部备注
node cli.js add-note <工单号> "【待人工】原因：<触发原因> 关键信息：<核心数据>"

# Step 2: 创建 Mac 提醒（5分钟后触发）
node cli.js remind <工单号> <账号名> "<具体问题描述>"

# Step 3: 停止对该工单一切后续操作
```

处理结束后汇总输出：
```
⚠️ 需人工处理（X张）
- [账号] 工单号 | 类型 | 剩余时间 | 原因
```

---

## §1 角色与红线

### 1.1 处理原则

- 严格串行：工单按顺序处理，不并行，不跳过
- 每步验证：操作后必须验证结果，失败则 retry
- 不自行决断：规则未覆盖的情况一律上报人工
- 证据留痕：每次拒绝退款必须上传物流截图

### 1.2 红线（绝对禁止）

- ❌ 遇到不确定情况自行猜测并操作（同意或拒绝）
- ❌ 因为"看起来应该同意"就直接同意
- ❌ 靠记忆推算商品明细（必须查商品对应表+档案V2）
- ❌ 靠商品名字判断商品是否一致（必须用规格商家编码对比）
- ❌ 赠品子订单号推算（主号+1），必须从 giftSubBizOrderDetailDTO.subBizOrderId 读取
- ❌ 并行操作（ERP 命令必须串行执行）
- ❌ 截图用于判断内容（截图只用于上传凭证）

### 1.3 处理前检查清单

```
□ 1. 读取工单列表，只处理倒计时 ≤ 2天（48小时）的工单
□ 2. 每条工单：先读详情 → 判断类型 → 按对应流程处理
□ 3. 涉及退货：去 ERP 售后工单新版验收，展开所有行
□ 4. 涉及套装/赠品：必须查商品对应表 + 商品档案V2，不靠记忆
□ 5. 最终操作（同意/拒绝）前再确认一次表单内容
```

---

## §2 工单类型路由表

读完工单详情后，根据售后类型加载对应子文档：

| 工单类型 | 判断条件 | 加载文档 |
|---------|---------|---------|
| 退货退款 | subBizType = 退货退款 | `docs/flow-5.1.md` |
| 仅退款（未发货） | ERP 状态：待审核/待打印 | `docs/flow-5.2.md` |
| 仅退款（已发货） | ERP 状态：卖家已发货 | `docs/flow-5.3.md` |
| 换货 | subBizType = 换货 | `docs/flow-5.4.md` |
| 需商品对应表/档案V2 | 涉及退货核验时 | `docs/erp-query.md` |
| ERP 技术问题 | 操作报错/页面异常 | `docs/ops-tech.md` |

> ⚠️ 仅退款时，必须先通过 ERP 搜索确认发货状态，再决定走 flow-5.2 还是 flow-5.3。

---

## §3 全局判断规则

### 3.1 工单优先级

倒计时字段（格式：`X天X小时X分后自动退款/流转至客服`）：
- **≤ 2天** → 处理；**> 2天** → 跳过

⚠️ 快捷筛选器数字不实时，必须看每条工单的倒计时字段。

### 3.2 账号→ERP 店铺名映射

由脚本 `lib/erp/shop-map.js` 的 `getErpShop(note)` 自动处理，无需手动查表。
- 澜泽账号：ERP 店铺未建立，`getErpShop()` 抛错 → 上报人工
- 账号11「曼玲-悦希」→ 对应 ERP「曼玲」（「悦希」是品牌名非店铺名）

### 3.3 ERP 订单状态含义

| ERP 状态 | 含义 |
|---------|------|
| 待审核 | 未发货 |
| 待打印快递单 | 未发货 |
| 待发货 | 打包中，人工确认 |
| 卖家已发货 | 已发货 |
| 交易成功 | 已完成 |

### 3.4 afterSaleNum 计算规则

- 应退主商品单品数 = 档案V2.subItemNum × afterSaleNum
- afterSaleNum=1 → 退1件套装（正常）
- afterSaleNum=2 → 退2件套装（如4盒套×2=应退8盒）
- **赠品数量始终1份，不随 afterSaleNum 倍增**

### 3.5 退回成功判断（满足任意一条）

- 物流显示"签收，收件人：退商家"
- 物流显示"退回"节点
- 物流显示"安排退回，退回原因：客户要求退回"
- 物流显示"拒收"节点

> 不需要等仓库实际签收，有退回记录即算退回。

---

## §4 通用操作规范

### 4.1 同意退款三步（通用）

```
1. 鲸灵工单详情页 → 点「同意退款」
2. 弹出确认弹窗 → 点「确认同意退款」
3. 若出现第三层风险提示弹窗（已发货时必现）：
   内容："若您的货物已经发出，且订单无法拦截..."
   → 点「确 认」（按钮文字含空格，必须精确匹配）
```

> ✅ cli.js approve 命令已自动处理三步（含第三层弹窗）

### 4.2 操作命令速查

```bash
# 读工单列表（≤48小时）
node cli.js list

# 读工单详情
node cli.js read-ticket <工单号>

# 同意退款（自动处理三步弹窗）
node cli.js approve <工单号>

# 拒绝退款
node cli.js reject <工单号> <原因> <详情> [图片URL]

# 添加内部备注
node cli.js add-note <工单号> "备注内容"

# 创建 Mac 提醒（5分钟后触发）
node cli.js remind <工单号> <账号名> "原因"

# 读物流信息
node cli.js logistics <工单号>

# ERP 商品对应表查询
node cli.js product-match <货号> <attr1> <ERP店铺名>

# ERP 商品档案V2查询
node cli.js product-archive <规格编码>

# ERP 订单搜索
node cli.js erp-search <子订单号>

# ERP 售后工单搜索（退货快递单号）
node cli.js erp-aftersale <快递单号>
```

### 4.3 内部备注格式规范

- 格式：**结论+动作，一句话，不写原因分析**
- 人工上报格式：`【待人工】原因：<触发原因> 关键信息：<核心数据>`
- ⚠️ 备注写 ERP shortTitle（如"KGOS保温壶1个"），不写编码（如 kgosbwh）

### 4.4 截图使用规范

**只在以下情况截图**：
- 拒绝退款时上传物流截图作为凭证
- 遇到从未见过的页面布局

**所有判断全部用 DOM 文字读取**，不截图判断。

---

## §5 已知人工处理触发案例

| 触发场景 | 首次案例 |
|---------|---------|
| 赠品退货含次品 | 工单100001775368135929803（酵素体验装qtyBad=1） |
| 换货商品不符 | 工单（KGOS保温壶 vs 灵芝金花黑茶） |
| 多发货套数 > 申请套数 | 工单100001775617216291882（发2套申请1套） |
| 澜泽账号（ERP未建立） | getErpShop() 抛错触发 |

---

## §6 已知坑位（通用操作层）

> 格式：`[触发次数/最后触发]` — 说明。触发次数≥3且超过2周未触发可清理。

- `[∞/永久保留]` **#5 赠品子订单号禁止推算**：赠品子订单号禁止用主号+1推算，必须从 `giftSubBizOrderDetailDTO.subBizOrderId` 读取
- `[∞/永久保留]` **#9 图片上传唯一路径**：curl+cookie 上传 → 注入 Vue 组件 `WorkOrderStateForm`；禁止 DataTransfer / 本地HTTP / XHR拦截器（拦截器会导致堆栈溢出无法恢复）
- `[∞/永久保留]` **#24 备注写 shortTitle 不写编码**：备注必须写 ERP shortTitle（如"KGOS保温壶1个"），禁止写编码（如 kgosbwh），人工处理者不知道编码含义
- `[∞/永久保留]` **#25 备注只写结论**：备注只写结论和动作，一句话，不写原因分析
- `[∞/永久保留]` **#37 内部备注入口**：必须用「致内部」按钮；严禁点「+新增备注」（会进入供应商可见的订单备注区域）
- `[1/2026-04]` **approve/reject 必须验证按钮消失**：操作完成后 eval 确认「同意退款」/「拒绝退款」按钮已从页面消失才算成功。返回 rejected:true 不等于按钮消失。
- `[1/2026-04]` **El-Select 展开必须用 cdp.clickAt**：展开 El-Select 下拉必须用 `cdp.clickAt(targetId, 'input.el-input__inner[placeholder="请选择"]')`；JS `.click()` 只触发 click 不触发 mousedown，下拉不展开（静默失败）。同类：El-DatePicker 等所有弹出组件均用 cdp.clickAt。
- `[1/2026-04]` **ERP 表格 el-input-number 值读 input.value**：ERP 表格明细行中凡是 el-input-number 列（如数量良品/次品），innerText 始终为空，必须用 `td.querySelector('input').value` 读值。
- `[1/2026-04]` **ERP 弹窗关闭按钮类名不统一**：档案V2「子商品信息」弹窗是 `button.el-dialog__closeBtn`，不是标准 `button.el-dialog__headerbtn`。检测弹窗存在用 wrapper 可见性，关闭时两个选择器都试。
- `[1/2026-04]` **jl-server 重启后等 pipeline 空闲**：重启后服务自动处理 queue.json pending 工单，此时浏览器被占用。任何浏览器操作前必须轮询 `GET /api/op-queue` 确认 running 为 null。
- `[1/2026-04]` **批量操作必须完整传 source 参数**：调 archive-manual 接口时，auto_executed 工单必须传 `source: 'auto_executed'`，漏传 fallback 为 manual_handled，历史页全部显示错误来源。
- `[1/2026-04]` **batch-execute 扫全量历史禁止误用**：`POST /api/simulations/batch-execute` 扫整个 simulations.jsonl（含历史归档），会触发数百条入队。处理当前工单用 `POST /api/queue/:id/reprocess`。
- `[1/2026-04]` **检查脚本语法禁用 node -e require()**：`node -e "require('./scan-all')"` 会执行脚本顶层代码（触发全量扫描）。语法检查用 `node --check <file>`。
- `[1/2026-04]` **退货快递单多次使用有两条独立路径**：① read-ticket.js 正则抓工单号时包含当前工单号自身 → 过滤 workOrderNum 本身；② pipeline.js 交叉比对时未排除同工单历史 sim → 加 `s.workOrderNum === workOrderNum` 过滤。两处都要检查。
- `[1/2026-04]` **ERP 密码框点击触发自动填充**：ERP 完全退出到登录页，Chrome 密码自动填充需 `cdp.clickAt(targetId, 'input[type="password"]')` 触发；点账号框无效。实现见 `lib/erp/navigate.js` 场景B。
- `[1/2026-04]` **LaunchAgent 后台禁用 Reminders.app**：后台进程发提醒必须用 `display notification`，不能 osascript 操作 Reminders.app（AppleEvent 超时 -1712）。
- `[1/2026-04]` **测试框架触发时机**：修改 lib/ 任意文件、CLI 步骤连续出错 ≥2 次、新增 CLI 命令时，必须跑 `node test.js`。框架建立后若不主动触发等于白建。
- `[1/2026-04]` **工单列表类型识别串位**：`list.js` 扫描窗口 `winStart = positions[t-1].idx + 1` 覆盖上一条详情行，导致类型串位。修复：`winStart = Math.max(positions[t-1].idx + 1, center - 3)`。
- `[∞/永久保留]` **#48 读表数据用表头定位列索引，禁数据特征过滤**：`<th>` 表头文本定位列索引（"商品名称"/"商家编码"/"组合比例"），直接读。禁止用正则/关键词/长度过滤数据内容——这会把合法非数字编码（kgoxnld等）当垃圾误杀。参见 `tasks/lessons.md §48`。
- `[∞/永久保留]` **#49 验证数据=读实时源头，不分析旧采集**：判断数据是否正确→从 ERP 页面/CLI 命令重新读取，不分析 simulations.jsonl 过期数据。验证单一环节用 CLI 直调，不走 pipeline。
- `[1/2026-05]` **#50 后台 osascript Reminders 需降级**：无 TTY 后台进程 osascript Reminders AppleEvent -1712。用 `createReminder()` 优先 Reminders 失败降级 `display notification`。
- `[∞/永久保留]` **#51 ERP 状态只路由不决策**：仅退款中 ERP 订单状态唯一作用是区分未发货（flow-5.2）vs 已发货（flow-5.3）。决策依据是物流数据。"交易关闭"只说明订单关了，不说明包裹已退回。必须加入 SHIPPED 常量让其走物流判断，禁止"看到状态X→直接决策Y"。
- `[∞/永久保留]` **#52 采集按工单类型分流**：product-match/archive 唯一消费者是退货退款的逐商品核对（flow-5.1 Step4）。仅退款/换货不需要，应跳过。反之，退货退款必须遍历所有子订单做 product-match（不能只取 subOrders[0]）。
- `[∞/永久保留]` **#53 决策只看"剩余-扫描"安全边际，不看累计等待**：累计等待时间无意义。唯一决策依据：剩余时效 - 下次扫描间隔 > 8h → 安全等待；≤ 8h → 立即拒绝防止超时自动退款。SAFETY_MARGIN_HOURS=8 常量化在 constants.js。2026-05-03 彻底移除 getWaitingHours。2026-05-03 晚追加8h安全边际。
- `[∞/永久保留]` **#54 推理文案说人话**：escalate reason 三要素：①第一句说清根因（非表象）②无代码变量名（afterSaleNum等）③给明确建议动作。格式："对应表查无此规格：XX×N件，请确认是否为赠品"。禁止"商品档案不完整…afterSaleNum=N"。
- `[∞/永久保留]` **#55 queue item 校验账号店铺匹配**：`POST /api/queue` 必须交叉校验 accountNum 和 accountNote 的对应关系（查 accounts.json）。账号编号和店铺名不一致时拒绝，防止注入错误session导致跨商家权限拒绝[cbe]。
- `[1/2026-05]` **#56 CLOSE_ALL_DIALOGS_JS 全量关闭**：原来只关 `.trade-detail-dialog` 漏了档案V2子品弹窗等。改为 `querySelectorAll('.el-dialog__wrapper')` 过滤 `getComputedStyle(e).display !== 'none'`。navigateErp 切页面前 + product-archive 启动时都加清理。
- `[1/2026-05]` **#57 洞察生成防并发+分批**：`POST /api/insights/generate` 无限流→并发重复生成。加 in-memory lock（冲突返回409）+ MAX_BATCH=30（差评优先）+ sim为null时skip不阻塞整批。
- `[∞/永久保留]` **#58 collect.js 重试上限**：collect.js 失败（含 exit code null/SIGTERM 杀进程）最多重试 3 次。pipeline.js processOne 维护 `collectRetries` 计数器：成功进入 inferring 时清零，失败累加，≥3 次标记 `simulated` 上报人工。防止采集死循环。op-queue.js 的 execCollect 路径暂不计数（独立 code path）。
- `[∞/永久保留]` **#59 spawn timeout 180s 双路径对齐**：pipeline.js 和 op-queue.js 各有一条 spawn collect.js 路径，两条都设 `timeout: 180000`（3分钟）。含赠品的退货退款工单采集步骤多（两次 product-match+archive），120s 不够易触发 SIGTERM → exit code=null → 被 #58 重试。改超时必须双路径同步。
- `[1/2026-05]` **#60 querySelector 返回隐藏元素导致假阴性**：`document.querySelector` 返回 DOM 序第一个匹配元素，不保证可见。ERP 页面常有同 placeholder 的隐藏 input（0×0），读到它会导致 Vue 父链遍历找 dataList 失败（错误返回"dataList 为空"但数据实际在页面上）。修复：与其他函数一致，用 `querySelectorAll` + `getBoundingClientRect().width>0 && height>0` 过滤后再取第一个。案例：2026-05-04 archive.js READ_DATALIST_JS 选中隐藏"主商家编码"input 而非可见的搜索结果输入框，导致 product-archive 假阴性 → escalate 而非 approve。
- `[1/2026-05]` **#61 DOM 移除 Element UI 弹窗破坏 Vue dialogVisible 状态**：`el.parentNode.removeChild(el)` 移除 `.el-dialog__wrapper` 后 Vue 内部 `dialogVisible` 仍为 true。下次 `a.ml_15` 点击时 Vue 认为弹窗已打开 → 跳过打开 → READ_SUB_ITEMS_JS 报"子商品弹窗未打开" → subItems 空数组 → escalate。必须用 `btn.click()` 触发 Vue close 流程，关闭后轮询等待弹窗 `display:none`（max 2s）。案例：2026-05-04 第一个工单正常，后续全部 subItems 空——CLOSE_SUB_DIALOG_JS 的 DOM 移除破坏了 Vue 状态。
- `[∞/永久保留]` **#62 Chrome 自动填充非确定性——单次触发，不可重试**：Chrome 密码管理器在同一页面生命周期内只自动填充一次（macOS sleep / Chrome 长时间运行后尤为明显）。`recoverLogin` 必须单次尝试自动填充，失败则进凭据注入（Phase 2），不能循环 reload 再试。循环 reload 会清掉已填密码且不会触发第二次自动填充。根因：5 轮修复方案均绕不开该单点，唯一解是确定性凭据注入。
- `[∞/永久保留]` **#63 ERP 熔断行为——熔断中不要在调用侧包 retry**：`erp-circuit-breaker.json` state=open 时，`erpNav()` 直接返回熔断错误；15 分钟冷却后 half_open 允许一次探测。上层代码不得在调用 erpNav/erpSearch 等时另包 retry 循环——本地 retry 会绕过全局熔断保护，在 session 耗尽时仍无限重试。
- `[∞/永久保留]` **#64 erp-health.json 读合并写，不能整体覆盖**：`updateErpHealth()` 必须读现有 JSON → merge → 写回，防止多调用点覆盖丢字段（status/lastOkTime/consecutiveAuthFail 由不同代码路径写入）。直接 `JSON.stringify(updates)` 写入会覆盖其他字段，导致 lastAlertTime 丢失 → 告警重复间隔失效。
