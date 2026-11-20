# Quick Launcher for Evaluator Live Simulation Demo
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "🚀 Sentinel AI - Interactive Live Simulation Launcher" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host "Checking health of local Sentinel AI Docker services..." -ForegroundColor Yellow
$health = powershell -ExecutionPolicy Bypass -File scripts/teammate.ps1 health
$health | Write-Host

Write-Host "`nLaunching Playwright Interactive Chrome Simulation..." -ForegroundColor Green
node scripts/live-demo.cjs
