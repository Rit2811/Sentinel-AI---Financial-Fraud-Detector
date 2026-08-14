$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

Push-Location (Join-Path $RepoRoot "backend")
try {
    & npm ci
    if ($LASTEXITCODE -ne 0) { throw "backend npm ci failed with code $LASTEXITCODE" }
}
finally {
    Pop-Location
}

Push-Location (Join-Path $RepoRoot "frontend")
try {
    & npm ci
    if ($LASTEXITCODE -ne 0) { throw "frontend npm ci failed with code $LASTEXITCODE" }
}
finally {
    Pop-Location
}
