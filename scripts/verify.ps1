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
    Write-Output "[backend] format, lint, unit tests"
    Push-Location (Join-Path $RepoRoot "backend")
    try {
        Invoke-Checked npm run format:check
        Invoke-Checked npm run lint
        Invoke-Checked npm test
    }
    finally {
        Pop-Location
    }

    Write-Output "[ml] lock, format, lint, unit tests (dataset download excluded)"
    Push-Location (Join-Path (Join-Path $RepoRoot "services") "ml")
    try {
        $PreviousUvCache = $env:UV_CACHE_DIR
        $PreviousUvPython = $env:UV_PYTHON_INSTALL_DIR
        $env:UV_CACHE_DIR = ".uv-cache"
        $env:UV_PYTHON_INSTALL_DIR = ".uv-python"
        Invoke-Checked uv sync --locked
        Invoke-Checked uv run ruff format --check .
        Invoke-Checked uv run ruff check .
        Invoke-Checked uv run pytest -q
    }
    finally {
        $env:UV_CACHE_DIR = $PreviousUvCache
        $env:UV_PYTHON_INSTALL_DIR = $PreviousUvPython
        Pop-Location
    }

    Write-Output "[frontend] format, lint, tests, build"
    Push-Location (Join-Path $RepoRoot "frontend")
    try {
        Invoke-Checked npm run format:check
        Invoke-Checked npm run lint
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
    $PostgresPort = if ($env:POSTGRES_PORT) { $env:POSTGRES_PORT } else { "15432" }
    $PostgresDatabase = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "sentinel" }
    $PostgresUser = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "sentinel" }
    $PostgresPassword = if ($env:POSTGRES_PASSWORD) { $env:POSTGRES_PASSWORD } else { "sentinel_local_only" }
    $Task3DatabaseUrl = "postgresql://${PostgresUser}:${PostgresPassword}@127.0.0.1:${PostgresPort}/${PostgresDatabase}"

    Write-Output "[database] Task 3 empty migration cycle and integration tests"
    Push-Location (Join-Path $RepoRoot "backend")
    try {
        $PreviousDatabaseUrl = $env:DATABASE_URL
        $PreviousTestDatabaseUrl = $env:TEST_DATABASE_URL
        $env:DATABASE_URL = $Task3DatabaseUrl
        $env:TEST_DATABASE_URL = $Task3DatabaseUrl
        Invoke-Checked npm run migrate:up
        Invoke-Checked npm run migrate:down
        Invoke-Checked npm run migrate:up
        Invoke-Checked npm run test:integration
    }
    finally {
        $env:DATABASE_URL = $PreviousDatabaseUrl
        $env:TEST_DATABASE_URL = $PreviousTestDatabaseUrl
        Pop-Location
    }

    Write-Output "[smoke] API and web"
    $Health = Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/health" -TimeoutSec 10
    $Ready = Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/ready" -TimeoutSec 10
    $Web = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$WebPort/" -TimeoutSec 10
    if ($Health.status -ne "ok" -or $Ready.status -ne "ready" -or $Web.StatusCode -ne 200) {
        throw "Smoke checks returned unexpected responses"
    }

    Write-Output "[smoke] Task 3 authorization ingestion"
    $SmokeEventId = [guid]::NewGuid().ToString()
    $SmokeAuthorizationId = [guid]::NewGuid().ToString()
    $SmokeHeaders = @{
        "Idempotency-Key" = [guid]::NewGuid().ToString()
        "X-Correlation-ID" = [guid]::NewGuid().ToString()
    }
    $SmokeBody = @{
        schema_version = "1.0"
        event_id = $SmokeEventId
        authorization_id = $SmokeAuthorizationId
        occurred_at = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
        data_origin = "synthetic_enriched"
        channel = "card_not_present"
        amount_minor = 129900
        currency = "INR"
        card_token = "card_tok_smoke_001"
        account_token = "acct_tok_smoke_001"
        merchant_id = "merchant_smoke_001"
        merchant_country = "IN"
        entry_mode = "ecommerce"
        device_token = "device_tok_smoke_001"
    } | ConvertTo-Json
    $SmokeResponse = Invoke-WebRequest -UseBasicParsing -Method Post -Uri "http://127.0.0.1:$ApiPort/api/v1/authorization-events" -Headers $SmokeHeaders -ContentType "application/json" -Body $SmokeBody -TimeoutSec 10
    $SmokePayload = $SmokeResponse.Content | ConvertFrom-Json
    if ($SmokeResponse.StatusCode -ne 202 -or $SmokePayload.outcome -ne "accepted") {
        throw "Task 3 smoke check returned an unexpected response"
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
    Write-Output "Task 2/3 regression and Task 4 code verification passed"
}
finally {
    & docker compose -f $ComposeFile down | Out-Null
}
