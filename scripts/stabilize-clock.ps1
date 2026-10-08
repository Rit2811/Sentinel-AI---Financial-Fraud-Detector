#Requires -RunAsAdministrator
[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$ReportPath)
$ErrorActionPreference = 'Stop'
$record = @{ status = 'STARTING'; settings_changed = $false }
$key = 'HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\Config'
$parameters = 'HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\Parameters'
try {
    if ((Get-CimInstance Win32_ComputerSystem).PartOfDomain) { throw 'Managed domain clock must be configured by its administrator' }
    $before = Get-ItemProperty -LiteralPath $key
    $peers = Get-ItemProperty -LiteralPath $parameters
    $record.before = @{ MinPollInterval=$before.MinPollInterval; MaxPollInterval=$before.MaxPollInterval; NtpServer=$peers.NtpServer; Type=$peers.Type }
    $record | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $ReportPath -Encoding UTF8
    Set-ItemProperty -LiteralPath $key -Name MinPollInterval -Value 6
    Set-ItemProperty -LiteralPath $key -Name MaxPollInterval -Value 6
    & w32tm /config /manualpeerlist:time.windows.com,0x8 /syncfromflags:manual /update | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Time service configuration failed' }
    $record.settings_changed=$true
    Restart-Service w32time
    $repair = Join-Path (Split-Path -Parent $ReportPath) 'stable-clock-correction.json'
    & powershell.exe -NoProfile -File (Join-Path $PSScriptRoot 'synchronize-clock.ps1') -ReportPath $repair
    if ($LASTEXITCODE -ne 0) { throw 'Bounded clock correction failed' }
    $record.poll_interval_seconds=64
    $record.status='PASS'
} catch {
    $record.status='FAIL'
    $record.error_type=$_.Exception.GetType().Name
    if ($record.before) {
        Set-ItemProperty -LiteralPath $key -Name MinPollInterval -Value $record.before.MinPollInterval
        Set-ItemProperty -LiteralPath $key -Name MaxPollInterval -Value $record.before.MaxPollInterval
        Set-ItemProperty -LiteralPath $parameters -Name NtpServer -Value $record.before.NtpServer
        Set-ItemProperty -LiteralPath $parameters -Name Type -Value $record.before.Type
        Restart-Service w32time
        $record.settings_rolled_back=$true
    }
} finally {
    $record.completed_at=[DateTime]::UtcNow.ToString('o')
    $record | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $ReportPath -Encoding UTF8
}
if ($record.status -ne 'PASS') { exit 1 }
