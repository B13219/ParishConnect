# Vinyrd API

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
docker compose up -d postgres
alembic upgrade head
python -m app.scripts.seed_demo
uvicorn app.main:app --reload --port 8003
```

Open:

- Staff console: `http://127.0.0.1:8003/staff/`
- Member app: `http://127.0.0.1:8003/member/`
- API docs: `http://127.0.0.1:8003/docs`

The older separate static server on port 5173 remains usable for local frontend work,
but production serves both interfaces from FastAPI on the same origin.

## Production bootstrap

Set the one-time bootstrap variables, run migrations, then:

```powershell
python -m app.scripts.bootstrap_admin
```

The bootstrap script creates the first branch, standard roles, and administrator when
needed. It never resets an existing administrator's password on restart.

## Readiness

```powershell
python -m app.scripts.check_deployment_readiness --strict
```

## Backup + restore verification

PostgreSQL client tools are required:

```powershell
python -m app.scripts.verify_backup_restore
```

This creates a real custom-format `pg_dump`, restores it into a temporary database,
compares table row counts, and removes the temporary restore database.
