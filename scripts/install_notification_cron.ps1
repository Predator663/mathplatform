# -----------------------------------------------------------------
#  MathPlatform - Install notification cron (Windows Task Scheduler)
#  Run this ONCE (as your normal user - no admin needed). Creates two
#  scheduled tasks that call the Django management commands directly,
#  no server/CRON_SECRET/HTTP endpoint involved since this all runs
#  locally:
#    - MathPlatform-AnalyticsAlerts   daily 06:00  (at-risk / critical
#      risk / grade-integrity emails)
#    - MathPlatform-DailyDigest       daily 18:00  (digest emails)
#  Undo with uninstall_notification_cron.ps1.
#
#  NOTE: your PC has to be on (or wake from sleep) at those times for
#  the task to fire - this isn't a server, it's your machine.
# -----------------------------------------------------------------
$scriptDir  = $PSScriptRoot
$root       = Split-Path -Parent $scriptDir          # project root
$backendDir = Join-Path $root 'backend'
$venvPython = Join-Path $backendDir 'venv\Scripts\python.exe'
$logDir     = Join-Path $scriptDir 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (-not (Test-Path $venvPython)) {
    Write-Host "ERROR: venv not found at $venvPython - run start.ps1 once first to create it."
    exit 1
}

function Install-CronTask {
    param(
        [string]$TaskName,
        [string]$Command,
        [string]$LogFile,
        [string]$Time
    )
    # cmd.exe wrapper so stdout/stderr both land in the log file
    $wrappedArgs = "/c `"cd /d `"$backendDir`" && `"$venvPython`" manage.py $Command >> `"$LogFile`" 2>&1`""

    $action  = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument $wrappedArgs -WorkingDirectory $backendDir
    $trigger = New-ScheduledTaskTrigger -Daily -At $Time
    $settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
    Write-Host "Installed task '$TaskName' -> daily at $Time"
}

Install-CronTask -TaskName 'MathPlatform-AnalyticsAlerts' `
    -Command 'send_analytics_alerts' `
    -LogFile (Join-Path $logDir 'analytics_alerts.log') `
    -Time '06:00'

Install-CronTask -TaskName 'MathPlatform-DailyDigest' `
    -Command 'send_daily_digest' `
    -LogFile (Join-Path $logDir 'daily_digest.log') `
    -Time '18:00'

Write-Host ""
Write-Host "Done. View/edit these anytime in Task Scheduler under Task Scheduler Library"
Write-Host "(names: MathPlatform-AnalyticsAlerts, MathPlatform-DailyDigest)."
Write-Host "Logs land in: $logDir"
Write-Host ""
Write-Host "Test a task immediately without waiting for its time: right-click it in"
Write-Host "Task Scheduler -> Run. Or from PowerShell:"
Write-Host "  Start-ScheduledTask -TaskName 'MathPlatform-AnalyticsAlerts'"
Write-Host ""
Write-Host "To remove: run uninstall_notification_cron.ps1"
