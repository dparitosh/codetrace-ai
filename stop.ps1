[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$pidFile = Join-Path $PSScriptRoot '.runtime\services.json'
if (-not (Test-Path $pidFile)) { Write-Host 'No managed services found.'; return }
foreach ($record in @(Get-Content -LiteralPath $pidFile -Raw | ConvertFrom-Json)) {
    $process = Get-Process -Id $record.pid -ErrorAction SilentlyContinue
    if ($process -and $process.StartTime.ToUniversalTime().Ticks.ToString() -eq $record.started) {
        & taskkill.exe /PID $process.Id /T /F | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Could not stop managed process $($process.Id). Service records have been retained." }
    }
}
Remove-Item -LiteralPath $pidFile
Write-Host 'CodeTrace services stopped.'
