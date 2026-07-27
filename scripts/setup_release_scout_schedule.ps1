<#
.SYNOPSIS
  Register a weekly /release-scout run via Windows Task Scheduler.

.DESCRIPTION
  WHY: Claude Code's native CronCreate is session-only (gone when the session exits,
  auto-expires after 7 days), so it cannot host a durable weekly self-dev scan. This
  registers a durable Windows Scheduled Task instead.

  SAFETY: dry-run by DEFAULT. Prints the task it would register and changes nothing.
  Re-run with -Apply to actually register it.

  ONE LINE YOU MUST VERIFY: the headless invocation ($ClaudeCmd). Whether
  `claude -p "/release-scout"` triggers the command in your install is environment-
  specific and NOT verified here -- confirm it runs interactively first.

.EXAMPLE
  .\setup_release_scout_schedule.ps1            # dry run
  .\setup_release_scout_schedule.ps1 -Apply     # register the task
#>
param(
  [switch]$Apply,
  [string]$ClaudeCmd = 'claude -p "/release-scout"',
  # Monday 09:07 local (off-minute on purpose).
  [string]$Time = '09:07'
)

$TaskName = 'release-scout-weekly'

Write-Host "Weekly /release-scout schedule (Windows Task Scheduler)"
Write-Host "  task    : $TaskName"
Write-Host "  when    : every Monday at $Time (local)"
Write-Host "  command : $ClaudeCmd"
Write-Host ""

if (-not $Apply) {
  Write-Host "DRY RUN -- nothing changed. To install it:"
  Write-Host "  1. Verify the command works interactively first: $ClaudeCmd"
  Write-Host "  2. Re-run:  .\setup_release_scout_schedule.ps1 -Apply"
  return
}

$action  = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument "/c $ClaudeCmd"
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At $Time
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Force | Out-Null
Write-Host "Installed task '$TaskName'."
Write-Host "Remove later with:  Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
