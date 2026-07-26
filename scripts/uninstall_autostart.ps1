# -----------------------------------------------------------------
#  MathPlatform - Remove autostart
# -----------------------------------------------------------------
$startupFolder = [Environment]::GetFolderPath('Startup')
$shortcutPath  = Join-Path $startupFolder 'MathPlatform.lnk'

if (Test-Path $shortcutPath) {
    Remove-Item $shortcutPath -Force
    Write-Host "Removed autostart shortcut. MathPlatform will no longer start automatically at login."
} else {
    Write-Host "No autostart shortcut found - nothing to remove."
}
