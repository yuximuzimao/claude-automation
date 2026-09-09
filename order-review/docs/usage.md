# 审单使用与数据维护

命令均在项目根目录执行。当前实现/待验证范围见[CURRENT](CURRENT.md)，操作红线见
[AGENTS](../AGENTS.md)，执行细节见[ERP关卡](rules/erp-execution.md)。

## 日常使用

原订单的商品总量、按订单查看和后台明细均只读。手动刷新或明确开启自动刷新后，
工具读取当前待审核页面序号1订单；本地保存方案不执行ERP。审核与拆分并审核由
用户逐单点击触发，不能把自动刷新理解为自动审核下一单。历史匹配和物流规则见
[根本约束](2026-07-23-package-rule-foundation.md)。

包裹编辑以“待分配库存”为中心：一次只编辑一个包裹，已完成包裹折叠为摘要；新增包裹只展示尚未分配的商品，返回编辑旧包裹时则展示该包已有商品和当前待分配商品。数量可直接输入并按回车或移开焦点生效，也可用紧凑的 `MIN / − / + / MAX` 快速清零、微调或加入最大可用量。底部只保留“新增包裹 / 恢复初始 / 保存方案”三个按钮；点击“保存方案”时会按 ERP 的剩余包裹方式处理：如果已经有空的最后一包，就把未分配商品放入该包；否则新增最后一包承接全部未分配商品，不能把剩余量追加到已有商品的当前包裹。随后才校验和保存。只有存在待分配商品且当前包裹已有商品时才能新增包裹；最后一个包裹不能删除。窗口中的商品、订单号、后台明细、推荐内容和方案信息均可拖动选中，并使用 `⌘C` 或右键菜单复制；每个平台订单组另有“复制单号”按钮。

## 运行

前提：Chrome 已使用远程调试端口 `9222` 打开 ERP 页面，并将前台标签页切换到标题为 `快麦ERP--待审核订单`、路由包含 `#/trade/toaudit/` 的页面。Chrome 应用脚本无法返回活动标签 URL 时，程序会用 macOS 辅助功能读取前台窗口标题作为保守回退；仍然只有唯一的待审核 CDP 页面才能被读取，不会转而扫描后台 ERP 标签。

浮窗只跟随 Chrome 主浏览器窗口；Chrome 内的确认框不会改变浮窗位置。切换到
其他应用时浮窗隐藏，切回 Chrome 时加入当前 Stage Manager 画面，但不会把 Chrome
或同组窗口切走。

```bash
PYTHONPATH=src python3.13 -m order_review.app
```

开发模式审核前检查：

```bash
PYTHONPATH=src python3.13 -m order_review.audit_dry_run
```

命令只读取当前已展开的序号 `1` 订单；未展开时直接停止，不会代替用户展开。检查结果追加到：

```text
~/Library/Application Support/Order Review/audit-executions.jsonl
```

日志仅保存系统订单号、确认快照/案例引用、状态、检查结果和时间，不保存完整商品原文或原始 DOM payload。

程序带跨进程单实例保护。已有悬浮窗运行时再次启动会直接退出，不会出现两个审单进程，也不会形成两个进程同时写案例的风险。案例仓库本身另有跨进程读改写锁，作为第二道保护。

## 测试

```bash
python3.13 -m pytest -q
```

Tk 界面测试必须完整退出：同一 pytest 进程只创建一个根窗口，fixture 无论成功或失败都强制取消后台任务并销毁窗口。运行前后需按精确命令复查审单和 pytest 进程；测试产生的新增进程、窗口或后台任务未清零时，本次测试不算完成，也不得继续重复启动。

需要复核长期内存时，可显式开启匿名诊断报告：

```bash
PYTHONPATH=src python3.13 -m order_review.app \
  --memory-report /private/tmp/order-review-memory.json
```

只有传入该参数时才启用 `tracemalloc`；日常运行不会承担追踪开销。

## 本地案例数据

确认后的不可变订单快照和包裹方案目前保存在：

```text
~/Library/Application Support/Order Review/cases.json
```

- 文件根节点和每条案例都带 `schemaVersion`。
- 读取一个订单时只解析一次案例文件，并复用同一份仓库快照完成同订单恢复、推荐、历史索引和兼容统计；案例增长后也不得退回同一次刷新重复解析完整 JSON。
- 每次写入都在跨进程锁内完成“读取 → 计算 → 校验 → 备份 → 原子替换 → 写后校验”，避免并发进程用旧状态覆盖新数据；写后校验失败时会隔离失败文件并自动恢复写入前的有效版本。
- 只有通过统一健康检查的旧文件才会进入正式备份；应用内按时间滚动保留 30 份有效旧版本。
- 当前实现按业务语义区分“确定性历史复用”和“人工形成的新案例”。精确匹配直接使用时不写订单采用关系或次数；近似容量候选经人工确认、或历史方案被人工修改时，才保存当前订单的新完整案例。
- 如需清空历史案例，应先退出悬浮窗并备份或移走该文件；工具本身不提供删除历史案例的入口。

### 案例健康检查

只读检查真实案例，不会修改文件：

```bash
PYTHONPATH=src python3.13 -m order_review.case_audit
```

检查覆盖 JSON/schema、数量守恒、案例和 assignment 引用、版本链和循环、重复 ID、规则统计以及商品/订单身份缺失。错误会阻止正式写入和备份；警告用于提示数据质量风险。

### 多版本备份与人工恢复

应用内备份位于：

```text
~/Library/Application Support/Order Review/backups/
```

查看有效备份（跨 `cases-*`、`pre-restore-*` 等前缀统一按文件时间排序；
文件名没有有效时间戳时回退到修改时间）：

```bash
PYTHONPATH=src python3.13 -m order_review.case_restore --list
```

恢复必须明确指定来源并加 `--yes`：

```bash
PYTHONPATH=src python3.13 -m order_review.case_restore \
  --from "/完整路径/backups/cases-时间戳.json" \
  --yes
```

执行恢复前必须先退出审单悬浮窗；命令会尝试获取单实例锁，程序仍在运行时直接拒绝恢复。恢复来源按实际读取字节重新校验：当前正式文件有效时先创建 `pre-restore`，当前文件损坏时原样隔离为 `cases.corrupt-时间戳.json`，然后原子恢复并再次校验。恢复失败时来源备份和故障文件均保留，不会静默删除或自动掩盖问题。

根工作区备份脚本 `/Users/chat/claude/backup-workspace.sh` 会纳入有效案例和已经存在的推荐事件文件，默认按时间保留 8 代工作区归档。若案例校验失败或正式 `cases.json` 缺失：

- 校验失败的故障文件改名为 `cases.invalid.json`，不会冒充正式案例。
- 归档附带跨前缀统一排序后时间最新的 3 个有效应用内案例备份。
- 校验失败写入 `ORDER_REVIEW_CASES_INVALID.txt`；正式文件缺失写入 `ORDER_REVIEW_CASES_MISSING.txt`。
- 独立健康文件 `order-review-health.txt` 标记为 `degraded`。
- 工作区其他内容继续归档，但脚本最终返回退出码 3，让 launchd 能识别降级状态。

推荐事件损坏时采用同样的隔离和降级策略。原有 launchd 调度仍为每周日 08:07。

### 推荐事件与离线回放

推荐效果事件独立保存在：

```text
~/Library/Application Support/Order Review/recommendation-events.jsonl
```

事件只有 `shown`、`confirmed_direct`、`confirmed_modified` 和 `abandoned_unknown`。同一应用会话内按订单签名和推荐 ID 去重；`abandoned_unknown` 只代表没有得到确认结果，不会被当作拒绝或负反馈。事件仅供离线观察，不参与推荐置信度或执行判断；写入是 best-effort，失败不能阻断刷新、切换订单、人工创建方案或关闭窗口。

只读检查推荐事件 JSONL：

```bash
PYTHONPATH=src python3.13 -m order_review.recommendation_event_audit
```

坏行会在健康检查和备份状态中明确显示；离线统计仍只读取有效行，不让辅助事件损坏阻塞案例报告。

只读生成历史回放和数据成熟度报告：

```bash
PYTHONPATH=src python3.13 -m order_review.case_replay
```

回放按确认时间隔离历史、排除被测试订单自身，并把同订单版本链折叠为一个独立样本，避免自我验证和样本虚增。历史表现使用订单首次确认方案作为测试目标，统计唯一候选完全一致、候选包含实际方案、冲突、错误推荐和无推荐；当前单包/多包成熟度使用每个订单最新有效版本。报告同时按匹配类型给出覆盖率和实际方案命中率。

需要定位具体订单时使用逐单明细：

```bash
PYTHONPATH=src python3.13 -m order_review.case_replay --details
```

明细会列出每层候选路径、人工实际包裹、系统候选、来源案例和问题分类，并自动核对 `data/replay-problem-set.json` 中的固定真实问题单。默认只展开需要关注的错误、低效和冲突订单；需要机器读取全部订单时使用 `--json --details`。该报告用于量清算法问题，不会写案例、改变推荐或操作 ERP。

较大数量单包历史只作为人工参考，不是连续容量结论。如果同一商品集合已经出现“较大数量单包、较小数量却要多包”的反例，系统会停止生成该类单包外推，并在悬浮窗列出冲突数量和阻断原因；相同数量已有精确历史时仍优先恢复精确方案。
