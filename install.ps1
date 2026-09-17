<#!
.SYNOPSIS
Installs CodeTrace AI prerequisites for a local Windows development environment.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python -and $python.Source -match 'WindowsApps') { $python = $null }
$npm = Get-Command npm -ErrorAction SilentlyContinue
if (-not $python) { throw 'A working Python 3.9+ installation is required. Install it from https://www.python.org/downloads/ and disable the Windows Store app-execution alias if it shadows Python.' }
if (-not $npm) { throw 'Node.js 20+ is required. Install it from https://nodejs.org/' }

Push-Location $root
try {
    if (-not (Test-Path '.venv\Scripts\python.exe')) { & $python.Source -m venv .venv }
    & '.venv\Scripts\python.exe' -m pip install --upgrade pip
    & '.venv\Scripts\python.exe' -m pip install -r 'backend\requirements-local.txt'
    & '.venv\Scripts\python.exe' -m pip install -e 'codegraph_core'
    Push-Location 'frontend'
    try { & $npm.Source install } finally { Pop-Location }
    Write-Host 'Installation complete. Run .\start.ps1' -ForegroundColor Green
} finally { Pop-Location }
