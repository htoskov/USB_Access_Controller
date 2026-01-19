# --- Self-elevate to Admin ---
if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
  ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {

  Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
  exit
}


$Project  = Join-Path $env:USERPROFILE "Desktop\USB_Access_Controller"
$Script   = Join-Path $Project "hid_guard_tray.py"
$TaskName = "USB_Access_Control_Tray"

$Py = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $Py) {
  $Py = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
}
if (-not $Py) {
  $Py = (Get-Command py.exe -ErrorAction Stop).Source
}

$Action  = New-ScheduledTaskAction -Execute $Py -Argument "`"$Script`"" -WorkingDirectory $Project
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Force
Start-ScheduledTask -TaskName $TaskName

Write-Host "Installed + started scheduled task: $TaskName"
