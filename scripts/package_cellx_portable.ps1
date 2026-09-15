param(
  [string]$OutputDir = "$PSScriptRoot\..\dist",
  [string]$PackageName = "cellx-workflow-portable"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$outputRoot = [IO.Path]::GetFullPath($OutputDir)
$workspacePrefix = [IO.Path]::GetFullPath($root).TrimEnd('\') + '\'
if (-not $outputRoot.StartsWith($workspacePrefix, [StringComparison]::OrdinalIgnoreCase) -or $PackageName -notmatch '^[a-zA-Z0-9_-]+$') {
  throw 'Package output must be inside the workspace and use a plain package name.'
}
$packageRoot = [IO.Path]::GetFullPath((Join-Path $outputRoot $PackageName))
$zipPath = [IO.Path]::GetFullPath((Join-Path $outputRoot "$PackageName.zip"))
if ((Test-Path -LiteralPath $packageRoot) -and (Get-Item -LiteralPath $packageRoot).LinkType) {
  throw 'Refusing to replace a linked package directory.'
}

if (Test-Path -LiteralPath $packageRoot) {
  Remove-Item -LiteralPath $packageRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $packageRoot | Out-Null

foreach ($item in @(
  "cellx-extension-api",
  "cellx-extension-ui",
  "workflow-templates",
  "run_cellx_portable.ps1",
  "run_cellx_portable.bat",
  "install_browser_dependencies.bat",
  "PORTABLE_README.md"
)) {
  $source = Join-Path $root $item
  if (Test-Path -LiteralPath $source) {
    Copy-Item -LiteralPath $source -Destination $packageRoot -Recurse -Force
  }
}

Get-ChildItem -Path $packageRoot -Recurse -File | Where-Object {
  $_.Name -match '(^\.env|\.pyc$|\.pem$|\.sqlite3?$|^marketplace-store\.json$|^test_.*\.py$)'
} | ForEach-Object {
  if (-not $_.FullName.StartsWith($packageRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Unexpected package file path.' }
  Remove-Item -LiteralPath $_.FullName -Force
}
if (Test-Path -LiteralPath $zipPath) {
  Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $packageRoot "*") -DestinationPath $zipPath -Force
Write-Host "Portable package created: $zipPath"
