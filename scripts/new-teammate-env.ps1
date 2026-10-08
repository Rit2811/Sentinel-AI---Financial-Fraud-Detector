[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9_-]{1,128}$')]
    [string]$ReviewerId,
    [string]$OutputPath
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutputPath) { $OutputPath = Join-Path $RepoRoot '.env.teammate.local' }
$TargetPath = [IO.Path]::GetFullPath($OutputPath)
if (-not $TargetPath.StartsWith($RepoRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'The credential file must stay inside this checkout.'
}
if (Test-Path -LiteralPath $TargetPath) { throw 'Existing credential file preserved; choose a new path.' }
$Text = [IO.File]::ReadAllText((Join-Path $RepoRoot 'infrastructure\teammate.env.example'))
$Generator = [Security.Cryptography.RandomNumberGenerator]::Create()
try {
    foreach ($Key in @('POSTGRES_PASSWORD', 'REDIS_PASSWORD', 'RESULT_API_TOKEN', 'REVIEW_API_TOKEN')) {
        $Bytes = New-Object byte[] 32
        $Generator.GetBytes($Bytes)
        $Secret = [BitConverter]::ToString($Bytes).Replace('-', '').ToLowerInvariant()
        $Text = [regex]::Replace($Text, "(?m)^$Key=.*$", "$Key=$Secret")
        [Array]::Clear($Bytes, 0, $Bytes.Length)
    }
}
finally { $Generator.Dispose() }
$Text = [regex]::Replace($Text, '(?m)^REVIEWER_ID=.*$', 'REVIEWER_ID=' + $ReviewerId)
$Text = [regex]::Replace($Text, '(?m)^SCORING_RUN_ID=.*$', 'SCORING_RUN_ID=' + [guid]::NewGuid().ToString())
$Text = [regex]::Replace($Text, '(?m)^SENTINEL_REPO_ROOT=.*$', 'SENTINEL_REPO_ROOT="' + $RepoRoot.Replace('\', '/') + '"')
$Encoding = New-Object System.Text.UTF8Encoding($false)
$File = [IO.File]::Open($TargetPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try {
    $Payload = $Encoding.GetBytes($Text)
    $File.Write($Payload, 0, $Payload.Length)
}
finally { $File.Dispose() }
Write-Output 'Created a private teammate configuration with four fresh secrets and a new run; secret values were not printed.'
