#Requires -Version 5.1
<#
    s.p.l.i.t 简体中文汉化安装器
    选择正版 split.exe，基于随包 payload.zip 生成汉化版并安全安装。
#>
[CmdletBinding()]
param(
    [string]$GameDir = 'C:\Program Files (x86)\Steam\steamapps\common\s.p.l.i.t\split_Windows',
    [string]$ExePath
)
$ErrorActionPreference = 'Stop'
$ExpectedOrigSha = '2F5E7E3EC06E1E3ECA3623E75DF65DE342DC39E21B886B59BA5D455BC752C9F6'
$ExpectedOrigLen = 407187680
$Payload = Join-Path $PSScriptRoot 'payload.zip'
$Patcher = Join-Path $PSScriptRoot 'apply_patch.py'
$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) { throw '未检测到 Python 3，请先安装 Python 3.8 或更新版本。' }
if (-not (Test-Path -LiteralPath $Payload)) { throw "找不到 payload.zip: $Payload" }
if (-not $ExePath) {
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.OpenFileDialog
    $dialog.Title = '选择 Steam 正版游戏目录中的 split.exe'
    $dialog.Filter = '游戏程序 (split.exe)|split.exe|所有文件 (*.*)|*.*'
    $dialog.FileName = 'split.exe'
    if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { throw '已取消选择原版 split.exe。' }
    $ExePath = $dialog.FileName
}
$ExePath = (Resolve-Path -LiteralPath $ExePath).Path
$Original = Get-Item -LiteralPath $ExePath
if ($Original.Name -ne 'split.exe') { throw '请选择原版 split.exe 文件。' }
$OrigSha = (Get-FileHash -LiteralPath $ExePath -Algorithm SHA256).Hash.ToUpperInvariant()
if ($Original.Length -ne $ExpectedOrigLen -or $OrigSha -ne $ExpectedOrigSha) {
    throw "原版校验失败，未修改游戏文件。大小=$($Original.Length)，SHA256=$OrigSha"
}
$GameDir = (Resolve-Path -LiteralPath $GameDir -ErrorAction SilentlyContinue).Path
if (-not $GameDir) { $GameDir = Split-Path -Parent $ExePath }
$Target = Join-Path $GameDir 'split.exe'
if ($Target -ne $ExePath) { throw '所选 split.exe 必须位于要安装的游戏目录；请调整 -GameDir 或重新选择文件。' }
if (@(Get-Process -Name split -ErrorAction SilentlyContinue).Count -gt 0) { throw '游戏正在运行，请退出游戏后重试。' }
$Backup = Join-Path $GameDir 'split.exe.orig.bak'
if (Test-Path -LiteralPath $Backup) {
    $bsha = (Get-FileHash -LiteralPath $Backup -Algorithm SHA256).Hash.ToUpperInvariant()
    if ($bsha -ne $ExpectedOrigSha) { throw "现有备份不是预期正版，拒绝覆盖：$Backup" }
} else {
    Copy-Item -LiteralPath $ExePath -Destination $Backup
    if ((Get-FileHash -LiteralPath $Backup -Algorithm SHA256).Hash.ToUpperInvariant() -ne $OrigSha) { throw '备份校验失败；游戏文件未覆盖。' }
}
$Built = Join-Path $GameDir 'split.exe.zh-new'
$Report = Join-Path $GameDir 'split-zh-build-report.txt'
& $Python.Source $Patcher --exe $ExePath --payload $Payload --out $Built --report $Report
if ($LASTEXITCODE -ne 0) { Remove-Item -LiteralPath $Built -Force -ErrorAction SilentlyContinue; throw "补丁构建失败，退出码 $LASTEXITCODE；原游戏文件未覆盖。查看 $Report" }
if (-not (Test-Path -LiteralPath $Built) -or -not (Select-String -LiteralPath $Report -Pattern '^VERDICT: PASS' -Quiet)) { Remove-Item -LiteralPath $Built -Force -ErrorAction SilentlyContinue; throw "应用器报告未通过验收；原游戏文件未覆盖。查看 $Report" }
$builtItem = Get-Item -LiteralPath $Built
$builtSha = (Get-FileHash -LiteralPath $Built -Algorithm SHA256).Hash.ToUpperInvariant()
if ($builtItem.Length -le $ExpectedOrigLen -or $builtSha -eq $OrigSha) { Remove-Item -LiteralPath $Built -Force; throw "构建结果不合理：$($builtItem.Length) / $builtSha；原游戏文件未覆盖。" }
$Temp = Join-Path $GameDir 'split.exe.zh-installing'
Move-Item -LiteralPath $Built -Destination $Temp -Force
try {
    Copy-Item -LiteralPath $Temp -Destination $Target -Force
    $installedSha = (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash.ToUpperInvariant()
    if ($installedSha -ne $ExpectedPatchedSha -or (Get-Item -LiteralPath $Target).Length -ne $ExpectedPatchedLen) { throw '安装后校验失败。' }
} catch {
    Copy-Item -LiteralPath $Backup -Destination $Target -Force
    throw "安装失败，已从原版备份回滚。$($_.Exception.Message)"
} finally {
    Remove-Item -LiteralPath $Temp -Force -ErrorAction SilentlyContinue
}
Write-Host "汉化安装完成。SHA256: $installedSha"
Write-Host "原版备份保留于: $Backup"
