param(
    [string]$GameRoot = "C:\Program Files (x86)\World of Warcraft\_classic_titan_",
    [Parameter(Mandatory = $true)]
    [string]$BridgePath,
    [datetime]$Since = (Get-Date).Date
)

$ErrorActionPreference = "Stop"
$accountRoot = Join-Path $GameRoot "WTF\Account"
if (-not (Test-Path -LiteralPath $accountRoot)) {
    throw "找不到WTF账号目录：$accountRoot"
}
if (-not (Test-Path -LiteralPath $BridgePath)) {
    New-Item -ItemType Directory -Path $BridgePath -Force | Out-Null
}

$files = Get-ChildItem -LiteralPath $accountRoot -Recurse -Filter "WoWRouteLogger.lua" -File |
    Where-Object { $_.FullName -match "\\SavedVariables\\WoWRouteLogger\.lua$" -and $_.LastWriteTime -ge $Since } |
    Sort-Object LastWriteTime

if (-not $files) {
    throw "没有找到从 $($Since.ToString('yyyy-MM-dd HH:mm')) 起更新的WoWRouteLogger.lua。请先完全退出游戏或输入/reload。"
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$temp = Join-Path ([System.IO.Path]::GetTempPath()) "wow-route-log-$timestamp"
New-Item -ItemType Directory -Path $temp -Force | Out-Null

$manifest = @()
$index = 0
foreach ($file in $files) {
    $index++
    $pathBytes = [System.Text.Encoding]::UTF8.GetBytes($file.FullName.ToLowerInvariant())
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hash = ([BitConverter]::ToString($sha.ComputeHash($pathBytes))).Replace("-", "").Substring(0, 10).ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
    $anonymousName = "profile-{0:D2}-{1}.lua" -f $index, $hash
    Copy-Item -LiteralPath $file.FullName -Destination (Join-Path $temp $anonymousName)
    $manifest += [ordered]@{
        profile_id = "P{0:D2}-{1}" -f $index, $hash
        file = $anonymousName
        modified_at = $file.LastWriteTime.ToString("o")
        bytes = $file.Length
    }
}

$manifestObject = [ordered]@{
    schema_version = 1
    exported_at = (Get-Date).ToString("o")
    since = $Since.ToString("o")
    profile_count = $manifest.Count
    profiles = $manifest
    privacy = "文件名和清单不包含账号、服务器或角色名称；profile_id由本机完整路径哈希生成。"
}
$manifestObject | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $temp "manifest.json") -Encoding UTF8

$zipPath = Join-Path $BridgePath "wow-route-log-$timestamp.zip"
Compress-Archive -Path (Join-Path $temp "*") -DestinationPath $zipPath -Force
Remove-Item -LiteralPath $temp -Recurse -Force

Write-Host "已导出 $($manifest.Count) 个角色日志："
Write-Host $zipPath
