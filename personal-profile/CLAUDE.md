# 个人资料 / 职业档案

项目中文名：个人资料 / 职业档案

## Session 启动

1. 读 `SKILL.md`
2. 读 `tasks/todo.md`
3. 读 `docs/INDEX.md`
4. 按任务进入 `docs/CURRENT.md`、`docs/career-profile.md`、`docs/resume-style.md` 或 `docs/current-resume.md`

## 稳定目标与边界

- 长期维护真实职业信息和现役简历，不依赖聊天记忆恢复。
- 职业事实只能来自用户确认、已有简历或可核验资料；不得为了匹配 JD 补写未做过的职责。
- 业务经历是主线，AI / 自动化是后来增加的工作方式和能力，不把用户包装成传统程序员或专业 RPA 开发。
- 简历只陈述事实、动作、规模和结果，不主动写能力边界辩解、自我降级或宣言式自我评价。
- 不因追求一页版式压缩掉真实工作经历。
- 联系方式、证件、账号等个人隐私不进入版本化文档；本地私人数据放 `private/`。
- PDF / Word 是导出物，放 `exports/` 或用户指定目录，不作为职业事实唯一真值。

## Owner

| 文档 | 唯一职责 |
| --- | --- |
| `docs/career-profile.md` | 已确认职业事实 |
| `docs/resume-style.md` | 简历表达、取舍、排版原则 |
| `docs/current-resume.md` | 当前现役简历正文 |
| `docs/CURRENT.md` | 当前求职方向、BOSS 状态、现役版本 |
| `tasks/todo.md` | 尚未完成事项 |
| `docs/archive/` | 已结束阶段与历史决策 |

## Git / 隐私边界

- `private/`、`exports/` 不进入 Git。
- 不保存身份证、账号密码、Cookie、银行卡等敏感信息。
- 当前职业事实和简历正文可以版本化；联系方式由本地私有文件在导出时补入。
