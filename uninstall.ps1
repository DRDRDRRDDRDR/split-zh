#Requires -Version 5.1
[CmdletBinding()]
param([string]$GameDir = 'C:\Program Files (x86)\Steam\steamapps\common\s.p.l.i.t\split_Windows')
$ErrorActionPreference = 'Stop'
$target = Join-Path $GameDir 'split.exe'
$backup = Join-Path $GameDir 'split.exe.orig.bak'
$receiptPath = Join-Path $GameDir 'split-zh-install.json'
if (@(Get-Process -Name split -ErrorAction SilentlyContinue).Count -gt 0) { throw '游戏正在运行，请退出后重试。' }
if (-not (Test-Path -LiteralPath $receiptPath) -or -not (Test-Path -LiteralPath $backup) -or -not (Test-Path -LiteralPath $target)) { throw '安装收据、目标文件或原版备份缺失；拒绝盲目回滚。' }
$receipt = Get-Content -LiteralPath $receiptPath -Raw -Encoding UTF8 | ConvertFrom-Json
$currentLen = (Get-Item -LiteralPath $target).Length
$currentSha = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToUpperInvariant()
if ($currentLen -ne [long]$receipt.installed_length -or $currentSha -ne $receipt.installed_sha256) { throw '当前 split.exe 已不同于本安装器安装的文件；可能被 Steam/其他 Mod 更新，拒绝覆盖。' }
$backupSha = (Get-FileHash -LiteralPath $backup -Algorithm SHA256).Hash.ToUpperInvariant()
if ($backupSha -ne $receipt.original_sha256) { throw '备份哈希与安装收据不一致，拒绝回滚。' }
Copy-Item -LiteralPath $backup -Destination $target -Force
if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToUpperInvariant() -ne $backupSha) { throw '回滚后校验失败。' }
Remove-Item -LiteralPath $receiptPath -Force
Write-Host '已恢复收据记录的原版 split.exe；备份保留未删除。'
