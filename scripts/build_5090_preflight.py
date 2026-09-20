"""Package a read-only Windows worker hardware check; uploads nothing."""
from pathlib import Path
import zipfile

root=Path(__file__).resolve().parents[1]/'outputs/windows-5090-preflight'
root.mkdir(parents=True,exist_ok=True)
script=r'''$ErrorActionPreference = 'Stop'
$osInfo = Get-CimInstance Win32_OperatingSystem
$computerInfo = Get-CimInstance Win32_ComputerSystem
$systemDrive = Get-CimInstance Win32_LogicalDisk -Filter ('DeviceID=' + [char]39 + $env:SystemDrive + [char]39)
$smi = Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue
$gpuRows = @()
$gpuError = $null
if ($smi) {
    $rawGpu = & $smi.Source '--query-gpu=name,memory.total,driver_version' '--format=csv,noheader,nounits' 2>$null
    if ($LASTEXITCODE -eq 0) {
        foreach ($line in $rawGpu) {
            $parts = $line -split ','
            if ($parts.Count -ge 3) { $gpuRows += [pscustomobject]@{name=$parts[0].Trim(); vramMiB=[int]$parts[1].Trim(); driver=$parts[2].Trim()} }
        }
    } else { $gpuError = 'NVIDIA driver query failed.' }
} else { $gpuError = 'nvidia-smi is unavailable; check the NVIDIA driver.' }
$reasons = @()
if (-not [Environment]::Is64BitOperatingSystem) { $reasons += '64-bit Windows required.' }
if ([int]$osInfo.BuildNumber -lt 19041) { $reasons += 'Windows build is too old for the initial target.' }
if (-not ($gpuRows | Where-Object { $_.name -match 'RTX 5090' })) { $reasons += 'Target RTX 5090 was not detected.' }
if ($computerInfo.TotalPhysicalMemory -lt 15GB) { $reasons += 'At least approximately 16 GB system RAM is required for initial testing; 32 GB recommended.' }
if ($systemDrive.FreeSpace -lt 25GB) { $reasons += 'At least 25 GB free system-drive space is required for the initial small-model test.' }
$report = [ordered]@{purpose='Windows RTX 5090 worker preflight'; windows=$osInfo.Caption; build=$osInfo.BuildNumber; architecture=$osInfo.OSArchitecture; ramGiB=[math]::Round($computerInfo.TotalPhysicalMemory/1GB,1); systemDiskFreeGiB=[math]::Round($systemDrive.FreeSpace/1GB,1); gpu=@($gpuRows); gpuQueryError=$gpuError; preliminaryPass=($reasons.Count -eq 0); reasons=@($reasons); note='Read-only hardware check. This does not certify CUDA/model compatibility. No model installed, no data uploaded, no firewall or driver changes.'}
$destination = $env:CELLX_PREFLIGHT_REPORT
if (-not $destination) { $destination = Join-Path (Get-Location) 'configuration-report.json' }
$report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $destination -Encoding UTF8
$report | ConvertTo-Json -Depth 5 | Write-Host
Write-Host ('Report saved: ' + $destination)
'''
(root/'Check-Hardware.ps1').write_text(script,encoding='utf-8-sig')
# The cmd launcher invokes only the read-only commands above. It does not alter
# Windows execution policy or require an administrator shell.
oneline='; '.join(line.strip() for line in script.splitlines()).replace('{;','{').replace('; }',' }').replace('}; else','} else')
launcher='@echo off\r\nsetlocal\r\nset "CELLX_PREFLIGHT_REPORT=%~dp0configuration-report.json"\r\npowershell.exe -NoProfile -Command "'+oneline+'"\r\npause\r\n'
(root/'Check-5090.cmd').write_text(launcher,encoding='ascii')
(root/'说明.txt').write_text('Windows 5090 工作机配置检测\n\n1. 将整个压缩包解压到家里5090电脑上的一个文件夹。\n2. 双击 Check-5090.cmd。无需管理员权限。\n3. 同一文件夹会生成 configuration-report.json，可将该文件发回这段对话。\n\n此工具只检测Windows版本、显卡型号、显存、驱动版本、内存和系统盘剩余空间，不收集用户名、序列号、密码、照片或网络地址，不上传数据，不安装模型，不更改系统配置。\n\n检测通过仅说明满足初步筛选；5090的CUDA环境和模型兼容性需要后续实际安装测试。25GB是初始小模型测试空间门槛，不是所有视频模型的空间需求。\n\n计划架构：客户网页 -> AWS任务队列 <- 家中5090主动领取任务 -> 生成并回传。此包仅为配置检测工具，尚未包含队列连接或安装器。\n',encoding='utf-8-sig')
archive=root.parent/'Windows-5090-配置检测.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for p in root.iterdir():
        if p.name != 'configuration-report.json': z.write(p,p.name)
print(archive)
