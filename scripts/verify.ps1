$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$ComposeFile = Join-Path $RepoRoot "infrastructure\compose.yaml"

function Invoke-Checked {
    param(
        [Parameter(Mandatory)] [string] $Command,
        [Parameter(ValueFromRemainingArguments)] [string[]] $Arguments
    )
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Command exited with code $LASTEXITCODE"
    }
}

function Invoke-Compose {
    param([Parameter(ValueFromRemainingArguments)] [string[]] $Arguments)
    Invoke-Checked docker compose -f $ComposeFile @Arguments
}

try {
    Write-Output "[backend] format, lint, types, tests"
    Push-Location (Join-Path $RepoRoot "backend")
    try {
        Invoke-Checked uv run ruff format --check .
        Invoke-Checked uv run ruff check .
        Invoke-Checked uv run mypy src
        Invoke-Checked uv run pytest
    }
    finally {
        Pop-Location
    }

    Write-Output "[frontend] format, lint, types, tests, build"
    Push-Location (Join-Path $RepoRoot "frontend")
    try {
        Invoke-Checked npm run format:check
        Invoke-Checked npm run lint
        Invoke-Checked npm run typecheck
        Invoke-Checked npm run test
        Invoke-Checked npm run build
    }
    finally {
        Pop-Location
    }

    Write-Output "[compose] validate, build, start, wait"
    Invoke-Compose config --quiet
    Invoke-Compose build
    Invoke-Compose up -d --wait
    Invoke-Compose ps

    $ApiPort = if ($env:API_PORT) { $env:API_PORT } else { "18000" }
    $WebPort = if ($env:WEB_PORT) { $env:WEB_PORT } else { "15173" }

    Write-Output "[smoke] API and web"
    $Health = Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/health" -TimeoutSec 10
    $Ready = Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/ready" -TimeoutSec 10
    $Web = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$WebPort/" -TimeoutSec 10
    if ($Health.status -ne "ok" -or $Ready.status -ne "ready" -or $Web.StatusCode -ne 200) {
        throw "Smoke checks returned unexpected responses"
    }

    Write-Output "[failure semantics] pause Redis; health stays live and readiness fails"
    Invoke-Compose pause redis
    $HealthWhileRedisDown = Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/health" -TimeoutSec 10
    if ($HealthWhileRedisDown.status -ne "ok") {
        throw "Liveness failed while Redis was paused"
    }
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/ready" -TimeoutSec 10
        throw "Readiness incorrectly succeeded while Redis was paused"
    }
    catch {
        $Response = $_.Exception.Response
        if (-not $Response -or [int]$Response.StatusCode -ne 503) {
            throw
        }
    }

    Write-Output "[recovery] unpause Redis and restart without rebuilding"
    Invoke-Compose unpause redis
    Invoke-Compose restart
    Invoke-Compose up -d --wait
    $Recovered = Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/ready" -TimeoutSec 10
    if ($Recovered.status -ne "ready") {
        throw "Readiness did not recover after restart"
    }

    Write-Output "[logs] recent bounded output"
    Invoke-Compose logs --no-color --tail 100
    Write-Output "Task 2 verification passed"
}
finally {
    & docker compose -f $ComposeFile down | Out-Null
}
