[CmdletBinding()]
param()

# Run locally once PER credential, then paste the output into the ignored env file.
# This script does not read, write, or replace any existing credential file.
$credentialBytes = New-Object byte[] 32
$credentialGenerator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try {
    $credentialGenerator.GetBytes($credentialBytes)
    [BitConverter]::ToString($credentialBytes).Replace('-', '').ToLowerInvariant()
}
finally {
    [Array]::Clear($credentialBytes, 0, $credentialBytes.Length)
    $credentialGenerator.Dispose()
}
