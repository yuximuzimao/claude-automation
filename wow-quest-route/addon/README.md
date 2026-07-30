# WoW Route Logger

只记录任务事件和移动坐标，不进行自动操作。

## 安装

完全退出游戏后运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\Install-WoWRouteLogger.ps1
```

或者把`addon\WoWRouteLogger`复制到：

```text
C:\Program Files (x86)\World of Warcraft\_classic_titan_\Interface\AddOns\WoWRouteLogger
```

进入游戏输入`/wrl status`验证。

## 命令

- `/wrl status`：查看当前会话事件数和轨迹点数；
- `/wrl checkpoint`：手工记录当前位置；
- `/wrl note 备注`：记录异常说明。

日志保存到每个角色自己的：

```text
WTF\Account\...\服务器\角色\SavedVariables\WoWRouteLogger.lua
```

不在日志内容中保存角色名、服务器名、账号名或GUID。保留最近30天、最多100个会话。
