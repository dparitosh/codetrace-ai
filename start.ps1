<#!
.SYNOPSIS
Starts the local CodeTrace AI backend and frontend on Windows.
#>
[CmdletBinding()]
param([switch]$NoBrowser)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python) -or -not (Test-Path (Join-Path $root 'frontend\node_modules'))) {
    throw 'Dependencies are missing. Run .\install.ps1 first.'
}

Start-Process -FilePath $python -WindowStyle Hidden -WorkingDirectory $root -ArgumentList ('"{0}"' -f (Join-Path $root 'backend\main.py'))
Start-Process powershell -WindowStyle Hidden -WorkingDirectory (Join-Path $root 'frontend') -ArgumentList '-NoProfile', '-Command', 'npm run dev -- --host 127.0.0.1 --port 3001 --strictPort'
if (-not $NoBrowser) { Start-Process 'http://localhost:3001/' }
