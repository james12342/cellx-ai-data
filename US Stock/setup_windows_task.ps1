param(
    [string]$TaskName = "US Stock Sector Radar Email",
    [string]$Time = "06:20",
    [string]$PythonPath = "",
    [string]$SmtpHost = "",
    [string]$SmtpPort = "",
    [string]$SmtpUsername = "",
    [string]$SmtpPassword = "",
    [string]$SmtpFrom = "",
    [string]$SmtpTo = "",
    [string]$SmtpUseTls = "true"
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

$envMap = @{
    "SMTP_HOST" = $SmtpHost
    "SMTP_PORT" = $SmtpPort
    "SMTP_USERNAME" = $SmtpUsername
    "SMTP_PASSWORD" = $SmtpPassword
    "SMTP_FROM" = $SmtpFrom
    "SMTP_TO" = $SmtpTo
    "SMTP_USE_TLS" = $SmtpUseTls
}

foreach ($item in $envMap.GetEnumerator()) {
    if ($item.Value) {
        [Environment]::SetEnvironmentVariable($item.Key, $item.Value, "User")
    }
}

$Script = Join-Path $Root "run_daily_email.py"
$Log = Join-Path $Logs "daily_us_radar.log"
$PowerShellArgs = "-NoProfile -ExecutionPolicy Bypass -Command `"Set-Location '$Root'; & '$PythonPath' '$Script' *> '$Log'`""

$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $PowerShellArgs
$Trigger = New-ScheduledTaskTrigger -Daily -At $Time
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Runs US stock sector radar and emails CSV reports." -Force | Out-Null

Write-Host "Scheduled task installed: $TaskName"
Write-Host "Run time: daily at $Time"
Write-Host "Log file: $Log"
