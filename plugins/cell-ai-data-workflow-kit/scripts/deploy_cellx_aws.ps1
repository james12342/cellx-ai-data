param(
  [string]$KeyPath = "$env:USERPROFILE\Downloads\LightsailDefaultKey-us-west-2.pem",
  [string]$HostName = "44.240.97.37",
  [string]$UserName = "ubuntu",
  [switch]$SkipApiRestart
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$uiApp = Join-Path $root "cellx-extension-ui\app.js"
$uiStyles = Join-Path $root "cellx-extension-ui\styles.css"
$uiIndex = Join-Path $root "cellx-extension-ui\index.html"
$apiServer = Join-Path $root "cellx-extension-api\server.py"
$marketingIndex = Join-Path $root "rdp-marketing-site\index.html"
$marketingStyles = Join-Path $root "rdp-marketing-site\styles.css"
$remote = "$UserName@$HostName"

foreach ($path in @($KeyPath, $uiApp, $uiStyles, $uiIndex, $apiServer, $marketingIndex, $marketingStyles)) {
  if (!(Test-Path -LiteralPath $path)) {
    throw "Missing required file: $path"
  }
}

Write-Host "Checking backend syntax..."
python -m py_compile $apiServer

Write-Host "Uploading CellX workflow UI..."
scp -i $KeyPath $uiApp "${remote}:/tmp/cellx-workflow-app.js"
scp -i $KeyPath $uiStyles "${remote}:/tmp/cellx-workflow-styles.css"
scp -i $KeyPath $uiIndex "${remote}:/tmp/cellx-workflow-index.html"

Write-Host "Uploading CellX extension API..."
scp -i $KeyPath $apiServer "${remote}:/tmp/cellx-extension-server.py"

Write-Host "Uploading marketing site..."
scp -i $KeyPath $marketingIndex "${remote}:/tmp/rdp-marketing-index.html"
scp -i $KeyPath $marketingStyles "${remote}:/tmp/rdp-marketing-styles.css"

$restartCommand = if ($SkipApiRestart) { "true" } else { "sudo systemctl restart cellx-extension-api && sudo systemctl is-active cellx-extension-api" }
$remoteCommand = @"
sudo cp /tmp/cellx-workflow-app.js /var/www/cellx-extension-ui/app.js &&
sudo cp /tmp/cellx-workflow-styles.css /var/www/cellx-extension-ui/styles.css &&
sudo cp /tmp/cellx-workflow-index.html /var/www/cellx-extension-ui/index.html &&
sudo cp /tmp/cellx-extension-server.py /opt/cellx-extension-api/server.py &&
sudo cp /tmp/rdp-marketing-index.html /var/www/rdp-marketing-site/index.html &&
sudo cp /tmp/rdp-marketing-styles.css /var/www/rdp-marketing-site/styles.css &&
sudo chown root:root /var/www/cellx-extension-ui/app.js /var/www/cellx-extension-ui/styles.css /var/www/cellx-extension-ui/index.html /opt/cellx-extension-api/server.py /var/www/rdp-marketing-site/index.html /var/www/rdp-marketing-site/styles.css &&
sudo chmod 644 /var/www/cellx-extension-ui/app.js /var/www/cellx-extension-ui/styles.css /var/www/cellx-extension-ui/index.html /opt/cellx-extension-api/server.py /var/www/rdp-marketing-site/index.html /var/www/rdp-marketing-site/styles.css &&
sudo python3 -m py_compile /opt/cellx-extension-api/server.py &&
$restartCommand
"@ -replace "`r?`n", " "

Write-Host "Installing files on AWS..."
ssh -i $KeyPath $remote $remoteCommand

Write-Host "Done. Open https://app.cellaidata.com/workflow/ and hard refresh if the browser cache still shows the old UI."
