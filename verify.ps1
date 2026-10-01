#Requires -Version 5.1
[CmdletBinding()]
param([string]$GameDir = 'C:\Program Files (x86)\Steam\steamapps\common\s.p.l.i.t\split_Windows')
$ErrorActionPreference = 'Stop'
$target = Join-Path $GameDir 'split.exe'
$receiptPath = Join-Path $GameDir 'split-zh-install.json'
if (-not (Test-Path -LiteralPath $target)) { throw "找不到 split.exe: $target" }
if (-not (Test-Path -LiteralPath $receiptPath)) { throw '找不到 split-zh-install.json；该目录可能不是由此安装器管理。' }
$receipt = Get-Content -LiteralPath $receiptPath -Raw -Encoding UTF8 | ConvertFrom-Json
$len = (Get-Item -LiteralPath $target).Length
$sha = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToUpperInvariant()
Write-Host "split.exe: $len 字节 / $sha"
if ($len -ne [long]$receipt.installed_length -or $sha -ne $receipt.installed_sha256) { throw '安装文件与收据不一致，可能被 Steam 或其他 Mod 修改。' }
$backup = Join-Path $GameDir 'split.exe.orig.bak'
if (-not (Test-Path -LiteralPath $backup)) { throw '安装器收据存在但原版备份缺失。' }
$bsha = (Get-FileHash -LiteralPath $backup -Algorithm SHA256).Hash.ToUpperInvariant()
if ($bsha -ne $receipt.original_sha256) { throw '原版备份与收据不一致。' }
Write-Host '状态: 汉化安装与原版备份均通过收据校验。'
