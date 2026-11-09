# Vinyrd management — zero-cost staging and Friday pilot contingency

Updated: 9 November 2026. Target: Friday 13 November 2026. Tracking: [#15](https://github.com/B13219/ParishConnect/issues/15), [draft #16](https://github.com/B13219/ParishConnect/pull/16).

## What is already validated

- Source: `release/vinyrd-management-pilot-2026-11-13`, original validated head `de040ee450a9059035fb16ed8e39cbbb96b02f44`.
- GitHub CI evidence: [run 42600556942](https://github.com/B13219/ParishConnect/actions/runs/42600556942): 289 tests, PostgreSQL 18 clean migration, Docker, browser/organization smoke, runtime isolation and backup/restore verification in **disposable CI data**.
- The paid Railway workspace is inaccessible to the owner due to expired billing; the connected API still reports old deployments online but must not be assumed usable.
- The proposed Railway staging source + HTTPS base URL + disabled demo-password configuration remain staged only. Do not commit/apply until the staging database/roles are verified.

## Two isolated environments, never silently interchangeable

1. **Temporary demonstration**: Render workspace `Vinard` (`tea-dbabj3u1egvs73a3kmgg`), database `vinyrd-pilot-staging-temp` (ID `dpg-dbp3510n74is73cmg480-a`), Frankfurt, PostgreSQL 18, Free. Created 9 November, **expires 9 December 2026**. This database has no Render-managed backups. **Synthetic identities and financial activity only**. Do not enter, import or copy real church data. Free app service may sleep and should never be represented as guaranteed availability.
2. **Candidate church pilot**: only after a durable external PostgreSQL database with appropriate privileges, tested backups, restored records, audit and branch isolation, and secure named staff accounts is available. Neon Free is a candidate, **not yet connected**; validate capacity, restore coverage and RPO/RTO against the church's needs before accepting personal records.

## Temporary Render demonstration deployment prerequisites

1. Confirm Render PostgreSQL service becomes available. The database should be populated only with **fictional** test records.
2. Provision separate database roles for migration/owner, runtime (no superuser/createdb/createrole/bypassrls/replication privileges, no owned tables), backup with BYPASSRLS when required for full-scoped backup, and restore to an **isolated test database**. Do not expose the operator's connection strings to the long-lived HTTP process.
3. From an authorized, secure local/operator workstation against the disposable database, run Alembic migrations to head `20260930_0021` using a migration owner, provision least-privilege runtime with `python -m app.scripts.provision_database_access`, then bootstrap **synthetic** pilot staff. The startup script `python -m app.scripts.start_backend` will *refuse to serve* in production/staging mode if the database is not at head or runtime role/grants are wrong.
4. For a Render Free web service, use repository root Dockerfile and **auto-deploy disabled** with a pinned tested revision; configure its `PARISHCONNECT_` runtime variables and strong distinct secrets via the provider secret manager, including `PARISHCONNECT_DATABASE_URL` with the PostgreSQL psycopg driver, `PARISHCONNECT_ENVIRONMENT=staging`, exact `PARISHCONNECT_PUBLIC_BASE_URL=https://<actual-service>.onrender.com`, empty/nonwildcard CORS, no default demo credentials, and access token lifetime <=240 minutes. Never commit credentials. Do not deploy an unconfigured app that defaults to localhost database and demo credentials.
5. After deploy, verify HTTPS `/health`, staff login, permissions, member/visitor lifecycle, branch scoping, check-in concurrency and correction, stewardship reconciliation, reporting, logs and readiness.
6. Include a prominent **SYNTHETIC DEMO — NOT FOR REAL CHURCH DATA** indicator on operator instructions and pilot presentation.

## Database verification (read-only, authorized SQL console)

```sql
SELECT current_setting('server_version') AS postgres_version,
       current_setting('TimeZone') AS session_timezone,
       current_user AS connected_role;
SELECT version_num FROM public.alembic_version;
SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolbypassrls
FROM pg_roles WHERE rolname LIKE 'vinyrd_%' ORDER BY rolname;
```

On a fresh database, `alembic_version` does not exist until migration. Do not take missing table as evidence of corruption. Never paste credentials or member data into support chats.

## Friday release rule

- **Real-data GO**: durable DB, verified backup and full isolated restore, migration head, least-privilege runtime, all required app tests and actual HTTPS/role workflows, church consent and data controls, named staff training/support, rollback and owner approval.
- **Otherwise**: deliver an explicitly labeled *synthetic-data preview and onboarding rehearsal* with the unresolved production blockers. No real member/financial records on an ephemeral, expiring or unproven database.
