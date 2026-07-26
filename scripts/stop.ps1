# -----------------------------------------------------------------
#  MathPlatform - Stop backend + frontend
# -----------------------------------------------------------------
$scriptDir = $PSScriptRoot
$runDir    = Join-Path $scriptDir 'run'
$backendPidFile  = Join-Path $runDir 'backend.pid'
$frontendPidFile = Join-Path $runDir 'frontend.pid'

function Stop-Tracked($pidFile, $label) {
    if (-not (Test-Path $pidFile)) {
        Write-Host "$label - no PID file, nothing tracked."
        return
    }
    $storedPid = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($storedPid) {
        $proc = Get-Process -Id $storedPid -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "Stopping $label (PID $storedPid)..."
            Stop-Process -Id $storedPid -Force -ErrorAction SilentlyContinue
        } else {
            Write-Host "$label - PID $storedPid wasn't running."
        }
    }
    Remove-Item $pidFile -ErrorAction SilentlyContinue
}

Stop-Tracked $backendPidFile  'Backend'
Stop-Tracked $frontendPidFile 'Frontend'

# `npm run dev` on Windows launches node.exe as a child of npm.cmd - killing
# the npm.cmd PID doesn't reliably take the child with it. Sweep anything
# still answering on our two ports as a fallback so nothing is left running.
foreach ($port in 8000, 5173) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        Write-Host "Killing leftover process on port $port (PID $($c.OwningProcess))"
        Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "MathPlatform stopped."
