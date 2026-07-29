# -----------------------------------------------------------------
#  MathPlatform - Remove the notification cron scheduled tasks.
# -----------------------------------------------------------------
$names = @('MathPlatform-AnalyticsAlerts', 'MathPlatform-DailyDigest')
foreach ($name in $names) {
    $existing = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false
        Write-Host "Removed task '$name'"
    } else {
        Write-Host "Task '$name' not found (already removed?)"
    }
}
