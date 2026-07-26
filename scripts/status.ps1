# -----------------------------------------------------------------
#  MathPlatform - Status check
# -----------------------------------------------------------------
function Show-Port($port, $label) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        Write-Host "$label (port $port): RUNNING  (PID $($conn[0].OwningProcess))"
    } else {
        Write-Host "$label (port $port): not running"
    }
}

Show-Port 8000 'Backend '
Show-Port 5173 'Frontend'
