$env:DOCKER_CONFIG = "$PSScriptRoot\.docker-cli-config"
docker compose up -d postgres

Write-Host ""
Write-Host "If Docker starts successfully, run:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "  alembic upgrade head"
Write-Host "  python -m app.scripts.seed_demo"

