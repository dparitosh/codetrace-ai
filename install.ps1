<#!
.SYNOPSIS
Installs CodeTrace AI prerequisites for a local Windows development environment.
#>
[CmdletBinding()]
param([string]$PythonPath)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = if ($PythonPath) { Get-Command $PythonPath -ErrorAction Stop } elseif (Test-Path (Join-Path $root '.venv\Scripts\python.exe')) { Get-Command (Join-Path $root '.venv\Scripts\python.exe') } else { Get-Command python -ErrorAction SilentlyContinue }
if ($python -and $python.Source -match 'WindowsApps') { $python = $null }
$npm = Get-Command npm -ErrorAction SilentlyContinue
if (-not $python) { throw 'Python 3.10+ is required. Install Python or pass -PythonPath with a working executable path.' }
if (-not $npm) { throw 'Node.js 20+ is required. Install it from https://nodejs.org/' }

Push-Location $root
try {
    & $python.Source -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.10+ is required.' }
    if (-not (Test-Path '.venv\Scripts\python.exe')) {
        & $python.Source -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
    }
    & '.venv\Scripts\python.exe' -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed.' }
    & '.venv\Scripts\python.exe' -m pip install -r 'backend\requirements-local.txt'
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
    & '.venv\Scripts\python.exe' -m pip install -e 'codegraph_core'
    if ($LASTEXITCODE -ne 0) { throw 'Core package installation failed.' }
    Push-Location 'frontend'
    try {
        & $npm.Source install
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    } finally { Pop-Location }
    Write-Host 'Installation complete. Run .\start.ps1' -ForegroundColor Green
} finally { Pop-Location }
