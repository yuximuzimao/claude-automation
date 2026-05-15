# 技术排查与操作指南（ops-tech）

> 适用场景：操作报错、页面异常、CDP 问题、底层操作细节
> 日常处理工单时无需读此文件；遇到技术问题时按需查阅

---

## §1 CDP 代理端点速查

| 端点 | 用途 | 注意 |
|------|------|------|
| `GET /targets` | 列出所有标签页（获取 targetId） | — |
| `POST /eval?target={id}` | 在页面执行 JS | ⚠️ 必须加 `-H "Content-Type: text/plain"`，body 为纯 JS 文本；超时 120s |
| `POST /clickAt?target={id}` | CSS 选择器真实点击 | 需要浏览器在前台 |
| `GET /screenshot?target={id}&file=/tmp/x.png` | 截图保存到本地 | 不受窗口遮挡影响 |
| `GET /navigate?target={id}&url={url}` | 导航到 URL | 用于跨系统跳转 |
| `GET /scroll?target={id}&direction=bottom` | 滚动页面 | — |

---

## §2 鲸灵平台操作技术细节

### 2.1 Vue2 导航（先验证，不在目标页才导航）

```javascript
// 验证是否已在列表页
var isOnList = window.location.href.includes("after-sale-list");
if (!isOnList) {
  var vue = document.querySelector("#app").__vue__;
  vue.$router.push("/business/after-sale-list");
  // 等 2 秒后验证 href.includes("after-sale-list")
}

// 已在列表页后，push 到详情页
vue.$router.push({
  path: "/business/after-sale-detail",
  query: { workOrderNum: "100001774760923825229" }
  // ⚠️ 必须用 workOrderNum，不是 afterSaleId
});
// 等 3 秒后验证
```

### 2.2 读取工单详情数据（Vue 组件 orderInfo）

```javascript
(function() {
  function findDeep(vm, depth) {
    if (depth > 10 || !vm) return null;
    if (vm.$data && vm.$data.orderInfo) return vm.$data.orderInfo;
    for (var i = 0; i < (vm.$children || []).length; i++) {
      var r = findDeep(vm.$children[i], depth + 1);
      if (r) return r;
    }
    return null;
  }
  var info = findDeep(document.querySelector("#app").__vue__, 0);
  return JSON.stringify({
    subOrders: (info.subBizOrderDetailDTO || []).map(function(s) {
      return {
        id: s.subBizOrderId,
        sku: s.spuBarcode,
        attr1: s.attribute1,
        afterSaleNum: s.afterSaleNum,
        logistics: s.logisticsStatusDesc
      };
    }),
    gifts: (info.giftSubBizOrderDetailDTO || []).map(function(g) {
      return { id: g.subBizOrderId, sku: g.spuBarcode, attr1: g.attribute1 };
    }),
    mainOrderId: info.bizOrderId
  });
})()
```

### 2.3 鲸灵物流弹窗（多包裹）

```javascript
// 点"查看物流"后等 2 秒
// ⚠️ 弹窗有多个 tab（包裹1、包裹2...），每个 tab 是不同快递单号
var btns = Array.from(document.querySelectorAll("button.el-button--text.el-button--mini"));
btns.find(b => b.textContent.trim() === "查看物流")?.click();

// 读当前 tab
var dialogs = Array.from(document.querySelectorAll(".el-dialog__wrapper"))
  .filter(d => window.getComputedStyle(d).display !== "none");
var dialog = dialogs[0];
dialog.innerText  // 包含物流单号和物流节点

// 切换到包裹2
var tab2 = Array.from(dialog.querySelectorAll(".el-tabs__item"))
  .find(t => t.textContent.includes("包裹2"));
tab2?.click();
// 等 1 秒后再读 dialog.innerText
```

### 2.4 内部备注操作（三次 eval）

> ⚠️ 严禁点「+新增备注」按钮——会进入「订单备注（供应商）」区域，买家可见

```javascript
// eval 1：点击工单行的「致内部」按钮（用工单号精确定位）
var ticketNum = '100001774954951289846';
var spans = Array.from(document.querySelectorAll('span'));
var ticket = spans.filter(el => el.innerText && el.innerText.trim() === ticketNum)[0];
var ticketY = ticket.getBoundingClientRect().top;
var btns = Array.from(document.querySelectorAll('button'))
  .filter(b => b.innerText.trim() === '致内部' && b.getBoundingClientRect().width > 0);
var btn = btns.reduce((a, b) =>
  Math.abs(b.getBoundingClientRect().top - ticketY) <
  Math.abs(a.getBoundingClientRect().top - ticketY) ? b : a
);
['mousedown','mouseup','click'].forEach(t =>
  btn.dispatchEvent(new MouseEvent(t, {bubbles:true, cancelable:true}))
);

// eval 2（sleep 1s 后）：填写内容
var ta = document.querySelector('textarea[placeholder="添加内部备注"]');
ta.focus();
document.execCommand('selectAll');
document.execCommand('insertText', false, '备注内容');

// eval 3：提交（必须 MouseEvent dispatch，不能用 clickAt + button 选择器）
var addBtn = Array.from(document.querySelectorAll('button'))
  .filter(b => b.innerText.trim() === '添加' && b.getBoundingClientRect().width > 0)[0];
['mousedown','mouseup','click'].forEach(t =>
  addBtn.dispatchEvent(new MouseEvent(t, {bubbles:true, cancelable:true}))
);
```

---

## §3 ERP 操作技术细节

### 3.1 ERP 页面导航（顶部固定标签法）

```javascript
// Step 0：前置检查，已在目标页则跳过
var targetHash = "#/tradeNew/manage/";  // 替换为目标页 hash
if (window.location.hash !== targetHash) {
  var li = Array.from(document.querySelectorAll("li.fix-tab"))
    .find(el => el.textContent.trim() === "订单管理");  // 替换为目标页名
  li.click();
  // 等 2 秒后验证 window.location.hash === targetHash
}
```

**四个常用页面**：
| 页面 | 标签文字 | hash | document.title |
|------|---------|------|----------------|
| 订单管理 | `订单管理` | `#/tradeNew/manage/` | `快麦ERP--订单管理` |
| 售后工单新版 | `售后工单新版` | `#/aftersale/sale_handle_next/` | `快麦ERP--售后处理` |
| 商品档案V2 | `商品档案V2` | `#/prod/parallel/` | `快麦ERP--商品档案V2` |
| 商品对应表 | `商品对应表` | `#/prod/prod_correspondence_next/` | `快麦ERP--商品对应表` |

> ⚠️ **禁止**：`/navigate` 直接跳转任何 ERP 功能页面（会被重定向到首页或登录页）

### 3.2 ERP 登录状态检测与恢复

**检测方法**（`checkLogin()` 在 `lib/erp/navigate.js`）：

```javascript
// 任意一条为 true 则判定未登录
url.includes('login')
|| !title.includes('快麦ERP--')
|| !!document.querySelector('.inner-login-wrapper')  // session 超时弹窗
```

**恢复机制（`recoverLogin()` 在 `lib/erp/navigate.js`）**：

```
Phase 1: 凭据注入（injectCredentials，确定性）
  注入三字段：
    #login-company（公司名，用 id=login-company 定位）
    input[name="userName"]（账号）
    input[type="password"]（密码）
  注入方式：nativeInputValueSetter + dispatchEvent('input'/'change')
  凭据来源：优先 env vars（ERP_COMPANY/ERP_USERNAME/ERP_PASSWORD），
           无 env vars 时用硬编码 fallback（~/.claude/settings.json env 块配置可选）
  注入后读回验证（value.length > 0），失败则抛错

  ⚠️ Chrome 自动填充在 CDP headless 模式下完全不触发（2026-05-13 测试确认：reload 等 20s 三字段全空）
  ⚠️ cdp.clickAt(input) 会触发表单重置清除内容，登录页禁止点击任何输入框

Phase 2: 点登录按钮 → 等协议弹窗（.rc-kmui-com-dlg）→ 点同意（input.rc-btn-ok）
  checkLogin() 确认 loggedIn: true → 成功
  否则 → 抛错（触发熔断计数）
```

**熔断器**（`data/erp-circuit-breaker.json`）：
- 连续 3 次认证失败（`classifyErpError()` 返回 true）→ `state: 'open'`
- 熔断冷却 15 分钟 → `state: 'half_open'` → 允许一次探测
- 熔断中任何 `erpNav()` 调用立即返回熔断错误，不重试

**保活心跳**（`server.js startErpHeartbeat()`）：
- 每 1 小时检查 ERP 登录状态
- 已登录 → `fetch(location.href + '?_t=Date.now(), {credentials:'include'})` 续期 session
  → fetch 后再调 `checkLogin()` 验证 session 仍有效
  → 失败则降级到 `recoverLogin()`
- 未登录 → 直接 `recoverLogin()`
- 连续失败超过 30 分钟 → 重复 macOS 通知告警

**ERP 健康状态文件**（`data/erp-health.json`，读合并写，不会覆盖丢字段）：
```json
{
  "status": "up",
  "lastOkTime": "ISO",
  "lastFailTime": "ISO",
  "lastAlertTime": "ISO",
  "failReason": "...",
  "consecutiveAuthFail": 0
}
```

> 凭据来源优先级：env vars（`ERP_COMPANY`/`ERP_USERNAME`/`ERP_PASSWORD`）→ 硬编码 fallback（代码内已内置）。env vars 不配置也能正常工作，配置后可覆盖默认凭据。

### 3.3 ERP 订单详情弹窗（查物流）

```javascript
// ⚠️ 严禁点 a[data-name=logistics_info]——会开快递公司过滤面板，完全无用
// ✅ 正确：点 show_detail_dialog 打开订单详情弹窗
var row = rows[N];  // N = 目标行序号（0-based）

// 确认已展开（未展开则先点）
var isExpanded = !!row.querySelector(".module-trade-list-item-row2");
if (!isExpanded) {
  row.querySelector(".J_Trigger_Show_Orders").click();  // 等 2 秒
}

// 打开详情弹窗
var link = row.querySelector("a[data-name=show_detail_dialog][data-sid]");
link.click();  // 等 2 秒

// 验证弹窗已打开（禁止用 el-dialog__wrapper display:none 判断）
// 正确：document.querySelector(".js-logistics-container") !== null

// 读物流
var logisticsText = document.querySelector(".js-logistics-container").innerText;
var trackingText = document.querySelector(".box-nav.box-toogle-el").innerText;

// 关闭弹窗
// clickAt: a.ui_close
// 验证：document.querySelector(".js-logistics-container") === null
```

**多包裹优化（同一次搜索处理所有行）：**
```
搜主子订单号 → 展开所有行 → 行1: show_detail_dialog → 读物流 → 关闭 → 行2: ... → 全部处理完
再搜赠品子订单号（如有）→ 同上
⚠️ 禁止搜一次只看一行就切出去再搜
```

### 3.4 图片上传（拒绝退款凭证）

```bash
# Step 1: 截图 + 裁剪弹窗区域
COOKIES=$(curl -s "http://localhost:3456/eval?target=$JLID" \
  -d 'document.cookie' | python3 -c "import sys,json; print(json.load(sys.stdin)['value'])")

curl -s "http://localhost:3456/screenshot?target=$JLID&file=/tmp/full.png"

RECT=$(curl -s "http://localhost:3456/eval?target=$JLID" \
  -d 'var d = document.querySelector(".el-dialog"); JSON.stringify(d.getBoundingClientRect())')
python3 -c "
from PIL import Image; import json
rect = json.loads('$RECT')
img = Image.open('/tmp/full.png')
img.crop((int(rect['x']), int(rect['y']),
          int(rect['x']+rect['width']), int(rect['y']+rect['height']))).save('/tmp/crop.png')
"

# Step 2: 上传
RESULT=$(curl -s -b "$COOKIES" \
  -F "fileUpload=@/tmp/crop.png;type=image/png" \
  "https://seller-portal.jlsupp.com/base-service/imgUpload")
IMG_URL=$(echo $RESULT | python3 -c "import sys,json; print(json.load(sys.stdin)['entry'][0])")

# Step 3: 注入 Vue 组件
curl -s "http://localhost:3456/eval?target=$JLID" \
  -d "(function() {
  function findComp(vm, name, d) {
    if (d > 20 || !vm) return null;
    if ((vm.\$options||{}).name === name) return vm;
    for (var i=0; i<(vm.\$children||[]).length; i++) {
      var r = findComp(vm.\$children[i], name, d+1);
      if (r) return r;
    }
    return null;
  }
  var comp = findComp(document.querySelector('#app').__vue__, 'WorkOrderStateForm', 0);
  comp.\$set(comp.formInfo, 'operaterEvidencePegUrl', ['$IMG_URL']);
  comp.\$set(comp, 'templateRefusePictureList', ['$IMG_URL']);
  return 'done';
})()"
```

> ⚠️ **禁止**：DataTransfer 设置 file input / 开本地 HTTP 服务器 / 设置 XHR/fetch 全局拦截器（会导致堆栈溢出）

---

## §4 常见问题排查

| 现象 | 原因 | 解决 |
|------|------|------|
| eval 返回 undefined 或空 | 忘加 `Content-Type: text/plain` | 确认 curl 命令加了 `-H "Content-Type: text/plain"` |
| ERP 导航后仍在原页面 | 登录已掉线 | 先执行登录检测，已掉线走 §3.2 恢复流程 |
| 商品对应表搜索结果为空 | 店铺过滤器未切换 | 确认 getErpShop() 返回值正确，重新执行 product-match |
| 商品档案V2 DOM 空白但不报错 | DOM 未渲染，但 Vue dataList 有数据 | 直接从 Vue sv.dataList 读（脚本已处理） |
| 鲸灵备注弹窗关闭了但未保存 | 用了错误的按钮点击方式 | 必须用 MouseEvent dispatch（mousedown+mouseup+click），不能用 clickAt+button |
| ERP 搜索后无结果 | 用了主订单号而非子订单号 | 永远用子订单号（纯数字） |
| 套件辨识错误 | 靠商品名猜套件 | 必须查档案V2 subItemNum 字段 |

---

## §5 关键 URL 速查

| 系统 | 页面 | URL |
|------|------|-----|
| 鲸灵 | 售后工单列表 | `https://scrm.jlsupp.com/micro-customer/business/after-sale-list` |
| 鲸灵 | 售后工单详情 | Vue Router push `workOrderNum={工单号}` |
| ERP | 订单管理 | `https://erpb.superboss.cc/index.html#/tradeNew/manage/` |
| ERP | 售后工单新版 | `https://erpb.superboss.cc/index.html#/aftersale/sale_handle_next/` |
| ERP | 商品对应表 | `https://erpb.superboss.cc/index.html#/prod/prod_correspondence_next/` |
| ERP | 商品档案V2 | `https://erpb.superboss.cc/index.html#/prod/parallel/` |
| 鲸灵图片上传 | API | `https://seller-portal.jlsupp.com/base-service/imgUpload` |

---

## §6 已知坑位（技术操作层）

- `[∞/永久保留]` **#1 导航参数**：鲸灵详情页导航必须用 `workOrderNum`，禁止用 `afterSaleId`
- `[∞/永久保留]` **#2 Vue Router 导航**：禁止直接 URL 跳转鲸灵详情页（组件数据为空），必须先回列表再 router.push
- `[∞/永久保留]` **#3 ERP 用子订单号**：ERP 搜索永远用子订单号（纯数字），禁止用主订单号
- `[∞/永久保留]` **#4 ERP radio 点击**：ERP 切「四合一/mixKey」必须用 clickAt 真实点击，禁止 JS 赋值 radio.checked
- `[∞/永久保留]` **#8 搜索框填值**：禁止直接 `input.value = "xxx"` 后搜索；必须用 execCommand("insertText") + 回车，且填值和回车必须在同一 eval 里
- `[∞/永久保留]` **#10 禁止全局拦截器**：严禁设置全局 fetch/XHR 拦截器——会导致堆栈溢出，页面无法恢复
- `[∞/永久保留]` **#11 eval 不 await**：CDP eval 超时 120s，不能在 eval 里 await 长时间 XHR，异步请求不在 eval 里等待
- `[∞/永久保留]` **#14 ERP 导航方式**：禁止用 /navigate 跳转任何 ERP 功能页面（会被重定向），必须用顶部 `li.fix-tab` 标签导航
- `[∞/永久保留]` **#16 ERP 弹窗判断**：ERP 订单详情弹窗不是标准 el-dialog，禁止用 `el-dialog__wrapper` display:none 判断；正确用 `.js-logistics-container !== null`
- `[∞/永久保留]` **#17 订单行展开状态**：禁止用 `trade-icon-close/plus` class 判断展开状态（与状态无关）；正确用 `.module-trade-list-item-row2` 是否存在
- `[∞/永久保留]` **#18 识别字段必须多场景验证**：任何识别/判断字段，必须多订单、多场景对比验证后才能写入规则，一次测试不算验证
- `[∞/永久保留]` **#19 eval body 格式**：`POST /eval?target={id}` 的 body 为纯 JS 文本，禁止用 JSON 格式 `{"targetId":...,"code":...}`
- `[∞/永久保留]` **#26 ERP 物流入口**：禁止点 `a[data-name=logistics_info]`（打开快递公司过滤面板）；直接点 `show_detail_dialog`；同次搜索所有行一次性处理完，不重复搜索
- `[∞/永久保留]` **#34 截图需滚动**：截图前先 `window.scrollBy(0, el.getBoundingClientRect().top - 20)` 让内容贴近视口顶；内容超出视口时分段截图+PIL垂直拼接
- `[∞/永久保留]` **#41 ERP 登录检测**：ERP 掉线时浮层弹窗不改变 title/hash，检测失败；每次 navigateErp 前先 location.reload()（3秒），再检测 `.inner-login-wrapper`

---

## §7 测试框架使用规范

> 框架入口：`node test.js`，代码在 `test/schemas.js` + `test/runner.js`

### 触发时机（以下情况必须跑）

- 修改了 `lib/` 任意文件或 `cli.js` 之后
- 某个 CLI 步骤连续出错 ≥2 次
- 新增了 CLI 命令（必须先写 schema，再上线）

### 步骤速查

| 步骤ID | 对应命令 | 说明 |
|--------|---------|------|
| JL-1 | `list` | 读工单列表 |
| JL-2 | `read-ticket <工单号>` | 读工单详情 |
| JL-5 | `logistics <工单号>` | 读鲸灵物流（flow-5.3 核心） |
| PM-1 | `product-match <货号> [attr1]` | 商品对应表 |
| PA-1 | `product-archive <specCode>` | 商品档案V2 |
| ERP-1 | `erp-search <子订单号>` | ERP搜索订单 |
| ERP-2 | `erp-logistics <行号>` | ERP物流详情 |
| ERP-3 | `erp-aftersale <退货单号>` | ERP售后入库 |
| JL-3 | `reject`（预检，不提交） | 拒绝退款 |
| JL-4 | `approve`（预检，不提交） | 同意退款 |

### 典型用法

```bash
# 1. 修改了任何代码前，先跑基础设施检查
node test.js l0

# 2. 修改了 logistics.js → 验证 JL-5
node test.js step JL-5 <工单号>

# 3. 修改了 erp-search 相关 → 验证 ERP-1 + ERP-2
node test.js step ERP-1 <子订单号>
node test.js step ERP-2 <子订单号>

# 4. 数据链路验证（步骤间衔接，需有退货快递单号的工单）
node test.js chain <工单号>

# 5. 全量稳定性测试（各只读步骤跑10次，约30分钟）
node test.js all <工单号>
```

### 验收标准

- **单步骤**：≥ 9/10 次成功
- **全量**：所有步骤均 ≥ 9/10
- **新命令上线前**：至少跑对应 step × 3次 + 相关 chain 一遍
