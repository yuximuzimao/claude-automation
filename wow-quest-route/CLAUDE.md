# 魔兽世界任务路线

项目中文名：魔兽世界五开打金任务路线

## 项目第一目标

把“任务路线”作为独立打金方式做成可长期复用的高净金币 / 玩家真实墙钟系统。升级、80级后一次性任务清理、Task Card、Route Profile和Route Atlas页面都只服务这个目标。

## Session入口

1. 先读`SKILL.md`。
2. 当前未完成工作只读`tasks/todo.md`。
3. 当前角色/实跑恢复点只读`docs/verified-routes/CURRENT.md`。
4. 涉及Route Lifecycle长期事实、路线、规则、页面、发布或迁移且存在业务分类判断时，进入`docs/verified-routes/ROUTE-DESIGN-PROCESS.md`。
5. 需要找文件只查`docs/INDEX.md`。

工作区级文档职责、渐进式披露、Todo唯一性和现役/历史二分只服从工作区根`/Users/chat/claude/CLAUDE.md`，本项目不复制第二套定义。

## 数据与Git边界

- `/sessions/`是运行时敏感目录，必须Git忽略。
- Questie/WTF为只读输入；不提交账号、角色、GUID、登录信息等敏感数据。
- 项目历史进入`docs/archive/`或明确日期化历史文档，并退出默认读取链。
- NEAT、Git操作、测试选择和脚本目录分别按对应技能/文档执行。
