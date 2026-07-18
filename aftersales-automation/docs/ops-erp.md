# ERP 操作与登录排查

> 适用场景：ERP 页面导航、登录恢复、订单物流弹窗和拒绝退款凭证上传。

## 1. ERP 页面导航（顶部固定标签法）

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

## 2. ERP 登录状态检测与恢复

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

**保活心跳（已停用）**：
- `server.js` 仍保留 `startErpHeartbeat()` 函数，但自 2026-06-16 起启动流程不再调用它。
- 当前不做每小时主动续期；ERP session 超时后，由实际操作入口的 `checkLogin()` → `recoverLogin()` 现场恢复。
- 排查登录问题时不要等待心跳，也不要假设后台会主动告警；以本次操作返回和 `data/erp-health.json` 为准。

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

## 3. ERP 订单详情弹窗（查物流）

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

## 4. 图片上传（拒绝退款凭证）

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
