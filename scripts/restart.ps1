# -----------------------------------------------------------------
#  MathPlatform - Restart (stop, then start, backend + frontend)
#
#  Manual use:  double-click restart.bat  (in the project root)
# -----------------------------------------------------------------
param(
    [switch]$OpenChrome
)

$scriptDir = $PSScriptRoot

. (Join-Path $scriptDir 'hacker_theme.ps1')

Initialize-HackerConsole -Title 'MathPlatform - Restart'
Show-MatrixIntro -DurationMs 900
Write-HackerBanner -Subtitle 'RESTARTING SYSTEM...'
Write-Typewriter '  >> Cycling backend + frontend...' -Color Cyan
Write-Host ''

# Run stop.ps1 and start.ps1 as their own scripts rather than duplicating
# their logic - each already renders its own banner/boot-sequence, so a
# restart naturally reads as "shutdown sequence, then boot sequence"
# instead of a third, separately-maintained copy of the same steps.
& (Join-Path $scriptDir 'stop.ps1')

Start-Sleep -Milliseconds 400

if ($OpenChrome) {
    & (Join-Path $scriptDir 'start.ps1') -OpenChrome
} else {
    & (Join-Path $scriptDir 'start.ps1')
}
