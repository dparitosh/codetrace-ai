[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Run install.ps1 first.' }
Push-Location $root
try { & $python (Join-Path $root 'backend\main.py') } finally { Pop-Location }
