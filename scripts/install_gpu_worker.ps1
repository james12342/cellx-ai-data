$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$root = 'C:\Users\User\CellAI-5090'
$worker = Join-Path $root 'worker'
$secret = Join-Path $worker 'worker-token'
$admins = [Security.Principal.SecurityIdentifier]::new('S-1-5-32-544')
$system = [Security.Principal.SecurityIdentifier]::new('S-1-5-18')
$owner = [Security.Principal.WindowsIdentity]::GetCurrent().User
$acl = [Security.AccessControl.FileSecurity]::new()
$acl.SetOwner($owner)
$acl.SetAccessRuleProtection($true, $false)
foreach ($sid in @($admins, $system, $owner)) {
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid, 'FullControl', 'Allow'))
}
Set-Acl -LiteralPath $secret -AclObject $acl
$action = New-ScheduledTaskAction -Execute "$root\venv\Scripts\python.exe" -Argument "-u $worker\gpu_portrait_worker.py" -WorkingDirectory $worker
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName 'CellAI-5090-GPU-Worker' -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Outbound authenticated GPU job worker for app.cellaidata.com' -Force | Select-Object TaskName,State
Start-ScheduledTask -TaskName 'CellAI-5090-GPU-Worker'
Get-ScheduledTask -TaskName 'CellAI-5090-GPU-Worker' | Select-Object TaskName,State
