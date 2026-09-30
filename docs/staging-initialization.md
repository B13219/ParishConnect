# Staging initialization and recovery

Current single head: `20260930_0021`, following `20260928_0020`,
`20260927_0019` and `20260927_0018`. Follow the
[template governance migration notes](denomination-template-governance.md).
Migration 0021 adds no tables: it adds the constrained unit-label update policy,
helper/trigger and indexes. Reapply runtime privilege provisioning because the
current matrix adds `UPDATE` on `organization_units`; RLS and the immutable-field
trigger constrain that permission. Do not modify historical migrations.

## Phase 6 release gate

Before changes, record the exact staging project/environment/service IDs, current
deployment SHA and schema head. Confirm owner/runtime/backup/restore access,
independently verified administrator identity/Branch/scope/authority reference,
HTTPS origin, strong existing authentication secrets, disabled demo credentials,
temporary bootstrap controls, fake-data boundaries, PostgreSQL 16 utilities,
backup storage and EAS preview access/API origin. Do not rotate identity secrets
as a side effect of validation.

Use one feature-branch SHA for Linux CI, staging acceptance and EAS preview. Keep
the release candidate provisional until all three are verified. The Railway
environment name alone does not identify staging: verify its project ID too.
Do not point disposable fixture scripts at an existing deployment; their loopback
guards are intentional. Create approved test organizations through authenticated
setup APIs and preserve all pre-existing staging data.

Capture before/after grants, configuration snapshots and governance history under
operator access around the existing owner migration/provisioning procedure below.
Run the complete backend/PostgreSQL/Chromium suite and native typecheck, lint and
tests. Browser and JS checks now run on every backend validation workflow.

For a configured acceptance account with governance history, run the full restore
gate using separately injected operator credentials:

```text
python -m app.scripts.verify_backup_restore --acceptance-smoke --backup-path <protected-dump-path>
```

Supply that existing validation account through `PARISHCONNECT_BOOTSTRAP_ADMIN_EMAIL`
and `PARISHCONNECT_BOOTSTRAP_ADMIN_PASSWORD` to this one-off verifier only. The
verifier does not bootstrap an account or enable authority: it authenticates to
the isolated restored runtime and performs read-only organization/governance API
checks. The HTTP child never receives the password as bootstrap configuration.
This mode requires nonempty restored grants and approval history, strict readiness,
current migration head, health and authenticated API checks. Ordinary backup mode
remains usable for unconfigured databases. Protect/delete retained dumps according
to the approved backup retention policy; never commit them.

Record actual EAS build ID, profile, version/code, artifact and matching commit;
do not substitute an earlier preview. No store submission, release tag, main merge
or production deployment is part of Phase 6. Rollback guidance below remains
application rollback with preserved schema/history, not automatic database downgrade.

## Credentials and UTC

All commands run from `backend/`. Inject real credentials through the deployment secret store; examples are placeholders. Never put operational credentials or bootstrap flags in a mobile/web client.

| Setting / credential | Required privileges and use |
| --- | --- |
| `PARISHCONNECT_DATABASE_URL` | HTTP runtime login: CONNECT, public schema USAGE, explicit table DML matrix in `app/services/database_privileges.py`, SELECT on alembic_version. No ownership, inherited roles, SUPERUSER, CREATEDB, CREATEROLE, BYPASSRLS, replication, schema CREATE or TRUNCATE. Internal unrestricted tree traversal cannot be executed. Actor-bound RLS helpers remain callable. |
| `PARISHCONNECT_MIGRATION_DATABASE_URL` | One-off operator login owning the application schema/tables/functions, with database/schema creation privileges needed by Alembic and ability to grant table access. Run migrations, initial local admin creation, privilege provisioning and approved authority initialization. Never grant membership in this role to runtime. |
| `PARISHCONNECT_BACKUP_DATABASE_URL` | Separate login targeting the source database, CONNECT, schema USAGE, SELECT on every table and BYPASSRLS to avoid filtering. No superuser, CREATEDB, CREATEROLE or writes. DBA creates the BYPASSRLS role. Treat its read access as sensitive. |
| `PARISHCONNECT_RESTORE_DATABASE_URL` | Separate operator login on the destination server's maintenance database (usually postgres), CONNECT and CREATEDB, owning only databases it restores; no SUPERUSER, CREATEROLE or BYPASSRLS. Destination runtime role must already exist. Use on an isolated restore server where practical. Never attach to HTTP. |
| `VINYRD_ALLOW_AUTHORITY_BOOTSTRAP` | Defaults false; true for exactly one approved operator CLI invocation, then removed. |
| `VINYRD_ALLOW_AUTHORITY_RECOVERY` | Independent default-false, one-shot recovery guard; requires deployment authorization. |

The provisioning command grants the precise current runtime matrix and read-only backup access. It does not create roles or passwords. Example DBA role creation (substitute secrets securely):

```sql
CREATE ROLE vinyrd_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION PASSWORD '<runtime-secret>';
CREATE ROLE vinyrd_backup LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE BYPASSRLS NOREPLICATION PASSWORD '<backup-secret>';
CREATE ROLE vinyrd_restore LOGIN NOSUPERUSER CREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION PASSWORD '<restore-secret>';
```

Do not use a database-owner URL for HTTP. Production/staging startup fails closed on excess privileges, missing grants, non-UTC sessions or stale migration head. Existing legacy operational tables retain server ORM tenancy; this is not a claim that every table has RLS. Runtime credentials remain trusted server secrets.

Runtime, migration and operator SQLAlchemy engines explicitly set UTC. Backup tools use `PGTZ=UTC` and `PGOPTIONS=-c timezone=UTC -c row_security=off`: incomplete RLS access fails rather than silently filtering. Keep PostgreSQL 16 client utilities available. `row_security=off` does not itself bypass RLS.

If the hosting service cannot supply separate BYPASSRLS backup and CREATEDB restore roles, obtain provider-authorized operational credentials or an isolated restore service. Do not loosen the HTTP role to work around that limitation. Reapply provisioning after every migration that adds tables; no broad future-table default grants are installed.

## Staging sequence

1. Create the staging database and separate roles. Build the existing Dockerfile. Configure production-like authentication secrets/public URL and the runtime URL. Keep operator credentials in one-off jobs.
2. With the migration URL injected, run `python -m alembic upgrade head`, then the existing `python -m app.scripts.bootstrap_admin` for the independently verified initial local church admin, then `python -m app.scripts.provision_database_access --runtime-role vinyrd_runtime --backup-role vinyrd_backup`. Remove the initial password. The Docker entrypoint also supports an optional migration URL for migrate/bootstrap/runtime-provision followed by credential-scrubbed HTTP startup, but external one-off jobs are preferred; container-level secrets remain accessible to container operators even after process scrubbing.
3. Start the existing Docker CMD using runtime credentials only. Check `/health` and `python -m app.scripts.check_deployment_readiness --strict --check-database`. Confirm current head and UTC. The simple health endpoint alone is not database readiness.
4. Sign in as the verified existing local Administrator. Record the intended actor, recipient and approval ticket; verify identity and governance authorization independently of church setup.
5. Preview and confirm the organization tree through existing Organization Setup. Verify the church's linked unit and actual root ancestry. Office titles confer no authorization.
6. In a one-off deployment-owner job only, temporarily enable the bootstrap flag.
7. Run the command below with verified UUIDs. Only Administrator/descendants at the configured active root is supported. Both actor and target must be active local Administrators connected to that tree. Knowing a UUID or sharing a denomination name is insufficient.
8. Inspect the audit row and grant through Organization Administration. Audit records actor, recipient, unit, role, scope, approval reference/type, database operator role and timestamp. It records no credential values. Exact active retries with the same actor/recipient/root/reference return the existing grant.
9. End the operator job and remove the flag/owner credential. The CLI consumes the flag in its process. The HTTP entrypoint strips operational credentials and both flags from the worker environment; there is no HTTP bootstrap endpoint.
10. Verify contained delegation through the existing grant API/console using a different recipient; self-grants, ancestor/sibling delegation and unrelated roots remain denied. Verify member/staff access and office-only accounts remain unchanged.
11. Run the existing backup verifier with explicit runtime, backup and restore URLs: `python -m app.scripts.verify_backup_restore --backup-path <protected-backup-path>`. Run on a quiet staging database so concurrent writes do not invalidate row-count comparisons. Protect/retain the resulting dump under the existing backup policy.
12. The verifier creates a unique clean destination database, restores all 31 application tables, compares counts and full grant rows, verifies head, reapplies runtime privileges/internal helper restrictions and starts the restored service with runtime credentials. It checks HTTP health and drops only its newly created verification database. It does not overwrite the source. For an operational restore, apply the same owner/runtime provisioning before opening traffic; `--no-privileges` requires reapplying ACLs. Run non-owner RLS regression tests against an isolated restored copy.
13. Run legacy/member/staff and organization smoke checks in disposable staging, verify cross-tenant denials, restart, then recheck health/readiness. CI smoke scripts require explicit disposable loopback databases; never point fixture-writing scripts at production.

One-shot POSIX invocation (PowerShell: set the flag only around the command and remove it in `finally`):

```sh
VINYRD_ALLOW_AUTHORITY_BOOTSTRAP=true python -m app.scripts.provision_organization_grant \
  --actor-user-id VERIFIED_LOCAL_ADMIN_UUID \
  --user-id VERIFIED_RECIPIENT_LOCAL_ADMIN_UUID \
  --organization-unit-id VERIFIED_ROOT_UUID \
  --permission-role administrator --scope-mode descendants \
  --authority-reference VERIFIED_APPROVAL_TICKET
```

This is an operator-only server-side operation rather than a public route. Migration ownership plus independent deployment authorization is the second guard; a local admin cannot invoke it through HTTP. The operator must verify the named actor is the approving person: the CLI does not authenticate that person interactively. Bootstrap refuses any authority history in the tree, even inactive descendants, which is deliberately stricter than checking only active grants. The root transaction lock serializes concurrent initialization/recovery. No office or ChurchMembership is created or changed.

## Controlled recovery and rollback

Revocation never reopens normal bootstrap. First try contained delegation from a surviving authorized root administrator. If the only root administrator is lost/revoked, independently verify the incident and replacement existing local Administrator, retain an approval ticket, and use a one-off migration-owner job with `VINYRD_ALLOW_AUTHORITY_RECOVERY=true` and the same command plus `--recover`. Recovery requires prior authority history and no active root Administrator/descendants grant for an active account. If a lost account is still active, an authorized operator must explicitly disable that account or revoke its grant in a separately recorded incident procedure first; do not silently bypass the guard. Recovery creates/reactivates the matching grant and writes a distinct recovery audit. Remove the flag immediately, verify access and delegate normally. Do not delete audit or grant history to force initial bootstrap.

A failed bootstrap transaction rolls back its grant and audit. An accidental successful grant must be revoked through an authorized contained administrator, preserving history; operator incident recovery is available when no such administrator remains. Phase 3.5 needs no downgrade. Roll back application code/config only after checking compatibility; retain least-privilege roles and the current schema. Never restore over a live database without a separate authorized cutover, tested snapshot and downtime plan. Keep the source database untouched during restore verification.

BOOTSTRAP AUTHORITY IS EXPLICIT AND TEMPORARY

RUNTIME APPLICATION PRIVILEGES DO NOT INCLUDE RESTORE AUTHORITY
