$ErrorActionPreference = "Stop"
$RepoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$Targets = @(
    "backend\.venv",
    "backend\.pytest_cache",
    "backend\.mypy_cache",
    "backend\.ruff_cache",
    "frontend\node_modules",
    "frontend\dist",
    "frontend\coverage"
)

foreach ($RelativeTarget in $Targets) {
    $Target = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $RelativeTarget))
    if (-not $Target.StartsWith($RepoRoot + [System.IO.Path]::DirectorySeparatorChar)) {
        throw "Refusing to clean path outside repository: $Target"
    }
    if (Test-Path -LiteralPath $Target) {
        Remove-Item -LiteralPath $Target -Recurse -Force
    }
}
