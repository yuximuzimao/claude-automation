# QQ首页确认器

本工具判断当前画面是否适合沿用已确认的土地坐标开始操作，不判断作物种类、成熟度或库存。当前验收进度唯一见CURRENT/Todo；基础真机验收完成后用于操作SOP的开工前检查；失败时交Agent诊断，不继续执行田内脚本。

## 图片识别

入口：`scripts/farm_home_check.py --image <保存的窗口截图>`。只读取图片和本地模板，不查询窗口、不激活程序、不截图、不点击。

只接受603×1111逻辑像素或其2倍Retina截图；拒绝缩略图、整屏截图、微信画布与裁切尺寸。标准化后同时检查：

- QQ经典农场标题、首页分享及底部仓库/商店/图鉴等固定控件。
- 场景内“劳动光荣”标牌的位置。旧版或平移画面即使是自己的首页，也不能用于当前固定坐标；位置偏差超过4像素时拦下。
- 种植栏、施肥栏、作物操作面板、四格预览、奖励与分享等已知面板特征。
- 好友农场的返回入口、空白加载画面。

使用局部模板相关性加RGB绝对颜色差。相关性可以匹配变暗后的背景，不能单独用来判断首页可操作；颜色差用于防止弹窗下变暗的首页按钮被误认作正常状态。没有足够证据时返回`unknown_or_non_home`，不猜测或自动关弹窗。

模板与阈值唯一在 `data/home-recognition.json`，图片在 `assets/ui/home/`；配置记录模板来源截图和裁剪区域。依赖Python 3.13、Pillow、NumPy、OpenCV（本机已安装）。

## 真机入口

先编译窗口助手：

```sh
swiftc scripts/farm_home_window.swift -o _sandbox/farm_home_window
```

- `python3.13 scripts/farm_home_check.py --live`：只读检查当前窗口并截取一次，不改变焦点。
- `python3.13 scripts/farm_home_check.py --live --prepare`：只激活已存在且唯一的QQ农场进程，等待5秒，再检查和截图；不启动QQ、不登录、不点游戏控件。

窗口助手校验：唯一窗口、精确身份、标准尺寸、前台进程、前方其他窗口遮挡。侧边缩略窗可由`--prepare`激活恢复；恢复后仍不标准就停止。截图后再做一次只读窗口检查，身份/位置/尺寸变化则丢弃结果。已知Dock/通知中心透明整屏系统层采用项目现有特例，其余遮挡一律拒绝。

不会自动重试、关闭弹窗、返回首页或执行收菜种植；不接入后台调度。只对本次捕获给结论，不能缓存为下一次点击授权。

## 返回值

- `visual_ready`：图片是否满足当前首页坐标与面板条件。
- `ready_for_input`：只有真机模式同时通过窗口检查和图片检查时为true。离线图片即使识别通过也始终为false。
- `state`：`home`、`scene_misaligned`、`friend_farm`、`overlay`、`non_home`、`loading_or_blank`、`unknown_or_non_home`、`invalid_image_size`或`error`。
- `features`：局部相关分数、颜色误差和匹配位置，供离线诊断；不生成点击指令。
- 退出0表示本次模式的检查通过；退出2表示未通过。调用方不能只凭离线命令退出0执行真机动作。

没有真实登录/授权弹窗样本时，不声称能准确命名这种弹窗；不满足首页证据时仅拒绝放行。对未见过的局部遮罩和新版本UI，不承诺完整检出；新异常应补截图测试，不能降低门槛直接放行。

## 离线复验

`tests/home-screenshot-corpus.json`是人工核对的本地历史截图清单，保存文件SHA256、预期是否可用及模板来源/回归分组。它不参与运行时识别，也不代表当前田内状态。原始截图仍在工作区`_sandbox/`，不提交Git；缺失或被覆盖时复验明确失败，不静默跳过。

```sh
python3.13 tests/check_home_screenshots.py --report ../_sandbox/farm-home-offline/report.json
python3.13 -m pytest tests/test_home_check.py tests/test_capture_vision_m1.py -q
```

回归集参与了开发调试，不能作为完全未见过的独立测试集；重复文件与模板来源数量在报告中单独披露。旧版、场景偏移及裁切图片按“能否安全使用当前坐标”标注，不能只按“看起来是首页”标为通过。
