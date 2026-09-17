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

$backend = "`$env:UPLOAD_DIR='$root\backend\data\uploads'; `$env:TEMP_DIR='$root\backend\data\temp'; `$env:LOG_DIR='$root\backend\data\logs'; & '$python' '$root\backend\main.py'"
Start-Process powershell -ArgumentList '-NoExit', '-Command', $backend
Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$root\frontend'; npm run dev -- --host 127.0.0.1 --port 3001"
if (-not $NoBrowser) { Start-Process 'http://localhost:3001/' }
