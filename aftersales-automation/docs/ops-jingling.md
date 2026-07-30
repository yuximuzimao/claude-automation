# 鲸灵与 CDP 操作指南

> 适用场景：鲸灵页面异常、CDP 调用、工单详情读取、内部备注、账号 Session 与重新登录。

## 1. CDP 代理端点速查

| 端点 | 用途 | 注意 |
|------|------|------|
| `GET /targets` | 列出所有标签页（获取 targetId） | — |
| `POST /eval?target={id}` | 在页面执行 JS | ⚠️ 必须加 `-H "Content-Type: text/plain"`，body 为纯 JS 文本；超时 120s |
| `POST /clickAt?target={id}` | CSS 选择器真实点击 | 需要浏览器在前台 |
| `GET /screenshot?target={id}&file=/tmp/x.png` | 截图保存到本地 | 不受窗口遮挡影响 |
| `GET /navigate?target={id}&url={url}` | 导航到 URL | 用于跨系统跳转 |
| `GET /scroll?target={id}&direction=bottom` | 滚动页面 | — |

---

## 2. 鲸灵平台操作技术细节

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

#### 售后列表就绪与慢加载判断

- URL 已是 `after-sale-list`、页面标题正常，只能证明路由完成，不能证明微应用列表已经挂载。`Page.navigate` 返回或超时也不等于业务 DOM 就绪。
- A1 Step 11 必须在同一个 `targetId` 上有界轮询，直到同时读到「售后工单」和「待商家处理」再进入排序与清单读取；禁止退回固定等待几秒后立即判错。
- 排序下拉值正确但工单时效顺序不升序时，说明平台当次渲染状态不一致。排序校验必须和清单读取一样从卡片 `.el-timer` 读取倒计时，不能只识别「后自动」文案。Step 11 只允许等待 2 秒后刷新当前已确认的售后列表页一次，等待业务 DOM 重新就绪后复核；不重复点击排序、不重跑账号切换、不重试任何写操作。刷新后排序值丢失或列表仍乱序时继续 fail-closed，也不把它当作 Session 失效。
- 页面加载明显变慢时，先检查整机 CPU、残留测试/CLI 进程和浏览器 target 响应。只有证据指向浏览器存储损坏时才清缓存；不要把清缓存或重新登录当作通用修复。

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

### 2.5 鲸灵账号 Session、新增与重新登录

**多账号切换缓存**：
- `data/current-session.json` 记录当前 Chrome 中实际注入的鲸灵账号。
- `scan-all.js`、`lib/server/pipeline.js`、`lib/server/op-queue.js` 任一路径成功执行 `jl.js inject` 后，都必须同步写入该文件。
- 如果扫描脚本切换了账号但未更新 `current-session.json`，后续采集/重处理会误以为页面仍是旧账号，跳过必要注入，可能读不到当前账号工单并把 live queue 错误推进到完成态。

**店铺管理状态显示**：
- `hasFile=false`：没有保存 session，显示「添加登录」。
- `hasFile=true + status=unknown`：已有 session 文件但未单账号验证，显示「未扫描」，不显示「重新登录」。
- `status=expired/error`：登录失效或扫描异常，显示「重新登录」。
- 新增或重新登录确认保存成功后写 `ok`。历史或其他流程写入的 `unknown` 只能通过店铺管理“打开后台”的安全编排或 A1 单账号流程验证；批量刷新状态功能已删除，禁止恢复。

**安全切换门禁（2026-06-19）**：
1. `openAccountFlow` 先确定唯一鲸灵 `targetId` 并读取实时店铺名；目标账号已登录时直接复用。
2. 未登录或错号时，只清 jlsupp 子域 Cookie/storage；删除后再次读取，`JSESSIONID/_us` 任一残留都返回失败。
3. 只有 `success === true && verified === true` 才调用 04 注入，并把同一个 `targetId` 传入；禁止重新选择“第一个鲸灵 tab”。
4. 注入后固定导航 `https://scrm.jlsupp.com/micro-customer/business/after-sale-list`，再校验店铺名；禁止 `Page.reload` 继承旧工单详情 URL。

**新增与重新登录的待确认生命周期**：
1. 新增店铺调用 `POST /api/accounts/add` 创建账号并返回账号编号；重新登录调用 `POST /api/accounts/:num/relogin`。后端统一启动 `../sessions/jl.js --auto-save`，等待写入 `../sessions/.relogin-port-<num>`，前端随后显示同一组「确认保存/取消」按钮。
2. 用户登录完成后点「确认保存」：前端调用 `POST /api/accounts/:num/relogin-confirm`，后端请求临时登录进程 `/confirm`，保存 session。
3. 用户点「取消」：前端先进入 `reloginCancelling`，立即把确认/取消按钮禁用并显示「取消中...」，再等待 `POST /api/accounts/:num/relogin-cancel` 返回。只有成功后才能清理 `reloginConfirm` 并恢复「重新登录」；失败时保留确认态，允许再次取消或确认。
4. 用户关闭登录页：`jl.js` 检测浏览器断开，清理 port 文件，不保存 session。若此后确认保存返回「没有待确认的登录会话」，前端退出确认态并恢复「重新登录」，不能永久卡在「确认保存」。
5. 正常操作不需要估算等待秒数：以页面从「取消中...」变回「重新登录」为完成信号；按钮恢复前不要重复点击登录。

**账号配置保存**：
- 保存 session 时必须用 `lib/jl-account-config.js` 合并旧账号配置，保留 `phone/name/note/file` 等字段。
- 仅在首次新增且账号 Session 文件尚不存在时传 `--initialize-phone`；确认保存后从 `accountN.json` 的 storageState 中读取 `https://scrm.jlsupp.com` localStorage 里的 `supplierInfo.supplierMobileList[0]`，仅将有效 11 位值初始化到缺失的 `accounts.json.phone`，供下次重新登录自动填写。认证数据没有可用手机号时不阻断 Session 保存。
- 已有 Session 的普通重新登录不提取、不覆盖手机号。禁止只写登录过程返回的 session 字段；否则会丢 `phone`，下次打开登录页无法自动填入账号。
- 直接维护重新登录自动填写手机号时，只修改 `../sessions/accounts.json` 对应账号的 `phone` 并读回验证；这不是网页操作，不启动 CDP、不运行 `jl add`、不触发登录，也不修改 `accountN.json`。只有用户明确要求立即重新登录或在平台实际修改手机号时，才进入重新登录流程。

---
