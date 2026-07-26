# -----------------------------------------------------------------
#  MathPlatform - Install autostart
#  Run this ONCE. From then on, MathPlatform starts silently in the
#  background every time you log in to Windows - no manual step.
#  Undo with uninstall_autostart.ps1.
# -----------------------------------------------------------------
$scriptDir     = $PSScriptRoot
$vbsPath       = Join-Path $scriptDir 'start_hidden.vbs'
$startupFolder = [Environment]::GetFolderPath('Startup')
$shortcutPath  = Join-Path $startupFolder 'MathPlatform.lnk'

if (-not (Test-Path $vbsPath)) {
    Write-Host "ERROR: start_hidden.vbs not found next to this script."
    exit 1
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath       = "$env:WINDIR\System32\wscript.exe"
$shortcut.Arguments        = "`"$vbsPath`""
$shortcut.WorkingDirectory = $scriptDir
$shortcut.Description      = "Auto-start MathPlatform (backend + frontend) at login"
$shortcut.Save()

Write-Host ""
Write-Host "Installed. MathPlatform will now start automatically every time you log in."
Write-Host "Shortcut created at: $shortcutPath"
Write-Host ""
Write-Host "It starts silently - no window will appear. Give it ~20-30 seconds after"
Write-Host "login, then open Chrome to http://localhost:5173"
Write-Host ""
Write-Host "To stop auto-starting: run uninstall_autostart.ps1"
