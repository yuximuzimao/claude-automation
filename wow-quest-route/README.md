# 魔兽世界五开打金任务路线

面向国服泰坦重铸“时光”服的五开练级与任务打金路线项目。项目把单任务事实、正式路线、实跑状态、模型和玩家页面分开维护，最终提供可离线使用的Route Atlas执行页。

当前唯一正式执行页：

`data/routes/route-atlas-workbench.html`

地图资源位于同级`data/routes/maps/`。当前迁移中的候选页尚未替代这份正式页面。

## 从哪里开始

- Agent入口：`SKILL.md`
- 全部未完成事项：`tasks/todo.md`
- 文档与数据位置：`docs/INDEX.md`
- 当前实跑恢复点：`docs/verified-routes/CURRENT.md`
- Route Lifecycle分类SOP：`docs/verified-routes/ROUTE-DESIGN-PROCESS.md`

具体业务规则与正式操作从SOP进入对应唯一owner；README不复制规则、Todo或CURRENT。

## 安全与隐私

项目只离线读取用户提供的Questie/WTF等资料，不修改游戏文件，不注入客户端、不读内存、不抓包、不自动接交任务或广播输入。账号名、角色名、GUID、登录信息和原始运行时会话不得进入Git；历史材料统一进入`docs/archive/`并退出日常默认读取。
