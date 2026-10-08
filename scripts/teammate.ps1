[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('build', 'start', 'stop', 'status', 'health')]
    [string]$Operation,
    [switch]$Scoring
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$EnvPath = Join-Path $RepoRoot '.env.teammate.local'
if (-not (Test-Path -LiteralPath $EnvPath)) { throw 'Create .env.teammate.local with new-teammate-env.ps1 first.' }
$Base = @('compose', '-p', 'sentinel-team', '--env-file', $EnvPath,
    '-f', 'infrastructure/compose.yaml', '-f', 'infrastructure/compose.laptop-local.yaml',
    '-f', 'infrastructure/compose.teammate.yaml')
if ($Scoring -or $Operation -in @('stop', 'status', 'health')) { $Base += @('--profile', 'scoring') }

function Invoke-TeamCompose([string[]]$ComposeArgs) {
    & docker @Base @ComposeArgs
    if ($LASTEXITCODE -ne 0) { throw 'Teammate Compose operation failed; the owner deployment was not selected.' }
}

Push-Location $RepoRoot
try {
    # Inspect effective settings privately; never print rendered config or URIs.
    $Rendered = & docker @Base config --format json
    if ($LASTEXITCODE -ne 0) { throw 'Teammate configuration is invalid.' }
    $Config = ($Rendered -join "`n") | ConvertFrom-Json
    if ($Config.name -ne 'sentinel-team' -or
        $Config.volumes.postgres_data.name -ne 'sentinel-team-postgres-data' -or
        $Config.volumes.redis_data.name -ne 'sentinel-team-redis-data' -or
        $Config.services.api.environment.SCORING_ACTIVATION_HOLD -ne '1') {
        throw 'This developer helper requires its separate project/volumes and activation hold.'
    }
    if ($Operation -in @('build', 'start')) {
        foreach ($Key in @('POSTGRES_PASSWORD', 'REDIS_PASSWORD', 'RESULT_API_TOKEN', 'REVIEW_API_TOKEN')) {
            $Match = [regex]::Match([IO.File]::ReadAllText($EnvPath), "(?m)^$Key=([0-9a-f]{64})\r?$" )
            if (-not $Match.Success) { throw "Generate the private $Key value first." }
        }
    }
    if ($Operation -eq 'build') {
        $Services = @('api', 'web')
        if ($Scoring) { $Services += 'scoring-worker' }
        Invoke-TeamCompose (@('build') + $Services)
    }
    elseif ($Operation -eq 'start') {
        if ($Scoring) {
            $Model = $Config.services.'scoring-worker'.volumes | Where-Object target -eq '/model'
            $Gate = $Config.services.'scoring-worker'.volumes | Where-Object target -eq '/gates'
            foreach ($Item in @(@{Path=(Join-Path $Model.source 'manifest.json'); Pin='1e421627b7548e2a35de0e598fea23baa6996e316106346652d004c46d24d696'},
                @{Path=(Join-Path $Gate.source 'report.json'); Pin='abdffc8e3e90bfe040c72577de795e48a7d514e6de470adcf7dfb9732a2e18c2'})) {
                if (-not (Test-Path -LiteralPath $Item.Path) -or (Get-FileHash -LiteralPath $Item.Path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Item.Pin) {
                    throw 'Trusted private frozen bundle/gate evidence is missing or changed.'
                }
            }
        }
        Invoke-TeamCompose @('up', '-d', '--no-deps', '--no-build', '--wait', '--wait-timeout', '60', 'postgres', 'redis')
        # Wait for the API's forward migration/startup before launching consumers.
        Invoke-TeamCompose @('up', '-d', '--no-deps', '--no-build', '--wait', '--wait-timeout', '60', 'api')
        $Services = @('publisher', 'web')
        if ($Scoring) { $Services += 'scoring-worker' }
        Invoke-TeamCompose (@('up', '-d', '--no-deps', '--no-build', '--wait', '--wait-timeout', '60') + $Services)
        if ($Scoring) {
            $HealthCode = "import pg from 'pg';const p=new pg.Pool({connectionString:process.env.POSTGRES_URL});try{const r=await p.query('SELECT ready,blocked,extract(epoch FROM clock_timestamp()-heartbeat_at) AS age FROM scoring_worker_health WHERE run_id=`$1',[process.env.SCORING_RUN_ID]);const h=r.rows[0];if(!h?.ready||h.blocked||Number(h.age)>5)process.exitCode=2;}catch{process.exitCode=2;}finally{await p.end();}"
            $Deadline = [DateTime]::UtcNow.AddSeconds(30)
            do {
                & docker exec sentinel-team-api-1 node --input-type=module -e $HealthCode
                if ($LASTEXITCODE -eq 0) { break }
                if ([DateTime]::UtcNow -ge $Deadline) { throw 'The scorer did not become ready; keep ingestion stopped and investigate its private startup logs.' }
                Start-Sleep -Milliseconds 250
            } while ($true)
            Write-Output 'Frozen scorer initialized and reconciled; worker health is ready/unblocked.'
        }
        Write-Output 'Local services started. Scoring activation remains held on this independent deployment.'
    }
    elseif ($Operation -eq 'stop') { Invoke-TeamCompose @('stop') }
    elseif ($Operation -eq 'status') { Invoke-TeamCompose @('ps') }
    else {
        foreach ($Check in @(@{Name='Infrastructure';Port=$Config.services.api.ports[0].published;Path='/ready'},
            @{Name='Dashboard';Port=$Config.services.web.ports[0].published;Path='/'},
            @{Name='Dashboard data';Port=$Config.services.web.ports[0].published;Path='/api/v1/dashboard?range=24h'})) {
            $Response = Invoke-WebRequest -UseBasicParsing -Uri ('http://127.0.0.1:' + $Check.Port + $Check.Path)
            Write-Output ($Check.Name + ': HTTP ' + $Response.StatusCode)
        }
        Write-Output 'Scoring readiness stays HTTP 503 while the developer activation hold is set.'
    }
}
finally { Pop-Location }
