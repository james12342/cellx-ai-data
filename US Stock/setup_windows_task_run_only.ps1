param(
    [string]$TaskName = "US Stock Sector Radar",
    [string]$OldTaskName = "US Stock Sector Radar Email",
    [string]$Time = "06:20",
    [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Logs = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $Logs | Out-Null

if (-not $PythonPath) {
    $VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
    if (Test-Path $VenvPython) {
        $PythonPath = $VenvPython
    } else {
        $PythonPath = "python"
    }
}

try {
    Unregister-ScheduledTask -TaskName $OldTaskName -Confirm:$false -ErrorAction SilentlyContinue
} catch {
    Write-Host "Old email task was not found or could not be removed: $OldTaskName"
}

$Script = Join-Path $Root "us_stock_sector_radar.py"
$Log = Join-Path $Logs "daily_us_radar.log"
$PowerShellArgs = "-NoProfile -ExecutionPolicy Bypass -Command `"Set-Location '$Root'; & '$PythonPath' '$Script' *> '$Log'`""

$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $PowerShellArgs
$Trigger = New-ScheduledTaskTrigger -Daily -At $Time
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Runs US stock sector radar and writes reports locally." -Force | Out-Null

Write-Host "Scheduled task installed: $TaskName"
Write-Host "Run time: daily at $Time"
Write-Host "Log file: $Log"
