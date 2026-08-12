# Questie 人物历程导出

人物历程不是生成第一版静态路线的前提，但它能提供当前角色的实际接取、完成和放弃顺序，用于发现回头路、遗漏和任务批次差异。

## 推荐方式：让 Claude Code 脱敏导出

1. 完全退出魔兽世界，避免SavedVariables尚未写盘。
2. 在Windows上的Claude Code中执行以下任务：

```text
请只读查找：
C:\Program Files (x86)\World of Warcraft\_classic_titan_\WTF\Account

定位最近修改的账号级 SavedVariables\Questie.lua。
不要上传整个WTF，不要修改原文件。

该文件是账号级容器。请从 `QuestieConfig.char` 的多个角色条目中定位我本次新建的血精灵圣骑士对应条目，不能把整个文件当作单一角色日志。判断依据：
- 最近修改；
- 低等级；
- journey中包含任务8325、8326等逐日岛任务；
- 时间戳属于2026年本次游玩。

导出为 journey-current-sanitized.json，仅保留：
- quest_id
- event（Accept/Complete/Abandon）
- timestamp
- level
- 原始事件顺序index
- complete任务ID集合

删除账号名、服务器名、角色名、`profileKeys`、角色键、GUID和所有其他配置。
将文件放到bridge目录。
如果找不到2026年的记录，列出每个候选角色条目的最新时间、最低/最高等级和是否包含8325，但仍不得输出角色名或角色键。
```

3. 把生成的 `journey-current-sanitized.json` 放到bridge目录并告知ChatGPT。

## 工作区内直接解析原文件

如果原始`Questie.lua`已经放到工作区根目录的`.ai-bridge/`，可在`wow-quest-route`项目根目录执行：

```bash
python -m scripts.analyze_questie_journey ../.ai-bridge/Questie.lua --preview 40 --latest-only
```

该命令会：

- 从账号级`QuestieConfig.char[*].journey`中按最新时间定位当前候选角色；
- 输出事件数量、等级范围、当前在途任务、最近完成任务和末尾事件；
- 不输出账号名、服务器名、角色名、GUID或角色键；
- 容忍SavedVariables中的少量非UTF-8文本字节，替换异常文本但保留任务ID、等级和时间戳结构。

原文件仍只作为临时只读输入，不提交到项目仓库。

## 直接提供原文件的风险

账号级 `Questie.lua` 通常不含密码或Token，但可能包含：
- 账号内部目录名；
- 服务器名与角色名；
- 多个角色的历程和配置；
- 社交或共享设置。

因此优先上传脱敏JSON，而不是完整WTF或完整Questie.lua。

## 人物历程的局限

- `Accept`记录接取；
- `Complete`通常对应完成/交付时事件，不能提供移动轨迹；
- 不记录怪物击杀或拾取过程中的实时进度；
- 不记录坐标、道路和跟随卡点。

所以人物历程用于验证“顺序”，实测截图或一句文字用于验证“为什么绕路”。
