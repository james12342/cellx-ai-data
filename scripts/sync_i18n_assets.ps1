$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
foreach ($site in @('cellx-extension-ui', 'rdp-marketing-site', 'cellx-data-ui')) {
  foreach ($name in @('i18n.js', 'i18n.css')) {
    Copy-Item -LiteralPath (Join-Path $root "shared/$name") -Destination (Join-Path $root "$site/$name")
  }
}
