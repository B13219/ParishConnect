# Vinyrd Pilot Deployment Readiness

## Production architecture

Vinyrd Pilot v1.0 is deployed as one web service plus PostgreSQL:

```text
HTTPS domain
   |
   +-- /staff/    Vinyrd staff console
   +-- /member/   Vinyrd member webapp
   +-- /api/v1    FastAPI
   +-- /health
          |
          +-- PostgreSQL
```

Using one origin removes production CORS dependency between the web interfaces and API.

## Required environment

The legacy `PARISHCONNECT_` variable prefix is retained for compatibility.

```text
PARISHCONNECT_ENVIRONMENT=production
PARISHCONNECT_PUBLIC_BASE_URL=https://<your-domain>
PARISHCONNECT_CORS_ORIGINS=
PARISHCONNECT_DATABASE_URL=<managed PostgreSQL connection>
PARISHCONNECT_AUTH_TOKEN_SECRET=<32+ random characters>
PARISHCONNECT_QR_TOKEN_SECRET=<32+ random characters>
PARISHCONNECT_PASSWORD_SALT=<32+ random characters>
PARISHCONNECT_ACCESS_TOKEN_MINUTES=120
PARISHCONNECT_DEMO_PASSWORD=disabled
```

For the first launch only:

```text
PARISHCONNECT_BOOTSTRAP_ADMIN_NAME=<named administrator>
PARISHCONNECT_BOOTSTRAP_ADMIN_EMAIL=<administrator login>
PARISHCONNECT_BOOTSTRAP_ADMIN_PASSWORD=<strong temporary password>
PARISHCONNECT_BOOTSTRAP_BRANCH_NAME=<church name>
PARISHCONNECT_BOOTSTRAP_BRANCH_LOCATION=<location>
```

After the first administrator has logged in and changed credentials, remove the
bootstrap password from the hosting environment.

## Release commands

The production container runs:

```text
alembic upgrade head
python -m app.scripts.bootstrap_admin
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Run the strict gate:

```text
python -m app.scripts.check_deployment_readiness --strict
```

## Pilot journey

Before importing real church records, verify:

```text
Admin login
→ member registration
→ member account activation
→ member login
→ attendance
→ giving
→ prayer request
→ pastor follow-up
→ sermon publish
→ member sermon visibility
```

The automated version lives in `app.scripts.pilot_smoke`.

## Backup and recovery

The Admin backup manifest verifies application export scope, but production recovery
must also validate the database itself.

Run:

```text
python -m app.scripts.verify_backup_restore
```

The command creates a real PostgreSQL dump, restores it to a temporary database,
compares every application table row count, and deletes the temporary database.

Do not import real church data until this restore test passes on the intended hosting
database.
