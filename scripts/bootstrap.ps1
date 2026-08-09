$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

Push-Location (Join-Path $RepoRoot "backend")
try {
    & uv sync --frozen
    if ($LASTEXITCODE -ne 0) { throw "uv sync failed with code $LASTEXITCODE" }
}
finally {
    Pop-Location
}

Push-Location (Join-Path $RepoRoot "frontend")
try {
    & npm ci
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed with code $LASTEXITCODE" }
}
finally {
    Pop-Location
}
