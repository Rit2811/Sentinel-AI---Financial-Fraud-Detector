#Requires -RunAsAdministrator
[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$ReportPath)

$ErrorActionPreference = 'Stop'
$record = @{ status = 'STARTING'; configuration_changed = $false }
function Get-NtpOffsets([int]$Count) {
    $output = (& w32tm /stripchart /computer:time.windows.com /dataonly /samples:$Count 2>&1) -join "`n"
    if ($LASTEXITCODE -ne 0) { throw 'NTP measurement failed' }
    $matches = [regex]::Matches($output, '(?m),\s*(?<offset>[+-]\d+\.\d+)s\s*$')
    if ($matches.Count -ne $Count) { throw 'Incomplete NTP measurements' }
    return @($matches | ForEach-Object {
        [double]::Parse($_.Groups['offset'].Value, [Globalization.CultureInfo]::InvariantCulture)
    })
}

try {
    $before = @(Get-NtpOffsets 5)
    $ordered = @($before | Sort-Object)
    $offset = $ordered[2]
    if (($ordered[-1] - $ordered[0]) -gt 0.05 -or [Math]::Abs($offset) -gt 5) {
        throw 'Clock correction exceeds safe measured bounds'
    }
    $record.before_offsets_seconds = $before
    $record.correction_seconds = $offset
    $record.corrected_at = [DateTime]::UtcNow.ToString('o')
    Set-Date -Date ((Get-Date).AddSeconds($offset)) | Out-Null
    & w32tm /resync /rediscover | Out-Null
    $record.resync_exit_code = $LASTEXITCODE
    $after = @(Get-NtpOffsets 3)
    $record.after_offsets_seconds = $after
    if (@($after | Where-Object { [Math]::Abs($_) -gt 0.05 }).Count -gt 0) {
        throw 'Clock verification remains outside tolerance'
    }
    $record.status = 'PASS'
} catch {
    $record.status = 'FAIL'
    $record.error_type = $_.Exception.GetType().Name
} finally {
    $record.completed_at = [DateTime]::UtcNow.ToString('o')
    $record | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $ReportPath -Encoding UTF8
}
if ($record.status -ne 'PASS') { exit 1 }
