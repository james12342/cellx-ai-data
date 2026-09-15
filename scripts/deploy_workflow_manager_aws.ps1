param(
  [string]$KeyPath = "$env:USERPROFILE\Downloads\LightsailDefaultKey-us-west-2.pem",
  [string]$HostName = "44.240.97.37",
  [string]$UserName = "ubuntu"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$apiServer = Join-Path $root "cellx-extension-api\server.py"
$uiIndex = Join-Path $root "cellx-extension-ui\index.html"
$uiApp = Join-Path $root "cellx-extension-ui\app.js"
$uiStyles = Join-Path $root "cellx-extension-ui\styles.css"
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

foreach ($path in @($KeyPath, $apiServer, $uiIndex, $uiApp, $uiStyles)) {
  if (!(Test-Path -LiteralPath $path)) {
    throw "Missing required file: $path"
  }
}

Write-Host "Checking API syntax..."
python -m py_compile $apiServer
if ($LASTEXITCODE -ne 0) {
  throw "Python syntax check failed."
}

Write-Host "Uploading workflow manager API and UI assets..."
Invoke-Checked "scp" -Arguments ($sshOptions + @("-i", $KeyPath, $apiServer, "${remote}:/tmp/cellx-extension-server.py"))
Invoke-Checked "scp" -Arguments ($sshOptions + @("-i", $KeyPath, $uiIndex, "${remote}:/tmp/cellx-workflow-index.html"))
Invoke-Checked "scp" -Arguments ($sshOptions + @("-i", $KeyPath, $uiApp, "${remote}:/tmp/cellx-workflow-app.js"))
Invoke-Checked "scp" -Arguments ($sshOptions + @("-i", $KeyPath, $uiStyles, "${remote}:/tmp/cellx-workflow-styles.css"))

$remoteCommand = @"
sudo cp /tmp/cellx-extension-server.py /opt/cellx-extension-api/server.py &&
sudo cp /tmp/cellx-workflow-index.html /var/www/cellx-extension-ui/index.html &&
sudo cp /tmp/cellx-workflow-app.js /var/www/cellx-extension-ui/app.js &&
sudo cp /tmp/cellx-workflow-styles.css /var/www/cellx-extension-ui/styles.css &&
sudo chown root:root /opt/cellx-extension-api/server.py /var/www/cellx-extension-ui/index.html /var/www/cellx-extension-ui/app.js /var/www/cellx-extension-ui/styles.css &&
sudo chmod 644 /opt/cellx-extension-api/server.py /var/www/cellx-extension-ui/index.html /var/www/cellx-extension-ui/app.js /var/www/cellx-extension-ui/styles.css &&
sudo python3 -m py_compile /opt/cellx-extension-api/server.py &&
sudo systemctl restart cellx-extension-api &&
sudo systemctl is-active cellx-extension-api
"@ -replace "`r?`n", " "

Write-Host "Installing workflow manager on AWS..."
Invoke-Checked "ssh" -Arguments ($sshOptions + @("-i", $KeyPath, $remote, $remoteCommand))

Write-Host "Done. Open https://app.cellaidata.com/agent/ and hard refresh."
