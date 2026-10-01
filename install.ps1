#Requires -Version 5.1
<#
    s.p.l.i.t 简体中文汉化安装器
    从发布包中提取 payload，以用户提供的正版 split.exe 构建并安装。
#>
[CmdletBinding()]
param(
    [string]$GameDir = 'C:\Program Files (x86)\Steam\steamapps\common\s.p.l.i.t\split_Windows',
    [string]$ExePath
)
$ErrorActionPreference = 'Stop'
$ExpectedOrigSha = '2F5E7E3EC06E1E3ECA3623E75DF65DE342DC39E21B886B59BA5D455BC752C9F6'
$ExpectedOrigLen = 407187680
$ExpectedPayloadSha = 'A1BE6695AB647E57543564B03C81D5D0449D4AE7602F2D09E94F5ED00144B1B6'
$ExpectedPayloadLen = 34101396
$Patcher = Join-Path $PSScriptRoot 'apply_patch.py'
$Payload = Join-Path $PSScriptRoot 'payload.zip'
$TempRoot = Join-Path ([IO.Path]::GetTempPath()) ('split-zh-' + [guid]::NewGuid().ToString('N'))
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
$ResolvedGameDir = Resolve-Path -LiteralPath $GameDir -ErrorAction SilentlyContinue
if ($ResolvedGameDir) { $GameDir = $ResolvedGameDir.Path } else { $GameDir = Split-Path -Parent $ExePath }
$Target = Join-Path $GameDir 'split.exe'
if ([IO.Path]::GetFullPath($Target) -ne [IO.Path]::GetFullPath($ExePath)) { throw '所选 split.exe 必须位于要安装的游戏目录；请调整 -GameDir 或重新选择文件。' }
if (@(Get-Process -Name split -ErrorAction SilentlyContinue).Count -gt 0) { throw '游戏正在运行，请退出游戏后重试。' }
$Backup = Join-Path $GameDir 'split.exe.orig.bak'
$Temp = Join-Path $GameDir 'split.exe.zh-installing'
try {
    New-Item -ItemType Directory -Path $TempRoot -Force | Out-Null
    $PayloadSha = (Get-FileHash -LiteralPath $Payload -Algorithm SHA256).Hash.ToUpperInvariant()
    if ((Get-Item -LiteralPath $Payload).Length -ne $ExpectedPayloadLen -or $PayloadSha -ne $ExpectedPayloadSha) { throw 'payload.zip 哈希或长度不符，拒绝继续。' }
    $Built = Join-Path $TempRoot 'split.exe.zh-new'
    $Report = Join-Path $TempRoot 'build-report.txt'
    & $Python.Source $Patcher --exe $ExePath --payload $Payload --out $Built --report $Report
    if ($LASTEXITCODE -ne 0) { throw "补丁构建失败，退出码 $LASTEXITCODE。" }
    if (-not (Test-Path -LiteralPath $Built) -or -not (Select-String -LiteralPath $Report -Pattern '^VERDICT: PASS' -Quiet)) { throw "应用器报告未通过验收：$Report" }
    $BuiltItem = Get-Item -LiteralPath $Built
    $BuiltSha = (Get-FileHash -LiteralPath $Built -Algorithm SHA256).Hash.ToUpperInvariant()
    if ($BuiltItem.Length -le $ExpectedOrigLen -or $BuiltSha -eq $OrigSha) { throw "构建结果异常：$($BuiltItem.Length) 字节 / $BuiltSha" }
    if (Test-Path -LiteralPath $Backup) {
        $BackupSha = (Get-FileHash -LiteralPath $Backup -Algorithm SHA256).Hash.ToUpperInvariant()
        if ($BackupSha -ne $ExpectedOrigSha) { throw "现有备份不是预期正版，拒绝覆盖：$Backup" }
    } else {
        Copy-Item -LiteralPath $ExePath -Destination $Backup
        if ((Get-FileHash -LiteralPath $Backup -Algorithm SHA256).Hash.ToUpperInvariant() -ne $OrigSha) { throw '备份校验失败；游戏文件未覆盖。' }
    }
    Move-Item -LiteralPath $Built -Destination $Temp -Force
    try {
        Copy-Item -LiteralPath $Temp -Destination $Target -Force
        $InstalledSha = (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash.ToUpperInvariant()
        $InstalledLen = (Get-Item -LiteralPath $Target).Length
        if ($InstalledSha -ne $BuiltSha -or $InstalledLen -ne $BuiltItem.Length) { throw '安装后与已验证构建产物不一致。' }
    } catch {
        Copy-Item -LiteralPath $Backup -Destination $Target -Force
        throw "安装失败，已从原版备份回滚。$($_.Exception.Message)"
    }
    $Receipt = @{
        version = 1
        installed_length = $InstalledLen
        installed_sha256 = $InstalledSha
        original_length = $ExpectedOrigLen
        original_sha256 = $ExpectedOrigSha
        installed_utc = [DateTime]::UtcNow.ToString('o')
    } | ConvertTo-Json
    Set-Content -LiteralPath (Join-Path $GameDir 'split-zh-install.json') -Value $Receipt -Encoding UTF8
    Write-Host "汉化安装完成。大小: $InstalledLen 字节；SHA256: $InstalledSha"
    Write-Host "原版备份保留于: $Backup"
} finally {
    Remove-Item -LiteralPath $Temp -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
