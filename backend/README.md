# ParishConnect API

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8003
```

## Local PostgreSQL

Start a local demo database with Docker:

```powershell
docker compose up -d postgres
```

Apply the database schema:

```powershell
alembic upgrade head
```

Load safe sample data:

```powershell
python -m app.scripts.seed_demo
```

Run the deployment readiness check:

```powershell
python -m app.scripts.check_deployment_readiness
```

## Immediate Demo Database Fallback

If Docker Desktop or PostgreSQL is not available, create a local SQLite demo database with the same SQLAlchemy models:

```powershell
python -m app.scripts.init_demo_sqlite
.\run-demo.ps1
```

This is for local presentation only. PostgreSQL remains the intended development and production database.

Health check:

```text
GET /health
```

Product overview:

```text
GET /api/v1/
```

Expected response:

```json
{
  "status": "ok",
  "service": "ParishConnect API",
  "version": "0.1.0"
}
```

## Next Backend Steps

1. Replace demo secrets in `.env` before handling real records.
2. Point `PARISHCONNECT_DATABASE_URL` at the intended PostgreSQL database.
3. Run migrations with `alembic upgrade head`.
4. Create named administrator and staff accounts.
5. Run `python -m app.scripts.check_deployment_readiness --strict` before client pilot deployment.

## Database

The initial schema is captured in:

```text
alembic/versions/20260710_0001_initial_schema.py
```

It creates the first 11 tables for branches, users, roles, members, visitors, ministries, events, attendance, messages, and contributions.

## Demo Data Safety

The seed script uses fake names, fake `.test` emails, and fake phone numbers. Do not import real church records until authentication, role permissions, backups, and import validation are in place.

For deployment details, see `../docs/deployment-readiness.md`.
