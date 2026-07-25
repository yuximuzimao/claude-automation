---
name: product-mapping
description: 快麦商品对应表匹配——ERP档案V2查询、7步闭环SKU匹配、视觉识图、套件标注。CDP 通过 HTTP proxy 操作快麦ERP。
skill_dir: product-mapping
entry: cli.js
---

## DO FIRST

1. **找 CLI 命令** → `cli.js`（19 个命令，JSON 输出）
2. **找流程** → `docs/INDEX.md §2`（5 步核查流程：check→识图→match→check→verify-table）
3. **找单 SKU 匹配** → `lib/match-one.js`（7 步闭环，支持 `--from` 断点续跑）
4. **ERP 操作前必走完整导航** → `lib/navigate.js`（reload→登录检测→切tab→验hash→等Vue mount）
5. **写操作（新增匹配）必须人工确认后执行**
6. **新品牌建档前必读** → `docs/preflight-brand.md`（checklist 门禁） + `docs/brand-onboarding.md`（SOP 完整流程）；`docs/INDEX.md §7` 只保留入口原则
7. **ChatGPT 通过 CodexPro 操作时必读** → `docs/chatgpt-codexpro-operations.md`（本地图片桥接、前台时间边界、target 刷新、长任务交给本地 Codex）

## ENTRY MAP

| 文件 | 作用 | 何时读 |
|------|------|--------|
| `cli.js` | CLI 入口，19 个命令路由 | 了解可用命令或新增命令时 |
| `lib/check.js` | 完整核查流程编排（扫描+标记+生成结构化比较事实） | 改核查流程时 |
| `lib/brand-scope.js` | 首次指定品牌、后续继承与冲突拦截 | 改品牌作用域时 |
| `lib/compare.js` | 识图结果 vs ERP 档案明细的精确比较 | 改 match/mismatch 判定时 |
| `lib/match-one.js` | 单货号 7 步闭环编排器 | 改匹配流程/加步骤时 |
| `lib/match.js` | 批量匹配入口 | 批量匹配时 |
| `lib/cdp.js` | CDP HTTP proxy 客户端（localhost:3456），fallback 直连 | 写浏览器操作时 |
| `lib/targets.js` | 查找 ERP 浏览器 tab ID（优先 pinned，失效时按 URL 回退） | 需要定位 ERP 标签时 |
| `lib/navigate.js` | ERP 页面导航（reload→登录→切tab） | ERP 页面跳转时 |
| `lib/erp-lock.js` | ERP 操作锁（acquireErpLock/releaseErpLock）暂停 aftersales | 任何 ERP 操作（navigateErp 自动调用） |
| `lib/correspondence.js` | 商品对应表读取（`readCorrWithoutDownload`=纯读取；`readAllCorrespondence`=含下载副作用） | 查对应表数据时 |
| `lib/archive.js` | 商品档案V2查询 | 查档案数据时 |
| `lib/visual.js` | 视觉识别结论管理 | 查/写识图结果时 |
| `lib/preview-match.js` | 匹配前最终明细核对 HTML（AI 识图商品 + 自动注入配件同表展示，配件变色） | 识图完成后、match 前生成核对表时 |
| `lib/verify-table.js` | 图片+ERP明细诊断表 HTML 生成 | 最终自动核对出现异常、需要人工定位时 |
| `lib/jl-products.js` | 鲸灵活动商品列表抓取 | 获取商品清单时 |
| `lib/jl-sku-detail.js` | 鲸灵 SKU 详情读取 | 查单个 SKU 时 |
| `lib/auto-match.js` | 自动批量匹配 v1 | —（历史版本） |
| `lib/auto-match2.js` | 自动批量匹配 v2 | 批量自动匹配时 |
| `lib/doubao.js` | 豆包 AI 集成 | AI 辅助匹配时 |
| `lib/copy-as-suite.js` | 复制为套件 | — |
| `lib/mark-suite.js` | 对应表标记套件 | 标记 SKU 为套件时 |
| `lib/remap-sku.js` | SKU 重映射 | — |
| `lib/fetch-archive-names.js` | 档案V2 全量名称抓取 | 需要全量名称列表时 |
| `lib/result.js` | `ok()/fail()` JSON 封包 | 新增 CLI 命令时 |
| `lib/wait.js` | `sleep()`, `waitFor()` 工具 | 需要等待/重试时 |
| `lib/utils/safe-write.js` | 原子文件写入（tmp/rename） | 写数据文件时 |
| `lib/ops/ensure-corr-page.js` | 确保对应表页面就绪 | 操作对应表前 |
| `lib/ops/download-products.js` | 从 ERP 下载平台商品列表 | check 流程 step 1.2 |
| `lib/ops/read-skus.js` | 读对应表 SKU 列表 | check 流程 step 1.3 |
| `lib/ops/read-table-rows.js` | 通用表格 DOM 读取（th 表头定位） | 读任何 ERP 表格时 |
| `lib/ops/annotate.js` | 标注 SKU 类型（单品/套件） | match 流程 step annotate |
| `lib/ops/create-suite.js` | 对应表创建套件 | match 流程 step match |
| `lib/ops/remap-single.js` | 单品 SKU 重映射 | match 流程 step match |
| `lib/ops/read-erp-codes.js` | 重新读 ERP 编码验证 | match 流程 step read_erp |
| `docs/matching-stability.md` | 套件状态机、故障优先级、断点恢复与回归用例 | 自动匹配或排障时 |
| `docs/chatgpt-codexpro-operations.md` | ChatGPT + CodexPro 专属运行边界与图片桥接 | 通过 CodexPro 连接本地工作区时 |

## CORE FLOWS

### 核查主流程（`docs/INDEX.md §2`）

```
① check --shop <店铺> --brand <品牌> → 扫描+标记+下载图片+生成报告 (anchor: runCheck, listActiveProducts, readAllCorrespondence)
② AI 识图（当前具备视觉能力的对话模型） → visual-ok / visual-flag 记录结论 (anchor: recordVerdict, listPending)
②.3 check --reuse-active --skip-download → 同一 check 输出；AI 核对已匹配 SKU，未匹配视为正常待处理
②.5 preview-match          → 全部 SKU 展示最终匹配明细（AI 识图 + 自动配件同表，配件变色），由用户确认一次 (anchor: main in preview-match.js)
③ match --shop <店铺>      → 自动匹配（套件+单品，异常停止） (anchor: matchOne, matchSku)
④ check --shop <店铺> --reuse-active --skip-download → 最终自动对比 (anchor: runCheck)
```

- 平台商品已经更新且活动范围/识图已人工确认时，匹配后使用
  `check --shop <店铺> --reuse-active --skip-download`：复用上一份 check 报告与
  `sku-records.json` 交叉验证后的活动范围，只读 ERP 对应表，不重复下载平台商品
- 识图必须覆盖本次报告全部 SKU；`verify-table` 出现「无识图数据」表示流程未完成
- 比对结果必须由脚本精确输出：空识图但 ERP 有明细 = mismatch，有识图但 ERP 无可比明细 = mismatch
- 档案V2 主商家编码查不到时，先回退「规格商家编码」查询；不能直接判定档案缺失
- 品牌必须在首次 check 明确传入，并存入报告和每条 sku-record；后续流程自动继承，缺失/冲突即停止
- 匹配前 check 的门禁：`matchedComparisonMatch == matchedSkuCount` 且 `matchedComparisonMismatch == 0`；`unmatchedAwaitingMatch` 可大于 0
- 完成门禁：`recognitionDone == comparisonMatch == SKU总数`，且 mismatch/pending/pendingVisualReview 全为 0

### 7 步闭环（`lib/match-one.js`，单 SKU）

```
download → read_skus → recognize → annotate → match → read_erp → verify
(anchor: downloadProducts, readSkus, annotate, remapSingle, createSuite, readErpCodes, verifyArchive)
```

- `recognize` 步骤由当前具备视觉能力的对话模型执行 AI 识图，脚本到此暂停（**只识图片可见商品，不识配件**）；ChatGPT + CodexPro 模式按 `docs/chatgpt-codexpro-operations.md` 桥接本地图片
- `annotate` 步骤自动注入不可见配件（读 `data/products/{brand}/accessories.json`）
- 支持 `--from annotate` 从中间步骤续跑；`--brand <品牌>` 必须明确指定，断点续跑时与记录品牌不一致会停止
- `stage` 状态机：`skus_read → images_done → annotated → matched → verified`
- KGOS 真实 SKU 主图语料在微信文件目录 `.../2026-05/1主图汇总`；用于 product-detect 黄金验证集建设，不提交 Git，不与 HEE 历史 `data/imgs/` 混用

### 档案V2 查询流程

1. `navigateErp` → 商品档案V2（必须 reload→登录检测→切tab）
2. DOM 输入法设编码（非 `window.__sv` 直接赋值）
3. 点搜索 → 等结果 → 读子品明细（cells[1/3/10]）
4. 关闭弹窗用 `button.el-dialog__closeBtn`

## NON-STANDARD PATTERNS

### CDP 操作范式（HTTP proxy 模式）

```js
// product-mapping 的 CDP 走 HTTP proxy（localhost:3456），非直接 WebSocket
// proxy 模式下：eval/clickAt/navigate 都通过 HTTP 请求代理执行
// fallback 直连模式同样可用，通过 healthCheck() 自动检测
const result = await cdp.eval(targetId, `document.title`);
await cdp.clickAt(targetId, 'button.el-button--primary');
```

**关键差异**：此项目的 cdp.js 是 HTTP 客户端，aftersales-automation 的是 WebSocket 直连。两者导出相同接口但实现完全不同。不要混用。

### 档案V2 查询（DOM 输入法）

```js
// ❌ 错误：直接赋值不触发 Vue 响应
window.__sv.searchData.outerId = code;

// ✅ 正确：DOM 输入 + dispatch 事件
const input = document.querySelector('input[placeholder="主商家编码"]');
input.value = code;
input.dispatchEvent(new Event('input', { bubbles: true }));
input.dispatchEvent(new Event('change', { bubbles: true }));
// 向上遍历找有 handleQuery 的 Vue 组件
let vm = input.__vue__;
for (let i = 0; i < 12 && vm && !vm.handleQuery; i++) vm = vm.$parent;
vm.handleQuery();
```

### 对应表操作规则

- **搜索框** (`el-input-popup-editor input`)：当前 ERP 实测按 productCode（货号）搜索有效；2026-05-27 的 platformCode 旧结论已失效。再次 0 行时先做同页 A/B 探针
- **展开目标行**：用 `tds[6].innerText`（值=productCode）精确匹配后展开
- **定位目标 SKU**：展开后用子行 `tds[5].innerText` 精确匹配 platformCode
- **套件标记**：每次只处理一个 SKU，严禁批量勾选整个货号所有子行
- **图片列 class** 动态变化，逐段滚动（12 步）触发懒加载

### 多层 Dialog 确定按钮

```js
// 遍历所有 footer，找可见的那个
const footers = document.querySelectorAll('.el-dialog__footer');
const visible = Array.from(footers).find(f => f.getBoundingClientRect().height > 0);
visible.querySelector('button.el-button--primary').click();
// 禁止用 innerText 文字匹配（有的按钮是"确 定"带空格）
```

## FAILURE PATTERNS

| # | 错误 | 正确做法 |
|---|------|---------|
| 1 | ERP 操作前跳过 reload | 必须走完整 `navigateErp()`（reload→登录→切tab→验hash→等mount） |
| 2 | 档案V2 直接赋值 `window.__sv.searchData` | 必须 DOM 输入法 + dispatch input/change 事件 |
| 3 | 沿用旧文档，按 platformCode 搜对应表 | 当前 ERP 返回 0 行；按 productCode 搜索并用 `tds[6]` 精确展开，字段行为变化时先 A/B 实测 |
| 4 | 多层弹窗取第一个 footer | 必须遍历 `querySelectorAll` 找 `getBoundingClientRect().height > 0` 的 |
| 5 | 翻页用按钮状态判断结束 | 必须用"共X条"总数推算总页数 |
| 6 | 档案V2 查询前未清筛选残留 | 每次档案操作前检查/清空筛选状态 |
| 7 | 识图不看 features.json 颜色字段 | 颜色规则优先级高于图片文字标注 |
| 8 | 搜索结果只看数量或首行 | 多结果时必须找到某个 td 与完整 ERP 商品名精确相等；无精确行才报错，不能把合法的子串多结果误判为歧义 |
| 9 | 只识别未匹配 SKU | 全量识图，已匹配 SKU 也必须有 recognition 才能核对 |
| 10 | recognition 为空但 ERP 有明细时归入 pending | 必须输出 mismatch，不能让 AI 人工兜底替代脚本比较 |
| 11 | 主商家编码查不到就判定无明细 | 先按规格商家编码回退查询商品档案V2 |
| 12 | 用户已手动打开列表时仍自动开页/注入账号 | 只读当前页面；自动开页/注入登录态前必须先处理 targetId 绑定边界 |
| 13 | 只清 DOM checkbox 就认为弹窗已归零 | 同时清 `TableItem.multipleSelection`，并验证“已选择商品：0” |
| 14 | 中断后从头重复标记套件 | 先识别“复制为套件”中间态，已有则直接续配置子品 |
| 15 | 未指定品牌时静默使用 kgos/hee | 首次 check 必须 `--brand`；后续从记录继承并验证唯一性 |

## PATHS

data/products/kgos/features.json
data/products/hee/features.json
data/products/hee/accessories.json
data/products/hee/sku-map.json
docs/preflight-brand.md
docs/matching-stability.md
lib/brand-scope.js
lib/archive.js
lib/auto-match.js
lib/auto-match2.js
lib/compare.js
lib/cdp.js
lib/check.js
lib/copy-as-suite.js
lib/correspondence.js
lib/doubao.js
lib/fetch-archive-names.js
lib/jl-products.js
lib/jl-sku-detail.js
lib/mark-suite.js
lib/match-one.js
lib/match.js
lib/erp-lock.js
lib/navigate.js
lib/preview-match.js
lib/remap-sku.js
lib/result.js
lib/targets.js
lib/visual.js
lib/verify-table.js
lib/wait.js
lib/utils/safe-write.js
lib/ops/annotate.js
lib/ops/create-suite.js
lib/ops/download-products.js
lib/ops/ensure-corr-page.js
lib/ops/read-erp-codes.js
lib/ops/read-skus.js
lib/ops/read-table-rows.js
lib/ops/remap-single.js
lib/ops/verify-archive.js
cli.js
docs/INDEX.md
