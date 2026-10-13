[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
if (-not (Test-Path (Join-Path $root 'frontend\node_modules'))) { throw 'Run install.ps1 first.' }
Push-Location (Join-Path $root 'frontend')
try { & npm run dev } finally { Pop-Location }
