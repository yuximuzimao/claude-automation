# Mac 提醒事项接入与排查

新增、维护任何项目的提醒时先读本页。跨项目长期约定的唯一来源是 [/Users/chat/AGENTS.md](/Users/chat/AGENTS.md) 的「提醒与通知」；本页维护现有快捷指令的接入协议和排查方法。

## 当前入口

发送端把待办写入共享输入文件，再运行「创建提醒」快捷指令，由快捷指令写入 Mac 提醒事项。

| 对象 | 位置或入口 |
|---|---|
| 快捷指令 | `创建提醒` |
| 共享输入文件 | `/Users/chat/WorkBuddy/小爪/data/input.txt` |
| 售后发送函数 | [`createReminder()`](../aftersales-automation/lib/helpers.js) |
| 小爪场景流程 | [`CODEBUDDY.md`](/Users/chat/WorkBuddy/小爪/CODEBUDDY.md) |

售后新增提醒统一调用 `createReminder()`。小爪按自身场景流程写入同一文件并执行快捷指令。新增项目复用这套输入协议和快捷指令，并在自己的入口文档登记发送入口。

## 输入协议

输入使用 UTF-8 单行文本，标题和时间之间只有一个全角竖线 `｜`：

```text
标题｜YYYY-MM-DD HH:mm
```

时间按 Mac 本地时间解释。标题本身不要包含全角竖线；售后发送函数会将标题中的全角竖线替换为半角竖线。

- 售后默认设置为创建时刻约五分钟后提醒，具体实现以 `lib/helpers.js` 为准。
- 小爪普通待办按用户指定的日期和时间处理；无日期、打卡及周期任务的行为由其 `CODEBUDDY.md` 定义，不套用售后的五分钟默认值。
- 同一共享输入文件的写入和快捷指令执行必须串行，多条提醒不能并发覆盖输入。
- 更改输入文件位置时，核对快捷指令的「文件」动作、售后 `SHORTCUT_INPUT_PATH` 和小爪流程，三者必须一致。

## 发送结果

`shortcuts run "创建提醒"` 是现有执行入口。售后 `createReminder()` 在快捷指令退出码为 0 时返回 `true`，写文件或执行失败时返回 `false`。CLI 据此报告结果；新增或维护业务提醒的调用方应检查返回值并记录发送失败，不得声称失败的提醒已创建。

排查或人工发送时，写入后先读回输入文件；发送后需要确认实际落地时，读回对应提醒的标题和提醒时间。只找到同名快捷指令、只看到进程启动，均不能证明待办已经创建。

## 终端调用与读回

独立项目没有售后发送封装时，使用Agent的终端工具执行Python写共享文件，再串行运行现有快捷指令。输入标题/时间由当前业务已确认事实提供；不要为验证流程创建真实测试提醒。以下是调用结构，必须先替换占位输入，未替换会在格式校验阶段停止：

```sh
python3.13 - <<'PY'
from pathlib import Path
from datetime import datetime
import subprocess
payload = '替换为实际标题｜YYYY-MM-DD HH:mm'
assert payload.count('｜') == 1 and '\n' not in payload and '\r' not in payload
title, when = payload.split('｜')
assert title.strip()
datetime.strptime(when, '%Y-%m-%d %H:%M')
path = Path('/Users/chat/WorkBuddy/小爪/data/input.txt')
path.write_text(payload + '\n', encoding='utf-8')
assert path.read_text(encoding='utf-8').rstrip('\n') == payload
result = subprocess.run(['shortcuts', 'run', '创建提醒'], capture_output=True, text=True)
print(result.stdout)
if result.returncode:
    raise RuntimeError(result.stderr or f'shortcuts exit={result.returncode}')
PY
```

当前快捷指令成功输出可包含VTODO/VCALENDAR。调用方从**本次返回原文**核对SUMMARY标题、DTSTART/DUE本地日期时间与TZID（或带Z时间换算），保存UID作为已创建证据；不要只看进程退出0。具体业务若要求落地核验，标题/时间/时区均一致才记“已创建并核验”。

返回0但无可核验对象时记录“发送成功、落地未核验”，不是再次创建的理由；非0也可能已经部分写入，不能直接重复发送。本页没有统一的提醒事项只读查询CLI：输出缺失/不一致时保留共享输入和本次输出，报告需人工核查或补查询入口，不切换系统通知、不猜已创建、不自动重试。该限制不影响已经返回完整且匹配VTODO的正常调用。

## 排查顺序

| 现象 | 检查与处理 |
|---|---|
| 找不到「创建提醒」 | 先用 `shortcuts list` 核对名称，再检查本机快捷指令配置 |
| 输入文件不存在或无法写入 | 对照本页和快捷指令的「文件」动作核对当前路径；旧 QClaw 目录已退出使用 |
| 输入格式或时间不对 | 读回文件，确认单行、一个全角竖线、日期时间和本机时区 |
| 命令返回失败 | 查看调用方日志或错误状态并明确反馈；修复后先核对是否已存在同条提醒，避免重复创建 |
| 提醒重复或内容被覆盖 | 检查调用方是否重复发送、是否并发写入同一文件；售后的汇总和去重仍归业务流程负责 |
| 售后 ERP 异常 | 查项目 [`docs/ops-erp.md`](../aftersales-automation/docs/ops-erp.md)；提醒内容不等于账号已经失效 |

售后提醒回归与生产数据隔离见 [`docs/ops-testing.md §6`](../aftersales-automation/docs/ops-testing.md#6-提醒事项回归)。单元测试使用模拟发送，不创建真实待办。
