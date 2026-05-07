---
name: product-mapping
description: 快麦商品对应表匹配——ERP档案V2查询、7步闭环SKU匹配、视觉识图、套件标注。CDP 通过 HTTP proxy 操作快麦ERP。
skill_dir: product-mapping
entry: cli.js
---

## DO FIRST

1. **找 CLI 命令** → `cli.js`（18 个命令，JSON 输出）
2. **找流程** → `docs/INDEX.md §2`（4 步核查流程：check→识图→match→check）
3. **找单 SKU 匹配** → `lib/match-one.js`（7 步闭环，支持 `--from` 断点续跑）
4. **ERP 操作前必走完整导航** → `lib/navigate.js`（reload→登录检测→切tab→验hash→等Vue mount）
5. **写操作（新增匹配）必须人工确认后执行**

## ENTRY MAP

| 文件 | 作用 | 何时读 |
|------|------|--------|
| `cli.js` | CLI 入口，18 个命令路由 | 了解可用命令或新增命令时 |
| `lib/check.js` | 完整核查流程编排（扫描+标记+生成报告） | 改核查流程时 |
| `lib/match-one.js` | 单货号 7 步闭环编排器 | 改匹配流程/加步骤时 |
| `lib/match.js` | 批量匹配入口 | 批量匹配时 |
| `lib/cdp.js` | CDP HTTP proxy 客户端（localhost:3456），fallback 直连 | 写浏览器操作时 |
| `lib/targets.js` | 查找 ERP 浏览器 tab ID（固定 `1F46BAA...`） | 需要定位 ERP 标签时 |
| `lib/navigate.js` | ERP 页面导航（reload→登录→切tab） | ERP 页面跳转时 |
| `lib/erp-lock.js` | ERP 操作锁（acquireErpLock/releaseErpLock）暂停 aftersales | 任何 ERP 操作（navigateErp 自动调用） |
| `lib/correspondence.js` | 商品对应表读取 | 查对应表数据时 |
| `lib/archive.js` | 商品档案V2查询 | 查档案数据时 |
| `lib/visual.js` | 视觉识别结论管理 | 查/写识图结果时 |
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
| `lib/ops/verify-archive.js` | 档案匹配验证 | match 流程 step verify |

## CORE FLOWS

### 核查主流程（`docs/INDEX.md §2`）

```
① check --shop <店铺>  → 扫描+标记+下载图片+生成报告 (anchor: runCheck, listActiveProducts, readAllCorrespondence)
② 识图（Claude 手动） → visual-ok / visual-flag 记录结论 (anchor: recordVerdict, listPending)
③ match --shop <店铺>  → 自动匹配（套件+单品，异常停止） (anchor: matchOne, matchSku)
④ check --shop <店铺>  → 重新扫描+对比报告 (anchor: runCheck)
```

### 7 步闭环（`lib/match-one.js`，单 SKU）

```
download → read_skus → recognize → annotate → match → read_erp → verify
(anchor: downloadProducts, readSkus, annotate, remapSingle, createSuite, readErpCodes, verifyArchive)
```

- `recognize` 步骤由 Claude 手动执行，脚本到此暂停（**只识图片可见商品，不识配件**）
- `annotate` 步骤自动注入不可见配件（读 `data/products/{brand}/accessories.json`）
- 支持 `--from annotate` 从中间步骤续跑；`--brand hee` 指定品牌（默认 `kgos`）
- `stage` 状态机：`skus_read → images_done → annotated → matched → verified`

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

- **搜索框**：placeholder = "请输入商家编码"，实际只按货号过滤，输入 SKU platformCode 无效
- **正确做法**：全量读 40 行，按 `tds[6].innerText` 找目标货号行再展开
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
| 3 | 对应表搜索框按 platformCode 筛选 | 搜不到；必须全量读 40 行后按 `tds[6]` 找目标行 |
| 4 | 多层弹窗取第一个 footer | 必须遍历 `querySelectorAll` 找 `getBoundingClientRect().height > 0` 的 |
| 5 | 翻页用按钮状态判断结束 | 必须用"共X条"总数推算总页数 |
| 6 | 档案V2 查询前未清筛选残留 | 每次档案操作前检查/清空筛选状态 |
| 7 | 识图不看 features.json 颜色字段 | 颜色规则优先级高于图片文字标注 |
| 8 | 搜索 count > 0 宽松匹配 | `count !== 1` 必须报错"名称歧义"，防止套件写为子品 |

## PATHS

data/products/kgos/features.json
data/products/hee/features.json
data/products/hee/accessories.json
lib/archive.js
lib/auto-match.js
lib/auto-match2.js
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
lib/remap-sku.js
lib/result.js
lib/targets.js
lib/visual.js
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
