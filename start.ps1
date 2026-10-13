[CmdletBinding()]
param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$vite = Join-Path $root 'frontend\node_modules\vite\bin\vite.js'
if (-not (Test-Path $python) -or -not (Test-Path $vite)) { throw 'Dependencies are missing. Run install.ps1 first.' }
$node = (Get-Command node -ErrorAction Stop).Source
Push-Location $root
try {
    $configJson = & $python (Join-Path $root 'backend\local_config.py')
    if ($LASTEXITCODE -ne 0) { throw 'Invalid configuration. Check .env.local.' }
    $config = $configJson | ConvertFrom-Json
    $busyPorts = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners() | Where-Object { $_.Port -in $config.ports }
    if ($busyPorts) { throw ('A configured port is already in use: ' + (($busyPorts | ForEach-Object { $_.Port } | Select-Object -Unique) -join ', ')) }
    $runtime = Join-Path $root '.runtime'
    $pidFile = Join-Path $runtime 'services.json'
    if (Test-Path $pidFile) { throw 'A previous launch exists. Run stop.ps1 before starting again.' }
    New-Item -ItemType Directory -Force -Path $runtime, $config.logs | Out-Null
    $started = @()
    try {
        $backend = Start-Process -FilePath $python -WindowStyle Hidden -WorkingDirectory $root -ArgumentList ('"{0}"' -f (Join-Path $root 'backend\main.py')) -RedirectStandardOutput (Join-Path $config.logs 'backend.out.log') -RedirectStandardError (Join-Path $config.logs 'backend.err.log') -PassThru
        $started += $backend
        $frontend = Start-Process -FilePath $node -WindowStyle Hidden -WorkingDirectory (Join-Path $root 'frontend') -ArgumentList ('"{0}"' -f $vite) -RedirectStandardOutput (Join-Path $config.logs 'frontend.out.log') -RedirectStandardError (Join-Path $config.logs 'frontend.err.log') -PassThru
        $started += $frontend
        $records = @($started | ForEach-Object { @{ pid = $_.Id; started = $_.StartTime.ToUniversalTime().Ticks.ToString() } })
        ConvertTo-Json -InputObject $records | Set-Content -LiteralPath $pidFile
        $ready = $false
        $startupClock = [System.Diagnostics.Stopwatch]::StartNew()
        while ($startupClock.Elapsed.TotalSeconds -lt $config.startupTimeout) {
            if ($backend.HasExited -or $frontend.HasExited) { throw "A service exited. See logs in $($config.logs)." }
            try {
                Invoke-WebRequest -UseBasicParsing -Uri ($config.backend + '/health') -TimeoutSec 1 | Out-Null
                Invoke-WebRequest -UseBasicParsing -Uri $config.frontend -TimeoutSec 1 | Out-Null
                $ready = $true
                break
            } catch { Start-Sleep -Milliseconds 250 }
        }
        if (-not $ready) { throw "Services did not become ready. See logs in $($config.logs)." }
        Write-Host "Frontend: $($config.frontend)"
        Write-Host "API docs: $($config.backend)/docs"
        Write-Host 'Run .\stop.ps1 to stop these services.'
        if (-not $NoBrowser) { Start-Process $config.frontend }
    } catch {
        $cleanupFailed = $false
        $started | Where-Object { -not $_.HasExited } | ForEach-Object { & taskkill.exe /PID $_.Id /T /F | Out-Null; if ($LASTEXITCODE -ne 0) { $cleanupFailed = $true } }
        if (-not $cleanupFailed -and (Test-Path $pidFile)) { Remove-Item -LiteralPath $pidFile }
        throw
    }
} finally { Pop-Location }
