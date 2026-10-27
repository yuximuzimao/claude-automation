# 个人资料 / 职业档案 SKILL.md

## DO FIRST

1. 读 `tasks/todo.md`。
2. 读 `docs/INDEX.md`。
3. 修改当前简历或求职方向时，读 `docs/CURRENT.md`。
4. 需要核对经历、数字、工具能力时，读 `docs/career-profile.md`。
5. 涉及措辞、取舍、版式时，读 `docs/resume-style.md`。
6. 需要基于现版继续修改时，读 `docs/current-resume.md`。

本项目没有代码入口；核心产物是职业事实与简历文本。

## ENTRY MAP

| 文件 | 用途 | 何时读 |
| --- | --- | --- |
| `docs/career-profile.md` | 职业事实唯一真值 | 核对经历、数字、工具能力 |
| `docs/resume-style.md` | 简历表达与排版原则 | 写简历、改措辞、排版 |
| `docs/current-resume.md` | 当前现役简历正文 | 继续修改、导出 PDF / Word |
| `docs/CURRENT.md` | 当前求职与在线简历状态 | BOSS、求职方向、当前版本 |
| `tasks/todo.md` | 尚未完成事项唯一台账 | 每次启动 |
| `docs/archive/` | 已结束阶段与 NEAT 历史 | 需要追溯决策时 |

## CORE FLOWS

### 更新个人职业事实
先改 `docs/career-profile.md`。如果新事实会影响当前简历，再同步修改 `docs/current-resume.md`。

### 修改简历
先读 `docs/resume-style.md` + `docs/current-resume.md`，需要核实内容时回到 `docs/career-profile.md`。不得为了版式自行删掉真实工作经历。

### 针对岗位投递
真实 JD 可以改变当次投递版的关键词与顺序，但不能改变 `docs/career-profile.md` 中的事实。岗位定制优先改 2–3 处相关措辞，不把主简历改成与真实经历不符的传统产品经理、程序员或 RPA 开发。

### 导出
PDF / Word 放 `exports/` 或用户指定的 Documents / Downloads。项目内 `exports/` 默认不进 Git。

## FAILURE PATTERNS

- 不编造效率、节省成本、准确率、GMV、技术栈或项目职责。
- 不主动解释“我不是什么”“我不会什么”；简历只写做过什么、规模多大、如何处理。
- 不把 RPA 写成专业开发能力；但也不在公开简历里主动加“基础”“不会 Python”等自我降级标签。
- 不用“赋能、闭环、抓手、重构、沉淀方法论、全链路”等空泛词替代真实业务。
- 不为了强行压成一页删减历史经历；当前接受两页 A4。
- 不把游戏或纯兴趣自动化默认写进职业简历。

## PATHS

- 职业事实：`docs/career-profile.md`
- 表达规则：`docs/resume-style.md`
- 当前简历：`docs/current-resume.md`
- 当前状态：`docs/CURRENT.md`
- 历史：`docs/archive/`
- 私人联系方式：`private/`（本地，不入 Git）
- 导出文件：`exports/`（本地，不入 Git）
