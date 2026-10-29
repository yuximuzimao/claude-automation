# M0 离线验收与下一步入口（2026-10-30 北京时间）

## 本轮完成的实现

- `scripts/seed_order.py`：纯函数 `compute_visible_order`、`compute_picker_position`、`consume_confirmed`，默认每页 5 个。零库存自动过滤；确认消耗后才返回新的数量字典，不修改 stable_order。
- `scripts/bootstrap_runner_state.py`：从 2026-10-28 仓库快照与历史 picker 证据初始化 `data/seed-order.json` / `data/farm-state.json`。只生成一次；发现目标文件已存在就拒绝覆盖。
- `scripts/farm_runner.py`：M0 `dry-run`，读取策略样例与事实状态，按四格事务顺序推演目标 page/slot、扣减模拟库存，再推演普通一键种植；只输出 JSON，不点击、不截图、不写状态。
- `schemas/run-plan.schema.json` + `examples/run-plan.sample.json`：策略与 UI 派生位置严格分离；样例标记 EXAMPLE-ONLY-NOT-ACTIVE，不能当作实际下次种植计划。
- `tests/test_runner_m0.py`：离线回归测试。

## M0 验收证据

命令：

```bash
python3 -m unittest discover -s tests -v
python3 scripts/farm_runner.py dry-run
```

11 项单测通过；dry-run 返回 `dry_run_ok`，`llm_round_trips=0`、`click_count=0`、`screenshot_count=0`、`persisted=false`。

当前快照的目标位置：

| 平台 | 种子 | page/slot |
| --- | --- | --- |
| QQ | 泡泡棉花糖 | 1/3 |
| QQ | 紫薇 | 3/3 |
| QQ | 天山红枫 | 4/1 |
| 微信 | 星语铃花 | 1/3 |
| 微信 | 黄金果 | 2/1 |
| 微信 | 天山红枫 | 2/5 |

单测覆盖：种子用到 0 后自动左移并跨页、已知种子 0→positive 回到 stable_order 位置、历史未知正库存拒绝猜测、库存不足停止、错误 placement/非 24 格停止、RUN_PLAN 写入 page/slot 被拒绝、原子写盘和 `run-next` 安全停止。

## 历史顺序证据与未验证假设

- 2026-10-28 fresh-entry 仓库顺序是当前 `stable_order` 的唯一已校准基线；QQ 33 种、微信 22 种。
- `picker-order.json` 里的历史有但 fresh-entry 仓库没有的种子存为 `historical_zero_candidates_uncalibrated`。**不能凭旧顺序给这些种子猜稳定插入点。** 如果后来获得这些种子，`ORDER_SYNC_REQUIRED` 停止，等重新进入后校准。
- 微信旧顺序出现 `艾草 → 森野白桃`，fresh-entry 是 `森野白桃 → 森野甜橙 → 艾草`。目前只能判定历史存在差异，**不能证明永久改序，也不能证明重进一定恢复**。

后续真机验证：记录重进后的 fresh-entry 顺序 → 获得一个原本为 0/未出现的种子 → 不退出读取 session 顺序 → 退出/关闭并重新进入 → 读取 fresh-entry 顺序 → 比较相对顺序。只有实测重进后仍不恢复才考虑 `order_revision`。

## 安全边界与下一检查点

- `data/farm-state.json` 已应用明确记录的 2026-10-29 数量变化，但 10-28 仓库基线并非当前实时真值；QQ / 微信都标记 `inventory_dirty=true`。**M1/M2 真机点击前必须重新校准。**
- `python3 scripts/farm_runner.py run-next` 当前返回结构化 `RUNNER_NOT_READY`，不会打开农场。不要为跑通 M0 擅自解除。
- 下一轮从 M1 开始：window registry、window-local logical 坐标、截图裁剪、in-process vision、常驻 CGEvent helper、QQ/微信窗口恢复、收获状态机。先本地 mock/dry-run，再有限真机验收。
- 仍禁止 Agent 单击级正常执行、策略决策下沉、定时化/复杂化肥/通用视觉 Agent。
