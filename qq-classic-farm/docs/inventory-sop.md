# QQ种子库存核对

现役入口：`scripts/farm_inventory.py`。脚本负责受保护的仓库导航、带重叠截图、边界确认、退出与文件校验回写；**AI负责读取名称/数量、去重和明确确认读全**。不是自动OCR，不得只看脚本退出0就猜库存。

所有命令在`/Users/chat/claude/qq-classic-farm`运行，通过Agent终端工具执行；图片用`functions.exec → tools.view_image`逐张读取输出的绝对路径，不使用通用cua.getState作前置。当前只处理QQ；仓库读取不收获、种植、出售或购买。

## 1. 何时调用

- 正常按成功种植记账的轮次不扫描仓库。
- 仓鼠末尾购买后，或CURRENT/pending明确要求核库时调用。已获授权的购买后刷新不用再次询问。
- 小程序必须已经打开；主入口从正常自己农场首页开始。`capture`内部会激活已有农场并做首页检查，不负责打开/关闭小程序。
- 出现`recheck_order_after_reopen`时，下一次新打开小程序后先盘点核对顺序，再开始田内操作。`--after-reopen`必须对应这次真实重开，不为清标记而随意添加。

## 2. 捕获完整列表

```sh
python3.13 scripts/farm_inventory.py capture --execute
```

返回0且`status=inventory_capture_complete`，读取manifest绝对路径和views数组。正常流程会打开仓库→种子，核对仓库标题和选中页签；向顶部滚动直至内容稳定，再逐段向下（重叠部分用于去重），底部滚动不再变化后保存确认图；关闭仓库并检查回到首页。最多12次顶部滚动、20个向下视图；任何动作失败即停，不自动重试，不把达到上限算读完。

默认输出工作区`_sandbox/qq-inventory-日期时间/`。manifest包括首尾确认、每张图片及SHA256、盘点前catalog指纹、捕获时间和warehouse_closed。没有完整manifest不进入apply。

只有当前确实已经在种子页的开发/人工恢复场景才用`capture --already-open --execute`；这不是绕过页面检查的开关。`--output-dir`可指定新的空目录，已有目录拒绝覆盖。没有`--execute`仅返回计划，不查询窗口。

## 3. AI读图与观察文件

1. 逐张调用图片查看工具读取manifest.views中所有图片及bottom_confirmation。顶部/底部由脚本确认，但条目名称和数量仍由AI读取；先确认种子页及各数字清楚。
2. 按仓库从上到下、从左到右排序。相邻截图重复行只计一次；最后一屏继续滚动的重复确认不重复加数量。空格不是数量0条目。参考`seed-catalog.json`的名称/图片匹配身份，但数量必须从本次截图取得，不能把旧数量复制为新观察。
3. 图片不能唯一识别名称、数字或重叠关系时停止，不写complete=true。新获得但已在catalog建档的种子（此前数量0）可正常记入；**真正未建档名称会被apply拒绝**，需要在明确读到名称/图标/资料后按种子建档流程补齐再重新捕获，不能套用相似种子。不把这种异常说成整链自动识别已支持。
4. 用终端Python/json或文件编辑工具在本次输出目录写`observations.json`。格式如下，entries必须填完整有库存条目，不是只列差额：

```json
{
  "complete": true,
  "reviewed_views": [0, 1, 2],
  "confirmed_absent_names": [],
  "entries": [
    {"name": "实际完整种子名称", "quantity": 123}
  ]
}
```

reviewed_views按本次manifest真实索引填写；上例的3个索引不是固定屏数。confirmed_absent_names只用于旧有库存、本次完整读取确认已不存在的条目；缺失项未明确列出会拒绝，不能自动把漏读当耗尽。

## 4. 写回与读回

```sh
python3.13 scripts/farm_inventory.py apply --manifest /本次绝对路径/manifest.json --observations /本次绝对路径/observations.json --execute
```

若这批捕获来自小程序本次重新打开、用于确认新种子重排，追加`--after-reopen`。主控Agent负责真实重开事实，脚本不自动推断。捕获超过1小时、图片指纹变动、catalog已被其它流程改动、漏读视图、重名/非正整数/未知种子、未确认缺失等均拒绝，不写库存。

apply使用`data/.inventory-apply.lock`的非阻塞文件锁，在锁内重查数据指纹并完成写回；已有提交占用时返回INVENTORY_APPLY_BUSY，不自动重试。这只保护库存文件提交，不是桌面互斥。新种子的重开核序义务先写pending，再改数量；后续写入中断不会因数量已变正而丢失待核要求。

成功输出`inventory_applied`、changes、entries、total_quantity、pending_remaining。实际值覆盖旧值，不在实读值上再叠加同一轮增减；同步seed-catalog.json与文档QQ表和最近盘点时间，微信内容不变。新增已建档种子若尚未重开确认则保留recheck_order_after_reopen标记；已核清且无待确认顺序则清除QQ待核标记。相同manifest和观察文件再次apply返回inventory_already_applied，不重复写入；已更改的观察不得靠重复apply冒充成功。

apply只更新库存/顺序，不生成种植计划、不扣未来库存，也不改实种记录。完成后按operation-sop§4重新核对唯一计划，尤其是耗尽/新增引起的页槽变化；确认计划后才允许后续田内操作或安排下一轮。

## 5. 结束与异常

成功capture已关闭仓库、回到农场首页；本轮其它动作已完成时，按工具文档调用farm_window.py close并确认farm_closed。若库存核对是开工前置，核验完可按已授权任务继续，不重复开场。

失败时保留本次目录和pending，不盲目重扫或清标记。部分截图不等于全量读取；数据/文档写入中断不重复叠加差额，先核对实际文件。未知界面/焦点/截图失败按execution-tools§4取证与安全退出。采集图片仅限本轮，未来轮次须重新捕获。

现场验收记录见[阶段归档](archive/neat/2026-11-12-continuous-farm-trial.md)，返回值/异常用例测试见`tests/test_inventory.py`；未验证的自然场景只记Todo，不以既往样本保证所有新品或未来主题。
