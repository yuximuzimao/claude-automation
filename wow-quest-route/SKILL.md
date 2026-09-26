# 魔兽世界任务路线 SKILL.md

用途：沉淀本项目已经稳定的高频入口。这里只做低歧义一级分流；Route Lifecycle内部存在相似定义时一律交给SOP，不在Skill按关键词猜分支。

## DO FIRST

1. 读`tasks/todo.md`，确认当前未完成事项；不要默认加载历史。
2. 需要找文件时读`docs/INDEX.md`。
3. 涉及Task Card、Route Profile/Program、Observation、规则/模型、Route Atlas业务语义、发布或迁移的修改，进入`docs/verified-routes/ROUTE-DESIGN-PROCESS.md`分类。
4. SOP命中owner后，只读该owner及它明确要求的直接下游；实际操作方式就在对应owner中。
5. ERROR-BOOK与archive只按当前问题定向检索。

## 稳定快捷入口

### 继续当前实跑 / “下一步去哪”

只读`docs/verified-routes/CURRENT.md`。如果只是继续游戏，不加载Route Lifecycle全部规则；只有现场反馈需要写回长期事实、路线、Observation或规则时，才回SOP分类。

### DK职业/战斗配置

读`docs/verified-routes/DK-COMBAT-NOTES.md`。

### 视频拆解

读`docs/video-extraction/README.md`，需要恢复当前视频进度时再读`docs/video-extraction/CURRENT.md`。

### 测试与脚本盘点

- 已知改动需要选择验证范围：`tests/README.md`。
- 需要盘点“scripts目录里有什么”、退役或反向审计工具身份：`scripts/README.md`。
- 普通业务执行不从Scripts README挑脚本。

## 架构迁移

只有SOP分类为`ARCHITECTURE_MIGRATION`，或用户明确要求迁移/旧链退役，才读取对应迁移计划或历史。当前迁移历史：`docs/archive/analysis/2026-09-21-route-lifecycle-migration-history.md`；实时未完成事项仍只看`tasks/todo.md`。

每次新迁移按当次目标建立自己的计划，不复制旧迁移Stage模板。

## 项目边界

- 证据优先级及任务事实纠错只读Task Mechanics owner。
- 原始Questie/WTF/账号登录数据不提交；只保存必要的脱敏结构化结果。
