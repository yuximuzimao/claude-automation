# 2026-09-16 插件报错排查与 OmniCC 精简 NEAT

## 本次结论

- BugGrabber 的“用户界面有太多错误”并非单一来源；本次抓到的报错至少包括 `!LibGetFrame-1.0`、`NDui`、`EasyAuction` 和 `OmniCC`。
- 其中 `OmniCC` 出现 `3297x FontString:SetText(): Font not set`，并带有 `Lua Taint: OmniCC`，是本次已确认的高频错误源。
- 使用 `/occ blizzard` 切回暴雪自带冷却数字后，技能冷却数字立即恢复，确认此前“技能 CD 数字消失”由 OmniCC 接管冷却文字后自身字体错误导致。
- 当前用户对冷却数字的需求仅为技能图标显示剩余时间，暴雪自带功能已经满足；OmniCC 属于重复增强功能，没有继续保留的必要。
- 用户已实际删除 OmniCC；本轮只处理这一项，其他低频报错未改插件配置。

## 历史处理决定

- `OmniCC`：当前可由暴雪自带冷却数字完整替代；当前版本还会产生大量字体错误。整合包以后重新安装时可继续删除/禁用。
- 只有未来明确需要“背包/其他插件界面也显示冷却数字”或特殊字体、颜色、样式时，才重新评估 OmniCC；这不是默认恢复项，也不保存插件本体作为备份。

## 本次未继续处理的低频错误

- `NDui/Modules/Misc/Misc.lua:395`：`WardrobeTransmogFrame` 为 nil；本次仅观察到 2 次，且调用链来自 RurutiaSuite 顶栏加载 NDui。
- `EasyAuction`：调用受保护的 `Frame:SetPropagateKeyboardInput()` 被阻止；本次仅观察到 1 次。
- `!LibGetFrame-1.0`：出现 `ADDON_ACTION_BLOCKED`，触发点为 `MultiBarBottomRightButton11:SetAttribute()`；该库可能由上层插件调用，目前尚未继续追最终消费者。

## 复发时的检查顺序（非当前待办）

1. 保持 OmniCC 删除状态，继续正常使用暴雪自带冷却数字。
2. 如果 BugGrabber 再次频繁出现“错误过多”提示，优先查看当时错误次数最高的条目，不直接全量禁用插件或清空 WTF。
3. 只有确认某个剩余报错持续高频刷屏或影响功能，才在`tasks/todo.md`建立对应专项。
