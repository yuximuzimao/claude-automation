# 操作工具与结果判定

本页只维护现役工具的调用契约；做哪项动作由[操作SOP](operation-sop.md)决定，当前批次/授权见CURRENT。以下命令的工作目录统一为 `/Users/chat/claude/qq-classic-farm`，通过当前Agent的终端执行工具调用（Codex为`functions.exec → tools.exec_command`）。命令中的占位参数必须从指定来源取得，不照抄占位词。

## 1. 使用前提

- Python入口统一使用`python3.13`。本页`--execute`命令有实际操作，仅在对应授权与前置状态满足时调用。阅读SOP、检查参数或文档审计不执行这些命令。
- `--check-plan`才是明确离线校验。不要笼统把“不带--execute”称为完全离线：部分预检仍查窗口/截图；下表区分它们。
- Swift辅助程序缺失时先按[README构建清单](../README.md#独立操作脚本)编译。报编译/依赖错误时停在准备阶段，不改用通用桌面工具临时拼动作。
- 返回码非0先保留完整JSON/标准错误和已完成步骤，并按工具契约分类。farm_process时间查询的allowed_start=false加next_allowed_start是正常否定结果，未来排期按automation-trial继续选择时间；不能因此中断已经完成种植后的收尾。动作失败/工具自身异常才走停止分支。返回0也要区分预检、跳过与真正执行；`plan_ok_no_click`不等于已种植，`skipped_no_planting`不能扣种子。
- 页面动作由已有脚本内部完成；正常退出按项目口径记完成，不加每步截图。异常诊断才用第4节。平台封存与业务授权不由工具预检替代。

## 2. 开关、首页与田内入口

先定义实际参数：`PLANTED`为CURRENT登记的已校验完整实种文件绝对路径；`FIELD`为按当前实种与当前时间判定的`tail/mature/empty`；`ROUNDS`为当天尚未成功完成的萝卜轮数0–5。执行工具在每条命令返回后检查结果，不把下表整段当成批处理顺序。

| 操作 | 具体调用 | 成功证据/限制 |
| --- | --- | --- |
| 读取窗口 | `./_sandbox/farm_window_registry --platform qq` | 只读；JSON.platform=qq、windows提供当前身份和几何。枚举成功不等于页面可操作 |
| 打开QQ农场 | `python3.13 scripts/farm_window.py open --platform qq --execute` | 返回0且status为`farm_opened`或`farm_window_already_present`；之后仍须首页检查 |
| 开工首页准备 | `python3.13 scripts/farm_home_check.py --live --prepare` | 返回0、ready_for_input=true；激活已有农场、等待5秒、截图检查，不点田内 |
| 关闭QQ农场 | `python3.13 scripts/farm_window.py close --platform qq --execute` | 返回0且`farm_closed`，脚本已回读窗口消失；安全关闭边界见第4节 |
| 整轮收种 | `python3.13 scripts/farm_qq_round.py --field-state "$FIELD" --radish-rounds "$ROUNDS" --harvest-plan "$PLANTED" --execute` | `qq_round_actions_sent`及completed_stages；QQ专用，无--platform。空田省略--harvest-plan。不传--tasks/--friends/--reward做例行日常 |
| 只执行正式种植 | `python3.13 scripts/farm_plant_once.py --platform qq --execute` | 输入唯一data/operation-plan.json；`planting_clicks_sent_unverified`才表示实际发送种植动作，skipped不算种植 |
| 普通肥一次 | `python3.13 scripts/farm_fertilize_once.py --platform qq --kind ordinary --execute` | `fertilizer_click_sent`；内部含必要的一键务农/勾选处理，不另点务农。只有符合SOP阶段/当季条件才调用 |
| QQ有机肥一次 | `python3.13 scripts/farm_fertilize_once.py --platform qq --kind organic --execute` | 同上；用于萝卜循环或操作SOP§2已授权的提前一阶段双肥，不额外增加次数 |
| 按实种收获 | `python3.13 scripts/farm_harvest_once.py --platform qq --planted-plan "$PLANTED" --mature-confirmed --execute` | `harvest_click_sent_unverified`；mature-confirmed表示调用方已核实成熟或施肥成功后等待2.2秒，不是绕过前置的通用开关 |
| 纯普通田收获 | `python3.13 scripts/farm_harvest_once.py --platform qq --ordinary-only --execute` | 同上；只有明确没有四格且已成熟才用，不能省略实种记录来猜普通田 |
| 萝卜剩余轮数 | `python3.13 scripts/farm_radish_xp.py --rounds "$ROUNDS" --execute` | 独立入口只接受1–5，0轮直接跳过；`radish_rounds_sent`，读取completed_rounds/daily_completed_rounds/seeds_consumed和计数文件，不按请求轮数盲记成功 |
| 萝卜月度补货 | `python3.13 scripts/farm_radish_restock.py --purchases 37 --execute` | `radish_restock_clicks_sent`、completed_purchases及quantity_each；默认37×99。失败结果不保证含已购次数，不能估计部分数量后重跑 |
| 校验下一批计划 | `python3.13 scripts/farm_plant_once.py --platform qq --check-plan` | 离线，`plan_ok_no_click`；只证明现有解析/布局约束通过，不证明库存、种子名称、真实picker或单一种子数量正确，补充核对见操作SOP§4 |
| 校验完整实种记录 | `python3.13 scripts/farm_harvest_once.py --platform qq --planted-plan "$PLANTED" --check-plan` | 离线，`planted_record_ok_no_click`；记录必须是已完成事实，不能以未来计划冒充 |

整轮脚本只做田内动作；它不自动写完整实种文件、不扣JSON库存、不发提醒、不检查仓鼠、不关闭小程序，也不续排任务。这些由Agent按操作SOP及各owner接续；缺一项不能称完整收尾。

### QQ前台准备（必须先于开农场）

适用前提：QQ应用已经运行、用户已授权本轮操作、启动时间检查允许，且没有已知的其它任务正在使用桌面。不得因为QQ不在前台就要求用户手动切换。

| 当前情况 | 固定操作 |
| --- | --- |
| QQ已运行，但没有窗口显示在当前桌面（例如隐藏或最小化） | 执行下面的应用级恢复/激活命令；不依赖可见窗口取PID，不点击Dock或侧边缩略图 |
| QQ窗口在桌面，但不是最前面的应用 | 同样执行下面的命令，把QQ切到前台；不直接点击被遮挡的农场入口 |

两种情况使用同一入口，不需要模型猜测当前属于哪一种。通过终端执行一次：

```sh
osascript -e 'if application "/Applications/QQ.app" is not running then error "QQ_NOT_RUNNING"' -e 'tell application "/Applications/QQ.app" to activate'
```

该命令先确认QQ正在运行，再请求系统激活QQ；不模拟账号内点击，不启动登录流程。命令非0立即停止，不自动重试；QQ未运行时交用户打开并完成登录。返回0只证明激活请求已发出，不证明农场可以操作。

随后串行调用本节表中的开窗命令，再调用首页prepare；必须检查每条返回结果。开窗脚本会按已核实PID再次激活并等待5秒，然后检查入口窗口、前台和遮挡；只有开窗成功且首页prepare返回`ready_for_input=true`才进入田内。应用激活后若窗口仍无法恢复，或出现`QQ_PROCESS_NOT_UNIQUE`、窗口/遮挡异常、登录/安全提示，立即停止，不重复激活、不重开、不猜坐标。命令成功不得绕过后续检查。

## 3. 日常与仓鼠入口

各项先依据CURRENT当天完成记录决定是否调用；固定日常顺序见操作SOP。没有统一--platform约定，不从一个脚本类推另一个。

| 操作 | 具体调用 | 完成判定与失败边界 |
| --- | --- | --- |
| 免费化肥 | `python3.13 scripts/farm_daily_fertilizer_reward.py --platform qq --execute` | `daily_clicks_sent_unverified`、clicks_sent；脚本为固定点击链，没有独立额度/回首页视觉读回，不宣称它已识别“今日已领” |
| 首次分享并领奖 | `python3.13 scripts/farm_share_once.py --execute` | `share_actions_sent_unverified`、completed_steps；脚本含领取文字/奖励识别。正常流程是否自然验收完成见Todo |
| 已发送只补领取 | `python3.13 scripts/farm_share_once.py --claim-only --execute` | 只限已确认发送、领取中断的情况，从正常首页开始；检查completed_steps，不能把仅领取当新发送 |
| 好友全扫 | `python3.13 scripts/farm_friend_sweep.py --platform qq --execute` | 返回0、`return_home_click_sent`、reason=no_action；`stopped_return_home_click_sent`或非0不是扫完，不重放已完成交互 |
| 种草/放虫 | `python3.13 scripts/farm_mischief_once.py --execute` | 返回0、status=completed、reason=shared_quota_exhausted、shared_remaining=0；具体流程与识别边界见[mischief](mischief.md)。stopped_returned_home只表示停止后已发返回动作 |
| 每日任务独立请求 | `python3.13 scripts/farm_daily_task_once.py --platform qq --execute` | `daily_clicks_sent_unverified`；仅用户单独请求且前置已满足。固定好友互动与领取点击，不是动态任务书OCR读取工具，不用于确认全部任务状态 |
| 本轮末尾仓鼠 | `python3.13 scripts/farm_hamster_once.py --platform qq --execute` | `hamster_not_detected`表示未买；`merchant_reward_seen_dismiss_clicked`且inventory_refresh_required=true必须转库存核对。脚本不识别所获商品/数量、不更新seed-catalog |

分享失败先看send_attempted与completed_steps；send_attempted=true表示已尝试发送，不能因后续失败重发。以上失败均停止后续业务动作，按第4节处理退出；不得把所有失败一律等同于“完全没操作”。

## 4. 异常看图与安全退出

**已具备的项目入口优先使用，不以`cua.getState()`发现桌面作为例行前置。** 查询当前窗口用第2节registry；恢复现有农场用`farm_home_check.py --live --prepare`。需要看图时，用本节限定窗口截图，再用当前Agent的图片查看工具（Codex为`functions.exec → tools.view_image`）读取绝对路径图片。通用界面工具超时不证明这些本地工具失效；禁止重复超时调用，也不在未知画面上接续业务动作。

以下为异常取证的只读调用配方，已静态核对现役函数接口与Python语法，本轮未在真机执行；它不是自动盘点脚本；它不打开仓库、不翻页、不点任何按钮。窗口助手先确认身份/焦点/遮挡，拍摄前后再次比对窗口。截图可以是仓库或其它面板，不要求画面通过首页视觉分类。

```sh
python3.13 - <<'PY'
import json, subprocess
from pathlib import Path
from datetime import datetime
import sys
sys.path.insert(0, str(Path.cwd() / 'scripts'))
from farm_capture import capture_window
from farm_geometry import WindowFrame
from PIL import Image

def probe():
    p = subprocess.run(['./_sandbox/farm_home_window', '--check'],
                       capture_output=True, text=True, timeout=10, check=True)
    state = json.loads(p.stdout)
    if state['state'] != 'window_ready':
        raise ValueError(state)
    return state
before = probe()
layout = json.loads(Path('data/ui-layout.json').read_text())
frame = WindowFrame(before['owner'], before['title'], **before['frame'])
shot = capture_window(frame, 'qq', layout)
if probe() != before:
    raise ValueError('WINDOW_CHANGED_DURING_CAPTURE')
out = Path('../_sandbox') / ('qq-farm-diagnostic-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.png')
Image.fromarray(shot.rgb).save(out)
print(out.resolve())
PY
```

截图失败记录具体错误，不以历史图片代替当前画面。看图只是证据，不代表已有对应恢复动作。通用遮罩关闭、任意弹窗取消、移动窗口到空白区域目前没有统一已验收脚本；见Todo，不能把“先关闭/先移动”当作已有自动步骤，更不能猜坐标点空白。

安全退出：停止后不继续收种；若registry显示没有农场，记录已关闭；若仍存在且能确认标准窗口和标题栏关闭控件可用，使用第2节close一次，以farm_closed收尾。缩略窗原因已核清时先用已有prepare恢复，再关闭。身份不明、登录/安全提示、遮挡、关闭失败时不再试点，报告“窗口仍开/关闭未核实”。不能因为只读工具失败就直接宣称窗口关闭，也不为关闭而重跑开场/业务链。

## 5. 库存核对入口

现役完整调用见[库存核对SOP](inventory-sop.md)：`python3.13 scripts/farm_inventory.py capture --execute`从首页进入仓库、完整截图并回首页；Agent用`tools.view_image`逐张读取，写完整observations后调用`farm_inventory.py apply --manifest ... --observations ... --execute`校验并回写。不是单靠脚本自动OCR，不能省略读图。

该入口已完成两种起始状态的现场验收和数量回写；原基础工具由脚本内部复用，不再让定时Agent现拼点击/拖动。真正未建档新品、看不清数字、无法确认重叠时仍停止补证，不猜数量或套类别。完整参数、pending处理、成功字段及限制以inventory-sop为唯一owner。
