param(
  [int]$Port = 3001
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$apiDir = Join-Path $root "cellx-extension-api"
$uiDir = Join-Path $root "cellx-extension-ui"
$scriptDir = Join-Path $apiDir "customer-scripts"
$templateDir = Join-Path $uiDir "workflow-templates"

foreach ($path in @($apiDir, $uiDir, $scriptDir, $templateDir)) {
  if (!(Test-Path -LiteralPath $path)) {
    throw "Missing required folder: $path"
  }
}

$env:PORT = "$Port"
$env:UI_DIR = $uiDir
$env:SCRIPT_DIR = $scriptDir
$env:WORKFLOW_TEMPLATE_DIR = $templateDir
if (-not $env:MAX_SCRIPT_TIMEOUT) { $env:MAX_SCRIPT_TIMEOUT = "180" }
if (-not $env:MAX_SCRIPT_OUTPUT) { $env:MAX_SCRIPT_OUTPUT = "200000" }

$url = "http://127.0.0.1:$Port/agent/"
Write-Host "Starting CellX Workflow Designer at $url"
Write-Host "Set OPENAI_API_KEY before launching to enable AI Voice Builder."
Start-Process $url
Set-Location $apiDir
python .\server.py
