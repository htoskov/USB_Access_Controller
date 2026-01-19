# --- Self-elevate to Admin ---
if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
  ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {

  Start-Process powershell -Verb RunAs `
    -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
  exit
}

# ---- After elevation ----

$Project = Join-Path $env:USERPROFILE "Desktop\USB_Access_Controller"
$Script  = Join-Path $Project "hid_guard_tray.py"

# Find Python (prefer pythonw.exe for no console)
$Py = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $Py) {
  $Py = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
}
if (-not $Py) {
  $Py = (Get-Command py.exe -ErrorAction Stop).Source
}

Write-Host "Starting HID Guard Tray elevated..."
Write-Host "Python: $Py"
Write-Host "Script: $Script"

Start-Process $Py -ArgumentList "`"$Script`"" -WorkingDirectory $Project

Write-Host "Launched."
