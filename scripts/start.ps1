# -----------------------------------------------------------------
#  MathPlatform - Start (backend + frontend, in the background)
#
#  Idempotent: safe to run even if the servers are already up -
#  it detects that and just makes sure Chrome is pointed at them.
#
#  Manual use:      double-click start.bat  (in the project root)
#  Automatic use:   install_autostart.ps1 runs this silently at login
# -----------------------------------------------------------------
param(
    [switch]$OpenChrome
)

$ErrorActionPreference = 'Stop'

$scriptDir   = $PSScriptRoot
$root        = Split-Path -Parent $scriptDir          # project root
$backendDir  = Join-Path $root 'backend'
$frontendDir = Join-Path $root 'frontend'
$runDir      = Join-Path $scriptDir 'run'
$logDir      = Join-Path $scriptDir 'logs'
New-Item -ItemType Directory -Force -Path $runDir  | Out-Null
New-Item -ItemType Directory -Force -Path $logDir  | Out-Null

$backendPidFile  = Join-Path $runDir 'backend.pid'
$frontendPidFile = Join-Path $runDir 'frontend.pid'
$backendLog      = Join-Path $logDir 'backend.log'
$frontendLog     = Join-Path $logDir 'frontend.log'

$backendHealthUrl = 'http://127.0.0.1:8000/api/'
$frontendUrl       = 'http://localhost:5173'

function Write-Step($msg) { Write-Host "> $msg" }

# Runs a native .exe (python, pip, npm, ...) safely.
#
# Why this exists: with $ErrorActionPreference = 'Stop', PowerShell converts
# *any* line a native command writes to stderr into a terminating error -
# even routine warnings - and that can happen before output redirection
# (*>, 2>) finishes writing to a log file, so you see a truncated message
# on screen instead of the full thing in the log. This wraps the call with
# ErrorActionPreference temporarily relaxed, then checks the real exit code
# afterward, which is the correct way to detect native-command failure.
function Invoke-Native {
    param(
        [Parameter(Mandatory)] [string]$FilePath,
        [Parameter(Mandatory)] [string[]]$ArgumentList,
        [string]$LogFile,
        [string]$WorkingDirectory
    )
    $prevPref = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        if ($WorkingDirectory) { Push-Location $WorkingDirectory }
        if ($LogFile) {
            & $FilePath @ArgumentList *> $LogFile
        } else {
            & $FilePath @ArgumentList
        }
    } finally {
        if ($WorkingDirectory) { Pop-Location }
        $ErrorActionPreference = $prevPref
    }
    if ($LASTEXITCODE -ne 0) {
        $hint = if ($LogFile) { " Full output: $LogFile" } else { "" }
        throw "'$FilePath $($ArgumentList -join ' ')' failed with exit code $LASTEXITCODE.$hint"
    }
}

function Test-PortListening($port) {
    try {
        return [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
    } catch { return $false }
}

function Get-TrackedProcess($pidFile) {
    if (-not (Test-Path $pidFile)) { return $null }
    $storedPid = Get-Content $pidFile -ErrorAction SilentlyContinue
    if (-not $storedPid) { return $null }
    return Get-Process -Id $storedPid -ErrorAction SilentlyContinue
}

function Wait-ForHttp($url, [int]$timeoutSec = 45) {
    $elapsed = 0
    while ($elapsed -lt $timeoutSec) {
        try {
            $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
            if ($resp.StatusCode -lt 500) { return $true }
        } catch {
            # Windows PowerShell 5.1 throws for ANY non-2xx status (404, 403,
            # etc.), unlike PS7. That's still proof the server is up and
            # answering - only a connection-level failure (nothing listening
            # yet) means "keep waiting". Both WebException (5.1) and
            # HttpResponseException (7+) carry the real response here.
            $webResponse = $_.Exception.Response
            if ($webResponse -and $webResponse.StatusCode) {
                if ([int]$webResponse.StatusCode -lt 500) { return $true }
            }
            # else: genuine connection refused / timeout - not listening yet.
        }
        Start-Sleep -Seconds 1
        $elapsed++
    }
    return $false
}

function Open-InChrome($url) {
    $candidates = @(
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
        "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
    )
    $chrome = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($chrome) {
        Start-Process -FilePath $chrome -ArgumentList $url
    } else {
        Write-Step "Chrome not found in the usual install locations - opening your default browser instead."
        Start-Process $url
    }
}

Write-Host ""
Write-Host "========================================"
Write-Host "  MathPlatform - starting in background"
Write-Host "========================================"

try {

# -- Backend ------------------------------------------------------
$backendProc = Get-TrackedProcess $backendPidFile
if ($backendProc) {
    Write-Step "Backend already running (PID $($backendProc.Id)) - leaving it alone."
} elseif (Test-PortListening 8000) {
    Write-Step "Port 8000 is already in use by something this script didn't start - leaving it alone."
} else {
    $venvPython = Join-Path $backendDir 'venv\Scripts\python.exe'
    if (-not (Test-Path $venvPython)) {
        Write-Step "First run: creating virtual environment and installing backend dependencies..."
        Invoke-Native -FilePath 'python' -ArgumentList @('-m', 'venv', (Join-Path $backendDir 'venv'))
        Invoke-Native -FilePath $venvPython -ArgumentList @('-m', 'pip', 'install', '--upgrade', 'pip', '--quiet')
        Invoke-Native -FilePath $venvPython -ArgumentList @('-m', 'pip', 'install', '-r', (Join-Path $backendDir 'requirements.txt'), '--quiet')
    }

    Write-Step "Applying database migrations..."
    Invoke-Native -FilePath $venvPython `
        -ArgumentList @((Join-Path $backendDir 'manage.py'), 'migrate', '--run-syncdb') `
        -LogFile "$backendLog.migrate"

    Write-Step "Starting backend (Django) on http://127.0.0.1:8000 ..."
    # --noreload: the autoreloader spawns a child watcher process, and killing
    # just the parent PID later would leave that child running as an orphan.
    # A single, predictable process is what a background service should be.
    $beProc = Start-Process -FilePath $venvPython `
        -ArgumentList 'manage.py','runserver','127.0.0.1:8000','--noreload' `
        -WorkingDirectory $backendDir `
        -WindowStyle Hidden `
        -RedirectStandardOutput $backendLog `
        -RedirectStandardError "$backendLog.err" `
        -PassThru
    $beProc.Id | Out-File -Encoding ascii -FilePath $backendPidFile
    Write-Step "Backend started (PID $($beProc.Id)). Log: $backendLog"
}

# -- Frontend -----------------------------------------------------
$frontendProc = Get-TrackedProcess $frontendPidFile
if ($frontendProc) {
    Write-Step "Frontend already running (PID $($frontendProc.Id)) - leaving it alone."
} elseif (Test-PortListening 5173) {
    Write-Step "Port 5173 is already in use by something this script didn't start - leaving it alone."
} else {
    if (-not (Test-Path (Join-Path $frontendDir 'node_modules'))) {
        Write-Step "First run: installing frontend dependencies (npm install)..."
        Invoke-Native -FilePath 'npm' -ArgumentList @('install') -WorkingDirectory $frontendDir
    }

    $npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
    $npmPath = if ($npmCmd) { $npmCmd.Source } else { 'npm.cmd' }

    Write-Step "Starting frontend (Vite) on http://localhost:5173 ..."
    $feProc = Start-Process -FilePath $npmPath `
        -ArgumentList 'run','dev' `
        -WorkingDirectory $frontendDir `
        -WindowStyle Hidden `
        -RedirectStandardOutput $frontendLog `
        -RedirectStandardError "$frontendLog.err" `
        -PassThru
    $feProc.Id | Out-File -Encoding ascii -FilePath $frontendPidFile
    Write-Step "Frontend started (PID $($feProc.Id)). Log: $frontendLog"
}

# -- Wait for both to actually answer, then open Chrome ------------
Write-Step "Waiting for both servers to respond..."
$backendOk  = Wait-ForHttp $backendHealthUrl
$frontendOk = Wait-ForHttp $frontendUrl

if ($backendOk -and $frontendOk) {
    Write-Host ""
    Write-Host "MathPlatform is up -> $frontendUrl"
} else {
    Write-Host ""
    Write-Host "WARNING: didn't get a response within the timeout."
    if (-not $backendOk)  { Write-Host "  - Backend not responding.  Check $backendLog / $backendLog.err" }
    if (-not $frontendOk) { Write-Host "  - Frontend not responding. Check $frontendLog / $frontendLog.err" }
}

if ($OpenChrome) {
    Open-InChrome $frontendUrl
}

} catch {
    Write-Host ""
    Write-Host "========================================"
    Write-Host "  MathPlatform failed to start"
    Write-Host "========================================"
    Write-Host $_.Exception.Message
    exit 1
}
