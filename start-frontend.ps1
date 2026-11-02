[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$vite = Join-Path $root 'frontend\node_modules\vite\bin\vite.js'
if (-not (Test-Path -LiteralPath $vite)) { throw 'Run install.ps1 first.' }
$node = Get-Command node -ErrorAction Stop
Push-Location (Join-Path $root 'frontend')
try {
    & $node.Source $vite
    if ($LASTEXITCODE -ne 0) { throw "Frontend exited with code $LASTEXITCODE." }
} finally { Pop-Location }
