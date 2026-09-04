param(
  [string]$PluginPath = "plugins\cell-ai-data-workflow-kit",
  [string]$OutputDir = "dist"
)

$ErrorActionPreference = "Stop"
$plugin = Resolve-Path $PluginPath
$outDir = Join-Path (Get-Location) $OutputDir
New-Item -ItemType Directory -Force $outDir | Out-Null

$manifest = Get-Content (Join-Path $plugin ".codex-plugin\plugin.json") -Raw | ConvertFrom-Json
$version = $manifest.version -replace '[^A-Za-z0-9._-]', '-'
$zipPath = Join-Path $outDir "$($manifest.name)-$version.zip"

if (Test-Path $zipPath) {
  Remove-Item $zipPath
}

Compress-Archive -Path (Join-Path $plugin "*") -DestinationPath $zipPath -Force

Write-Host "Packaged plugin:"
Write-Host $zipPath
