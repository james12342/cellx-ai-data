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
$customerScriptsDir = Join-Path $root "cellx-extension-api\customer-scripts"
$workflowTemplatesDir = Join-Path $root "cellx-extension-ui\workflow-templates"
$marketingIndex = Join-Path $root "rdp-marketing-site\index.html"
$marketingStyles = Join-Path $root "rdp-marketing-site\styles.css"
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
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments
  )

  & $Command @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "$Command failed with exit code $LASTEXITCODE"
  }
}

foreach ($path in @($KeyPath, $uiApp, $uiStyles, $uiIndex, $apiServer, $customerScriptsDir, $workflowTemplatesDir, $marketingIndex, $marketingStyles)) {
  if (!(Test-Path -LiteralPath $path)) {
    throw "Missing required file: $path"
  }
}

Write-Host "Checking backend syntax..."
python -m py_compile $apiServer
Get-ChildItem -LiteralPath $customerScriptsDir -Filter *.py | ForEach-Object {
  python -m py_compile $_.FullName
}

Write-Host "Uploading CellX workflow UI..."
Invoke-Checked scp @sshOptions -i $KeyPath $uiApp "${remote}:/tmp/cellx-workflow-app.js"
Invoke-Checked scp @sshOptions -i $KeyPath $uiStyles "${remote}:/tmp/cellx-workflow-styles.css"
Invoke-Checked scp @sshOptions -i $KeyPath $uiIndex "${remote}:/tmp/cellx-workflow-index.html"

Write-Host "Uploading CellX extension API..."
Invoke-Checked scp @sshOptions -i $KeyPath $apiServer "${remote}:/tmp/cellx-extension-server.py"

Write-Host "Uploading customer scripts and workflow templates..."
Invoke-Checked ssh @sshOptions -i $KeyPath $remote "rm -rf /tmp/cellx-customer-scripts /tmp/cellx-workflow-templates && mkdir -p /tmp/cellx-customer-scripts /tmp/cellx-workflow-templates"
Invoke-Checked scp @sshOptions -i $KeyPath "$customerScriptsDir\*.py" "${remote}:/tmp/cellx-customer-scripts/"
Invoke-Checked scp @sshOptions -i $KeyPath "$workflowTemplatesDir\*.json" "${remote}:/tmp/cellx-workflow-templates/"

Write-Host "Uploading marketing site..."
Invoke-Checked scp @sshOptions -i $KeyPath $marketingIndex "${remote}:/tmp/rdp-marketing-index.html"
Invoke-Checked scp @sshOptions -i $KeyPath $marketingStyles "${remote}:/tmp/rdp-marketing-styles.css"

$restartCommand = if ($SkipApiRestart) { "true" } else { "sudo systemctl restart cellx-extension-api && sudo systemctl is-active cellx-extension-api" }
$remoteCommand = @"
sudo cp /tmp/cellx-workflow-app.js /var/www/cellx-extension-ui/app.js &&
sudo cp /tmp/cellx-workflow-styles.css /var/www/cellx-extension-ui/styles.css &&
sudo cp /tmp/cellx-workflow-index.html /var/www/cellx-extension-ui/index.html &&
sudo cp /tmp/cellx-extension-server.py /opt/cellx-extension-api/server.py &&
sudo mkdir -p /opt/cellx-extension-api/customer-scripts /var/www/cellx-extension-ui/workflow-templates &&
sudo cp /tmp/cellx-customer-scripts/*.py /opt/cellx-extension-api/customer-scripts/ &&
sudo cp /tmp/cellx-workflow-templates/*.json /var/www/cellx-extension-ui/workflow-templates/ &&
sudo cp /tmp/rdp-marketing-index.html /var/www/rdp-marketing-site/index.html &&
sudo cp /tmp/rdp-marketing-styles.css /var/www/rdp-marketing-site/styles.css &&
sudo chown -R root:root /var/www/cellx-extension-ui /opt/cellx-extension-api /var/www/rdp-marketing-site &&
sudo chmod 644 /var/www/cellx-extension-ui/app.js /var/www/cellx-extension-ui/styles.css /var/www/cellx-extension-ui/index.html /opt/cellx-extension-api/server.py /var/www/rdp-marketing-site/index.html /var/www/rdp-marketing-site/styles.css /opt/cellx-extension-api/customer-scripts/*.py /var/www/cellx-extension-ui/workflow-templates/*.json &&
sudo python3 -m py_compile /opt/cellx-extension-api/server.py &&
for script in /opt/cellx-extension-api/customer-scripts/*.py; do sudo python3 -m py_compile "`$script"; done &&
$restartCommand
"@ -replace "`r?`n", " "

Write-Host "Installing files on AWS..."
Invoke-Checked ssh @sshOptions -i $KeyPath $remote $remoteCommand

Write-Host "Done. Open https://app.cellaidata.com/agent/ and hard refresh if the browser cache still shows the old UI."
