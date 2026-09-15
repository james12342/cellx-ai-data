param(
  [string]$KeyPath = "$env:USERPROFILE\Downloads\LightsailDefaultKey-us-west-2.pem",
  [string]$HostName = "44.240.97.37",
  [string]$UserName = "ubuntu"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$scriptPath = Join-Path $root "cellx-extension-api\customer-scripts\orderdesk_daily_sync.py"
$runnerPath = Join-Path $root "cellx-extension-api\orderdesk_daily_sync_runner.sh"
$servicePath = Join-Path $root "cellx-extension-api\systemd\cellx-orderdesk-daily-sync.service"
$timerPath = Join-Path $root "cellx-extension-api\systemd\cellx-orderdesk-daily-sync.timer"
$knownHosts = Join-Path $env:TEMP "cellx-known-hosts"
$remote = "$UserName@$HostName"
$sshOptions = @(
  "-o", "StrictHostKeyChecking=accept-new",
  "-o", "UserKnownHostsFile=$knownHosts",
  "-o", "BatchMode=yes",
  "-o", "ConnectTimeout=20"
)

function Invoke-Checked {
  param(
    [Parameter(Mandatory = $true)][string]$Command,
    [string[]]$Arguments
  )

  & $Command @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "$Command failed with exit code $LASTEXITCODE"
  }
}

foreach ($path in @($KeyPath, $scriptPath, $runnerPath, $servicePath, $timerPath)) {
  if (!(Test-Path -LiteralPath $path)) {
    throw "Missing required file: $path"
  }
}

Write-Host "Checking OrderDesk sync script syntax..."
python -m py_compile $scriptPath
if ($LASTEXITCODE -ne 0) {
  throw "Python syntax check failed."
}

Write-Host "Uploading OrderDesk daily sync scheduler..."
Invoke-Checked "scp" -Arguments ($sshOptions + @("-i", $KeyPath, $scriptPath, "${remote}:/tmp/orderdesk_daily_sync.py"))
Invoke-Checked "scp" -Arguments ($sshOptions + @("-i", $KeyPath, $runnerPath, "${remote}:/tmp/orderdesk_daily_sync_runner.sh"))
Invoke-Checked "scp" -Arguments ($sshOptions + @("-i", $KeyPath, $servicePath, "${remote}:/tmp/cellx-orderdesk-daily-sync.service"))
Invoke-Checked "scp" -Arguments ($sshOptions + @("-i", $KeyPath, $timerPath, "${remote}:/tmp/cellx-orderdesk-daily-sync.timer"))

$remoteCommand = @"
sudo mkdir -p /opt/cellx-extension-api/customer-scripts &&
sudo cp /tmp/orderdesk_daily_sync.py /opt/cellx-extension-api/customer-scripts/orderdesk_daily_sync.py &&
sudo cp /tmp/orderdesk_daily_sync_runner.sh /opt/cellx-extension-api/orderdesk_daily_sync_runner.sh &&
sudo cp /tmp/cellx-orderdesk-daily-sync.service /etc/systemd/system/cellx-orderdesk-daily-sync.service &&
sudo cp /tmp/cellx-orderdesk-daily-sync.timer /etc/systemd/system/cellx-orderdesk-daily-sync.timer &&
sudo chown root:root /opt/cellx-extension-api/customer-scripts/orderdesk_daily_sync.py /opt/cellx-extension-api/orderdesk_daily_sync_runner.sh /etc/systemd/system/cellx-orderdesk-daily-sync.service /etc/systemd/system/cellx-orderdesk-daily-sync.timer &&
sudo chmod 644 /opt/cellx-extension-api/customer-scripts/orderdesk_daily_sync.py /etc/systemd/system/cellx-orderdesk-daily-sync.service /etc/systemd/system/cellx-orderdesk-daily-sync.timer &&
sudo chmod 755 /opt/cellx-extension-api/orderdesk_daily_sync_runner.sh &&
sudo python3 -m py_compile /opt/cellx-extension-api/customer-scripts/orderdesk_daily_sync.py &&
sudo systemd-analyze calendar '*-*-* 21:00:00 America/Los_Angeles' &&
sudo systemctl daemon-reload &&
sudo systemctl enable --now cellx-orderdesk-daily-sync.timer &&
sudo systemctl list-timers cellx-orderdesk-daily-sync.timer --no-pager
"@ -replace "`r?`n", " "

Write-Host "Installing and enabling AWS timer..."
Invoke-Checked "ssh" -Arguments ($sshOptions + @("-i", $KeyPath, $remote, $remoteCommand))

Write-Host "Done. OrderDesk sync is scheduled daily at 9 PM Pacific."
