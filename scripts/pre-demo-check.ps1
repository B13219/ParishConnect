param(
    [string]$BackendUrl = "http://127.0.0.1:8003",
    [string]$FrontendUrl = "http://127.0.0.1:5173"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendPath = Join-Path $projectRoot "backend"
$pythonPath = Join-Path $backendPath ".venv\Scripts\python.exe"

Write-Host "ParishConnect pre-demo check"
Write-Host ""

if (-not (Test-Path $pythonPath)) {
    Write-Host "[WARN] Backend virtual environment not found at $pythonPath"
    Write-Host "       Create it with: cd backend; python -m venv .venv; .\.venv\Scripts\Activate.ps1; python -m pip install -e `".[dev]`""
} else {
    Push-Location $backendPath
    try {
        Write-Host "[CHECK] Deployment readiness"
        & $pythonPath -m app.scripts.check_deployment_readiness
    } finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "[CHECK] Backend health: $BackendUrl/health"
try {
    $health = Invoke-RestMethod -Uri "$BackendUrl/health" -TimeoutSec 5
    Write-Host "[OK] Backend health:" ($health | ConvertTo-Json -Compress)
} catch {
    Write-Host "[WARN] Backend is not reachable. Start it with:"
    Write-Host "       cd backend; .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8003"
}

Write-Host ""
Write-Host "[CHECK] Frontend page: $FrontendUrl"
try {
    $frontend = Invoke-WebRequest -Uri $FrontendUrl -TimeoutSec 5
    Write-Host "[OK] Frontend HTTP status:" $frontend.StatusCode
} catch {
    Write-Host "[WARN] Frontend is not reachable. Start it with:"
    Write-Host "       cd frontend; python -m http.server 5173"
}

Write-Host ""
Write-Host "Pre-demo reminder: use fake data unless import/privacy/backups are approved."
