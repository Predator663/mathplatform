' MathPlatform - runs start.ps1 completely invisibly (no console flash).
' Used by the Startup-folder shortcut created by install_autostart.ps1.
' To also auto-open Chrome at every login, add " -OpenChrome" after start.ps1"" below.

Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

Set shell = CreateObject("WScript.Shell")
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & scriptDir & "\start.ps1"""
shell.Run cmd, 0, False
