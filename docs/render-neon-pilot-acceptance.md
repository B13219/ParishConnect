# Vinyrd synthetic pilot — Render ↔ Neon final acceptance checklist

Target: Friday 13 November 2026. **No real church data.** Service: `vinyrd-pilot-synthetic` in the Vinard Render workspace, deployed from `release/vinyrd-management-pilot-2026-11-13`, auto-deploy OFF. Public URL: https://vinyrd-pilot-synthetic.onrender.com/staff/.

Neon: dedicated `Vinyrd Pilot` project `gentle-sun-26451171`, Frankfurt, PostgreSQL 18, database `vinyrd_pilot`, branch `main`. Do not modify Imara Finance. The initial database has no tables until Alembic runs. Dedicated `vinyrd_runtime` is NOT a database administrator; the owner is `vinyrd_owner`.

## Required one-time secret setup in Render

Open https://dashboard.render.com/web/srv-dbpa0oe1egvs73bh2ba0 → Environment.

Use **the direct (non-pooler) Neon database URI** from the Neon console, not a pooled URL. Select database `vinyrd_pilot` and two *different* roles: `vinyrd_runtime` and `vinyrd_owner`. Use TLS `sslmode=require`. For SQLAlchemy, replace URI scheme `postgresql://` with `postgresql+psycopg://`; do not change its user/host/password/database. Never paste URI or secrets into GitHub issues, commits, support chat, screenshots or logs.

Enter these environment variable values directly into Render:

| Variable | Value |
| --- | --- |
| `PARISHCONNECT_DATABASE_URL` | Direct Neon URI for `vinyrd_runtime`, SQLAlchemy `postgresql+psycopg://` scheme |
| `PARISHCONNECT_MIGRATION_DATABASE_URL` | Direct URI for `vinyrd_owner`, same scheme |
| `PARISHCONNECT_BACKUP_DATABASE_URL` | Same direct URI for `vinyrd_owner`, **synthetic-only temporary** |
| `PARISHCONNECT_RESTORE_DATABASE_URL` | Same direct URI for `vinyrd_owner`, **synthetic-only temporary** |
| `PARISHCONNECT_AUTH_TOKEN_SECRET` | Fresh unique random secret, >=32 characters |
| `PARISHCONNECT_QR_TOKEN_SECRET` | Different fresh random secret, >=32 characters |
| `PARISHCONNECT_PASSWORD_SALT` | Third fresh random secret, >=32 characters |
| `PARISHCONNECT_BOOTSTRAP_ADMIN_PASSWORD` | Fresh strong password, >=20 characters |
| `VINYRD_PILOT_PASTOR_PASSWORD` | Another fresh strong password, >=20 characters |

On your own PC run `python -c "import secrets; print(secrets.token_urlsafe(48))"` once for each of the five distinct secrets/passwords. Copy each result into the matching secret field and keep synthetic admin sign-in credentials in your private password manager. Avoid using an existing church password.

Preconfigured **nonsecret** values on Render: `VINYRD_SYNTHETIC_PILOT=1`, `PARISHCONNECT_ENVIRONMENT=staging`, `PARISHCONNECT_SMS_MODE=simulate`, `PARISHCONNECT_DEMO_PASSWORD=disabled`, `PARISHCONNECT_BOOTSTRAP_ADMIN_EMAIL=pilot-admin@vinyrd.test`, `PARISHCONNECT_PUBLIC_BASE_URL=https://vinyrd-pilot-synthetic.onrender.com`, `PARISHCONNECT_ACCESS_TOKEN_MINUTES=120`. Verify these are still correct.

**Read before enabling:** one-time container command `python -m app.scripts.hosted_synthetic_pilot`:
1. Refuses to execute unless all synthetic-only guards pass.
2. Applies full Alembic migrations to **only the dedicated Neon `vinyrd_pilot` database**; creates synthetic admin and church.
3. Provisions runtime SQL grants, runs strict database readiness and synthetic HTTP workflows.
4. Attempts a full `pg_dump` + `createdb` + `pg_restore` into a separate randomly named database, verifies counts/grants, then removes that scratch database.
5. Starts the public HTTP worker with owner/backup/restore/test credentials removed from the worker's process environment.

**Crucial:** this one-time flow retains operator secrets in Render's service configuration until they are explicitly deleted, even though they are removed from the HTTP process. After observing the success marker `VINYRD_SYNTHETIC_PILOT_ACCEPTANCE_PASS`, update Render **Start Command** to `python -m app.scripts.start_backend`, **remove** `PARISHCONNECT_MIGRATION_DATABASE_URL`, `PARISHCONNECT_BACKUP_DATABASE_URL`, `PARISHCONNECT_RESTORE_DATABASE_URL`, `PARISHCONNECT_BOOTSTRAP_ADMIN_PASSWORD`, and `VINYRD_PILOT_PASTOR_PASSWORD` from the service environment, and redeploy. Do not leave operator credentials stored on the long-lived web service.

## Failures and recovery

- If validation fails before the success marker: **no pilot approval**. Inspect Render logs, redact credentials, and remediate. The main schema may have been migrated and synthetic bootstrap committed; do not delete it automatically.
- Neon may deny direct `createdb` / scratch database restore on the Free plan. If so, treat backup/restore verification as **incomplete**; do not bypass the restore gate or declare real-data readiness. An isolated Neon branch restore or a disposable PostgreSQL test using approved alternate credentials may replace this step only with equivalent evidence.
- The free Render service can sleep and restart slowly. Demonstrate only with fictional records; no real SMS, member addresses, church giving amounts or personal contact details.
- If the migrations succeed but HTTP fails, keep the gate failed; do not silently fall back to demo credentials or superuser connections.
- For the existing Railway data, migration has **not** occurred. Never assume Neon contains old Railway member records.

## Pilot acceptance evidence

All items required to claim **hosted synthetic acceptance**:

- [ ] Render deployment success and public HTTPS staff console serves.
- [ ] Confirm Neon Alembic head `20260930_0021` and expected application tables.
- [ ] Strict runtime readiness `no issues found`; runtime role lacks superuser, BYPASSRLS, CREATE and schema ownership.
- [ ] End-to-end synthetic administrator login, pastor role, member registration, attendance/geofence, stewardship and reports.
- [ ] Cross-branch organization access denied as designed; browser role navigation passes.
- [ ] Actual remote backup + isolated restore evidence, not CI-only.
- [ ] Runtime process no longer has migration/backup/restore credentials; operator secrets removed from Render settings.
- [ ] Document free-tier sleep behavior, support contact and rollback path.
- [ ] Final review by the intended church staff using only synthetic examples.

**Real-data acceptance:** separate GO/NO-GO based on durable backup retention, independent restore, privacy controls and production capacity. A successful synthetic rehearsal never authorizes import of real member or financial data.
