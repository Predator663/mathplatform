# -----------------------------------------------------------------
#  MathPlatform - Status check
# -----------------------------------------------------------------
$scriptDir = $PSScriptRoot
. (Join-Path $scriptDir 'hacker_theme.ps1')

function Show-Port($port, $label) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        Write-Host ("[ONLINE ] {0} (port {1}) - PID {2}" -f $label, $port, $conn[0].OwningProcess) -ForegroundColor Green
    } else {
        Write-Host ("[OFFLINE] {0} (port {1})" -f $label, $port) -ForegroundColor Red
    }
}

Initialize-HackerConsole -Title 'MathPlatform - Status'
Show-MatrixIntro -DurationMs 700
Write-HackerBanner -Subtitle 'SYSTEM STATUS'

Show-Port 8000 'Backend '
Show-Port 5173 'Frontend'
Write-Host ''
