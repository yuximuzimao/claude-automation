param(
    [string]$GameRoot = "C:\Program Files (x86)\World of Warcraft\_classic_titan_"
)

$ErrorActionPreference = "Stop"
$source = Join-Path $PSScriptRoot "..\addon\WoWRouteLogger"
$targetRoot = Join-Path $GameRoot "Interface\AddOns"
$target = Join-Path $targetRoot "WoWRouteLogger"

if (-not (Test-Path -LiteralPath $source)) {
    throw "安装包中缺少插件目录：$source"
}
if (-not (Test-Path -LiteralPath $targetRoot)) {
    throw "找不到游戏插件目录：$targetRoot"
}

if (Test-Path -LiteralPath $target) {
    Remove-Item -LiteralPath $target -Recurse -Force
}
Copy-Item -LiteralPath $source -Destination $target -Recurse -Force
Write-Host "已安装：$target"
Write-Host "启动游戏后输入 /wrl status 验证。"
