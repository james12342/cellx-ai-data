param(
  [string]$KeyPath = "$env:USERPROFILE\Downloads\LightsailDefaultKey-us-west-2.pem",
  [string]$HostName = "44.240.97.37",
  [string]$UserName = "ubuntu"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$customerScriptsDir = Join-Path $root "cellx-extension-api\customer-scripts"
$workflowTemplatesDir = Join-Path $root "cellx-extension-ui\workflow-templates"
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

foreach ($path in @($KeyPath, $customerScriptsDir, $workflowTemplatesDir)) {
  if (!(Test-Path -LiteralPath $path)) {
    throw "Missing required file: $path"
  }
}

Write-Host "Checking customer script syntax..."
Get-ChildItem -LiteralPath $customerScriptsDir -Filter *.py | ForEach-Object {
  python -m py_compile $_.FullName
}

Write-Host "Uploading workflow templates and customer scripts..."
Invoke-Checked "ssh" -Arguments ($sshOptions + @("-i", $KeyPath, $remote, "rm -rf /tmp/cellx-customer-scripts /tmp/cellx-workflow-templates && mkdir -p /tmp/cellx-customer-scripts /tmp/cellx-workflow-templates"))
Invoke-Checked "scp" -Arguments ($sshOptions + @("-i", $KeyPath, "$customerScriptsDir\*.py", "${remote}:/tmp/cellx-customer-scripts/"))
Invoke-Checked "scp" -Arguments ($sshOptions + @("-i", $KeyPath, "$workflowTemplatesDir\*.json", "${remote}:/tmp/cellx-workflow-templates/"))

$remoteCommand = @"
sudo mkdir -p /opt/cellx-extension-api/customer-scripts /var/www/cellx-extension-ui/workflow-templates &&
sudo cp /tmp/cellx-customer-scripts/*.py /opt/cellx-extension-api/customer-scripts/ &&
sudo cp /tmp/cellx-workflow-templates/*.json /var/www/cellx-extension-ui/workflow-templates/ &&
sudo chown -R root:root /opt/cellx-extension-api/customer-scripts /var/www/cellx-extension-ui/workflow-templates &&
sudo chmod 644 /opt/cellx-extension-api/customer-scripts/*.py /var/www/cellx-extension-ui/workflow-templates/*.json &&
for script in /opt/cellx-extension-api/customer-scripts/*.py; do sudo python3 -m py_compile "`$script"; done
"@ -replace "`r?`n", " "

Write-Host "Installing workflow assets on AWS..."
Invoke-Checked "ssh" -Arguments ($sshOptions + @("-i", $KeyPath, $remote, $remoteCommand))

Write-Host "Done. Open https://app.cellaidata.com/agent/ and hard refresh."
