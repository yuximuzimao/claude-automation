# 冰冠旧审计退役说明（2026-09-09）

## 结论

退役两个旧审计入口：

- `scripts/audit_icecrown_final_publication.py`
- `scripts/audit_icecrown_route_coverage.py`

原因不是“暂时报错”，而是它们属于旧冰冠发布模型。`audit_icecrown_final_publication.py` 固定要求 61 个正式任务、16 步、289 分钟、`live_entry_confirmed_current_group_at_12897` 等历史快照；当前路线已经是 164 个正式任务、54 个玩家步骤，继续运行只会制造必然失败的伪红灯。该脚本在 2026-08-30 的 neat 归档中已经明确标记为不适用于当前路线。

旧 `audit_icecrown_route_coverage.py` 本身仍能算出 164/164，但它的输出只被旧 `final_publication` 消费；当前 `build_icecrown_route_structured.py` 已直接生成 `icecrown-route-structured-coverage.json`，`audit_icecrown_structured_candidate.py` 又对最终玩家结构做更强的接/做/交完整性与覆盖闭合检查，因此旧 coverage 成为重复层。

## 保留的现役审计

- `audit_icecrown_route_dependency_order.py`：仍被 structured builder 使用，当前 164/164、0 dependency violation。
- `audit_icecrown_draft_readiness.py`：仍能产生有效 review queue；本次运行识别 20 个五开待实测点和 1 个目标锚点风险。
- `audit_icecrown_repeat_clones.py`：仍能区分首轮任务与后续 daily/repeat clone，尤其能发现“同机制但不同任务名/不同数量”的情况。
- `audit_icecrown_structured_candidate.py`：现役最终结构审计。

## 从旧 final_publication 迁移的有效检查

为了不因退役大一统脚本丢掉真正有价值的能力，以下检查已经迁入 `audit_icecrown_structured_candidate.py`：

1. draft task card 的 `route_note` 是否实际出现在最终 HUD；
2. 五开共享/不共享/待实测备注的格式与发布完整性；
3. 任务日志同时激活数量峰值是否超过 25；
4. `exclude_dependency_on_blocked_task` 任务是否错误泄漏进最终玩家动作；
5. 玩家可见 route/step 文本是否泄漏裸 5 位任务 ID 或历史规划术语。

迁移后现役 structured audit 在当前 164任务 / 54步 / 269点结构上重新运行：`PASS / hard=0`。任务日志峰值为 13，未超过 25。

另外修正了一个旧 final audit 真正抓到的玩家文案问题：冰冠跨图任务《永恒之龙的秘密，再来一次》的五开备注不再直接显示裸 ID `12470`，改为引用任务名《永恒之龙的秘密》。

## 现役发布链

`build_icecrown_entry_route.py`
→ `audit_icecrown_route_dependency_order.py`
→ `build_icecrown_route_structured.py`
→ `audit_icecrown_structured_candidate.py`
→ `publish_icecrown_route.py`
→ 全局 `audit_route_atlas_player_text.py` / objective-anchor / flight-state 等审计。

旧 `final_publication` 与旧 `route_coverage` 不得重新加入默认构建、默认审计或发布门禁。历史依据保留在 Git 历史与本说明中。
