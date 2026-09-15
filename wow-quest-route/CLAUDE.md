# 魔兽世界任务路线

项目中文名：魔兽世界五开打金任务路线

## 项目第一目标

把“任务路线”作为独立打金方式做成可长期复用的高净金币 / 玩家真实墙钟系统。升级、80级后一次性任务清理、Task Card、Route Profile和Route Atlas页面都只服务这个目标。

## 稳定纪律

- 当前等级、地图、任务栏和暂停状态只看`docs/verified-routes/CURRENT.md`，不复制到稳定入口。
- 用户当前服务器实测优先于旧模型/历史页面，但只修改实测真正证明的字段。
- 未受影响的已验证/可复用部分默认冻结；发现其它问题先报告或记todo，不自动扩大修改。
- Task Card、Rule Docs、Route Profile、CURRENT、Generated Product职责分离，禁止同一事实/决策双写成两份可独立演化真源。
- HTML、workbench聚合JSON和其它生成结果不能反向成为业务真源。
- archive、ERROR-BOOK只用于定向考古，不覆盖当前真源。
- Questie/WTF为只读输入；不提交账号、角色、GUID、登录信息等敏感数据。

## Session入口

1. 先读`SKILL.md`。
2. 再读`tasks/todo.md`。
3. 文件位置只查`docs/INDEX.md`。
4. 永久规则只从`docs/rules/README.md`进入对应唯一owner。
5. 当前实跑只读`docs/verified-routes/CURRENT.md`。
6. 新建、修订、实跑写回、发布、架构迁移按`docs/verified-routes/ROUTE-DESIGN-PROCESS.md`分支执行。

禁止为了局部问题一次性加载全部rules、全部Task Card、ERROR-BOOK或archive。

## 历史与Git边界

- `/sessions/`是运行时敏感目录，必须Git忽略。
- 项目历史统一放`docs/archive/`并正常版本化；archive只是退出默认读取范围。
- NEAT、Git操作、测试选择和脚本登记分别按对应技能/README执行，本文件不复制详细流程。

## 一句话边界

**本文件是项目宪章，不是业务规则目录。具体怎么计算、怎么排路线、怎么显示、怎么测试，一律进入`docs/rules/README.md`登记的唯一owner或对应流程入口。**
