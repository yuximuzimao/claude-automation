# 技术排查入口

> 日常处理工单无需通读。先按问题类型打开对应文档；仍无法定位时再看本页速查。

## 1. 按问题查文档

| 遇到的问题 | 打开文档 |
|---|---|
| 鲸灵页面、CDP、工单详情、备注、账号切换 | [ops-jingling.md](ops-jingling.md) |
| ERP 导航、登录恢复、物流弹窗、图片上传 | [ops-erp.md](ops-erp.md) |
| 修改代码后的分步测试与验收 | [ops-testing.md](ops-testing.md) |
| 队列卡住、紧急停止、停止后恢复 | [ops-queue.md](ops-queue.md) |

## 2. 常见问题速查

| 现象 | 原因 | 解决 |
|------|------|------|
| eval 返回 undefined 或空 | 忘加 `Content-Type: text/plain` | 确认 curl 命令加了 `-H "Content-Type: text/plain"` |
| ERP 导航后仍在原页面 | 登录已掉线 | 先执行登录检测，已掉线走 [ERP 登录恢复](ops-erp.md#2-erp-登录状态检测与恢复) |
| 商品对应表搜索结果为空 | 店铺过滤器未切换 | 确认 getErpShop() 返回值正确，重新执行 product-match |
| 商品档案V2 DOM 空白但不报错 | DOM 未渲染，但 Vue dataList 有数据 | 直接从 Vue sv.dataList 读（脚本已处理） |
| 鲸灵备注弹窗关闭了但未保存 | 用了错误的按钮点击方式 | 必须用 MouseEvent dispatch（mousedown+mouseup+click），不能用 clickAt+button |
| ERP 搜索后无结果 | 用了主订单号而非子订单号 | 永远用子订单号（纯数字） |
| ERP 搜索返回其他订单 | 搜索未生效或读到残留结果 | 逐行核验“平台交易号”；只重搜一次，第二次仍不匹配则报错停止 |
| 套件辨识错误 | 靠商品名猜套件 | 必须查档案V2 subItemNum 字段 |
| 新增店铺登录后没有「确认保存」 | 新增入口没有进入统一登录确认态，或未返回新账号编号 | 检查 `/accounts/add` 是否返回 `num`，以及前端是否把该账号写入 `reloginConfirm` |
| 店铺管理一直显示「确认保存」 | 一次性登录窗口已关闭或无待确认 port 文件 | 点「取消」并等「取消中...」结束；仍不恢复时再检查 `/relogin-cancel` 响应和 `.relogin-port-<num>` |
| 扫描后工单消失 | `scan-all.js` 切账号后未同步 `data/current-session.json` | 成功注入账号后立即写 current-session，再采集/重处理 |
| 提醒“倒计时解析失败，停止冻结48小时清单” | 旧代码按“后自动…”等文案白名单找倒计时，平台新增 `后供应商处理超时`、`后流转至客服` 就会漏读 | Step 10 必须从卡片 `.el-timer` 组件读取倒计时，不按后缀文案筛选；数字主体仍须严格解析，失败继续触发安全门禁 |

---

## 3. 关键 URL 速查

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

## 4. 跨系统技术红线

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
