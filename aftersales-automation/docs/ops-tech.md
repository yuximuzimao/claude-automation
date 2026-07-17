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

### 2.5 鲸灵账号 Session 与重新登录

**多账号切换缓存**：
- `data/current-session.json` 记录当前 Chrome 中实际注入的鲸灵账号。
- `scan-all.js`、`lib/server/pipeline.js`、`lib/server/op-queue.js` 任一路径成功执行 `jl.js inject` 后，都必须同步写入该文件。
- 如果扫描脚本切换了账号但未更新 `current-session.json`，后续采集/重处理会误以为页面仍是旧账号，跳过必要注入，可能读不到当前账号工单并把 live queue 错误推进到完成态。

**店铺管理状态显示**：
- `hasFile=false`：没有保存 session，显示「添加登录」。
- `hasFile=true + status=unknown`：已有 session 文件但未单账号验证，显示「未扫描」，不显示「重新登录」。
- `status=expired/error`：登录失效或扫描异常，显示「重新登录」。
- 重新登录保存成功后先写 `unknown`，只能通过店铺管理“打开后台”的安全编排或未来新 A1 单账号流程验证成 `ok`；批量刷新状态功能已删除，禁止恢复。

**安全切换门禁（2026-06-19）**：
1. `openAccountFlow` 先确定唯一鲸灵 `targetId` 并读取实时店铺名；目标账号已登录时直接复用。
2. 未登录或错号时，只清 jlsupp 子域 Cookie/storage；删除后再次读取，`JSESSIONID/_us` 任一残留都返回失败。
3. 只有 `success === true && verified === true` 才调用 04 注入，并把同一个 `targetId` 传入；禁止重新选择“第一个鲸灵 tab”。
4. 注入后固定导航 `https://scrm.jlsupp.com/micro-customer/business/after-sale-list`，再校验店铺名；禁止 `Page.reload` 继承旧工单详情 URL。

**重新登录待确认生命周期**：
1. 前端 `POST /api/accounts/:num/relogin`，后端启动 `../sessions/jl.js --auto-save`，写入 `../sessions/.relogin-port-<num>`。
2. 用户登录完成后点「确认保存」：前端调用 `POST /api/accounts/:num/relogin-confirm`，后端请求临时登录进程 `/save`，保存 session。
3. 用户点「取消」：前端先进入 `reloginCancelling`，立即把确认/取消按钮禁用并显示「取消中...」，再等待 `POST /api/accounts/:num/relogin-cancel` 返回。只有成功后才能清理 `reloginConfirm` 并恢复「重新登录」；失败时保留确认态，允许再次取消或确认。
4. 用户关闭登录页：`jl.js` 检测浏览器断开，清理 port 文件，不保存 session。若此后确认保存返回「没有待确认的登录会话」，前端退出确认态并恢复「重新登录」，不能永久卡在「确认保存」。
5. 正常操作不需要估算等待秒数：以页面从「取消中...」变回「重新登录」为完成信号；按钮恢复前不要重复点击登录。

**账号配置保存**：
- 保存 session 时必须用 `lib/jl-account-config.js` 合并旧账号配置，保留 `phone/name/note/file` 等字段。
- 禁止只写登录过程返回的 session 字段；否则会丢 `phone`，下次打开登录页无法自动填入账号。

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

// 验证弹窗已打开：等待 .el-dialog__wrapper.trade-detail-dialog 可见且含 h3.sub-title
// Array.from(document.querySelectorAll('.el-dialog__wrapper.trade-detail-dialog'))
//   .filter(d => d.getBoundingClientRect().width > 0)[0].querySelector('h3.sub-title')

// 读运单号：找 .list-title 中文字为"运单号:"的元素，读其 nextElementSibling
// 读物流文本：找含 h3.sub-title 且 innerText 包含"物流信息"的 .box 容器
var dialog = Array.from(document.querySelectorAll('.el-dialog__wrapper.trade-detail-dialog'))
  .filter(function(d){ return d.getBoundingClientRect().width > 0; }).slice(-1)[0];
var trackingEl = Array.from(dialog.querySelectorAll('.list-title'))
  .find(function(el){ return el.innerText.trim() === '运单号:'; });
var tracking = trackingEl && trackingEl.nextElementSibling
  ? trackingEl.nextElementSibling.innerText.trim() : '';
var logBox = Array.from(dialog.querySelectorAll('.box'))
  .find(function(b){ var h3 = b.querySelector('h3.sub-title'); return h3 && h3.innerText.includes('物流信息'); });
var logisticsText = logBox ? logBox.innerText : '';

// 关闭弹窗：点 .el-dialog__closeBtn（每次关一层，循环直到全部消失）
// 验证：.el-dialog__wrapper.trade-detail-dialog 可见数量归零
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
| ERP 搜索返回其他订单 | 搜索未生效或读到残留结果 | 逐行核验“平台交易号”；只重搜一次，第二次仍不匹配则报错停止 |
| 套件辨识错误 | 靠商品名猜套件 | 必须查档案V2 subItemNum 字段 |
| 店铺管理一直显示「确认保存」 | 重新登录页已关闭或无待确认 port 文件 | 点「取消」并等「取消中...」结束；仍不恢复时再检查 `/relogin-cancel` 响应和 `.relogin-port-<num>` |
| 重新登录保存后仍显示「重新登录」 | 保存后 `status=unknown` 被当作失效状态 | `unknown + hasFile` 是未单账号验证，不是失效；通过店铺管理“打开后台”安全验证 |
| 扫描后工单消失 | `scan-all.js` 切账号后未同步 `data/current-session.json` | 成功注入账号后立即写 current-session，再采集/重处理 |

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
- `[∞/永久保留]` **#16 ERP 弹窗判断**：ERP 订单详情弹窗是 `.el-dialog__wrapper.trade-detail-dialog`（标准 el-dialog 子类），用 `getBoundingClientRect().width > 0` 判断可见；`.js-logistics-container` 和 `.box-nav.box-toogle-el` 从未存在于生产DOM，禁止使用。运单号读 `.list-title[innerText="运单号:"].nextSibling`，物流文本读含 `h3.sub-title[includes("物流信息")]` 的 `.box` 容器；关闭弹窗用 `.el-dialog__closeBtn` 循环关直到可见数归零。**等待弹窗必须检测内容加载完成**：`h3.sub-title` 存在仅代表骨架渲染，内容区仍显示"暂无数据"（innerText <500 字符）；条件改为 `hasH3 && !(text.includes('暂无数据') && text.length < 500)`；timeout 15s，interval 800ms
- `[∞/永久保留]` **#17 订单行展开状态**：禁止用 `trade-icon-close/plus` class 判断展开状态（与状态无关）；正确用 `.module-trade-list-item-row2` 是否存在
- `[∞/永久保留]` **#18 识别字段必须多场景验证**：任何识别/判断字段，必须多订单、多场景对比验证后才能写入规则，一次测试不算验证
- `[∞/永久保留]` **#19 eval body 格式**：`POST /eval?target={id}` 的 body 为纯 JS 文本，禁止用 JSON 格式 `{"targetId":...,"code":...}`
- `[∞/永久保留]` **#26 ERP 物流入口**：禁止点 `a[data-name=logistics_info]`（打开快递公司过滤面板）；直接点 `show_detail_dialog`；同次搜索所有行一次性处理完，不重复搜索
- `[∞/永久保留]` **#34 截图需滚动**：截图前先 `window.scrollBy(0, el.getBoundingClientRect().top - 20)` 让内容贴近视口顶；内容超出视口时分段截图+PIL垂直拼接
- `[∞/永久保留]` **#41 ERP 登录检测**：ERP 掉线时浮层弹窗不改变 title/hash，检测失败；每次 navigateErp 前先 location.reload()（3秒），再检测 `.inner-login-wrapper`
- `[∞/永久保留]` **#43 鲸灵多账号切换必须同步 current-session**：任何成功 `jl.js inject` 的路径都要写 `data/current-session.json`，包括 `scan-all.js`。否则实际 tab 账号与缓存账号不一致，后续流程会跳过注入并读错/读空工单。
- `[∞/永久保留]` **#44 重新登录取消必须等后端收口**：点击取消后用 `reloginCancelling` 锁住确认/取消并显示「取消中...」；只有 `/relogin-cancel` 成功才清理 `reloginConfirm`、恢复「重新登录」，失败或请求抛错必须保留确认态。禁止先恢复按钮再异步取消，否则用户再次登录会让旧进程失去可追踪入口。`unknown + hasFile` 是保存但未验证，不等于登录失败。
- `[∞/永久保留]` **#45 ERP 搜索结果逐行验单**：每行“平台交易号”必须包含本次搜索的子订单号；合并订单用 `；` 或 `;` 拆分。结果错误只允许重搜一次，总共 2 次，第二次仍失败立即报错，不继续采集或推理。

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

---

## §8 队列紧急停止机制

> 2026-07-02 实现。旧 `emergencyStop()` 只杀 `spawnAsync` 子进程，对 async executor 完全无效——紧急停止按钮实际是摆设。现已通过 AbortController + 检查点机制修复。

### 8.1 如何停止

| 方式 | 操作 | 效果 |
|------|------|------|
| 全局紧急停止 | 前端面板点「🛑 紧急停止」 | 清空排队 + 中断运行中操作 |
| 单操作停止 | 队列下拉面板中运行中操作旁的「⏹」 | 只停该操作，保留排队 |
| API 停止 | `POST /api/emergency-stop` | 同上，返回验证结果 |
| API 单操作 | `DELETE /api/op-queue/:id` | 取消排队或停止运行中 |

### 8.2 停止流程（内部机制）

```
emergencyStop()
  ├─ paused = true（阻断新操作调度）
  ├─ 清空所有 queued 操作（内存队列）
  ├─ abortController.abort()（中断运行中 async executor）
  ├─ killAllTrackedProcs()（SIGTERM → 等2s → SIGKILL 僵尸）
  ├─ writeStopEvent() → data/emergency-stop.json
  └─ verifyStopState() → 返回 {queueEmpty, runningCleared, aliveProcs, allClean}
```

### 8.3 中断检查点

每个 executor 在关键步骤间调用 `assertNotAborted(op)`，检查 `op._abortSignal.aborted`。已中断时抛出 `AbortError`，被 `processNext()` 捕获标记为 `cancelled`（非 `error`）。

| Executor | 检查点 |
|----------|--------|
| execExecute | 打开账号后 → 列表排序后 → 打开详情后 |
| execReprocessOne | 打开账号后 → 列表排序后 → 定位工单后 → 打开详情后 |
| execOpenTicket | 打开账号后 → 列表排序后 → 定位工单后 |
| execScan | 每个账号迭代前 + 传入子函数 |
| execA1FixedBatch | 入口 + 传入子函数（每个工单迭代前检查） |
| execScanFinalize | 入口 → 清理拦截后 → 入队前 |
| execReturnInbound | 每个快递单号前 |
| execOpenAccount | 入口 |
| execReinfer | 入口 + 传入 execReprocessOne |

### 8.4 Stop 事件文件

**位置**：`data/emergency-stop.json`

```json
{
  "stoppedAt": "2026-07-02T08:49:27.576Z",
  "interrupted": { "id": "op-...", "type": "scan", "label": "...", "startedAt": "..." },
  "clearedCount": 5,
  "queueEmpty": true,
  "runningCleared": true
}
```

**生命周期**：
- 写入：`emergencyStop()` 调用时
- 读取：server 启动时输出警告；前端页面加载时检查并 Toast
- 查询：`GET /api/stop-event`
- 清除：`resume()` 调用时删除文件

### 8.5 重启后行为

1. server 启动时调用 `readStopEvent()` → 发现文件 → `console.log` 警告（含被中断的操作和清除的排队数）
2. 启动残留状态清理：`collecting/collected/inferring` → `pending`（与 stop 无关，是崩溃恢复通用逻辑）
3. **紧急停止后不会自动恢复被中断任务**：用户自行决定是否重新处理；这不影响 server 的定时扫描调度

### 8.6 验证停止结果

`POST /api/emergency-stop` 响应包含 `verify` 字段：

```json
{
  "ok": true,
  "paused": true,
  "verify": {
    "queueEmpty": true,
    "runningCleared": true,
    "aliveProcs": null,
    "paused": true,
    "allClean": true
  }
}
```

- `allClean: true` → 前端显示 "⏹️ 已停止：队列清空，进程已终止"
- `allClean: false` → 前端显示具体问题（队列未清空 / 子进程残留 / 运行中操作未清除）
