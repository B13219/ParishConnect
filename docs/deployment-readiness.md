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

PostgreSQL application connections explicitly request `timezone=UTC`. Legacy
timestamp-without-time-zone attendance fields are interpreted as UTC; changing
church display timezone does not change this database-session requirement. Keep
migration/backup sessions in UTC too (`PGTZ=UTC` or a database UTC default).
Linux container CI sets the disposable database default to UTC and asserts UTC
on the running application's connections. A local smoke run also verifies that
the connection setting works when the server default is `Africa/Nairobi`.

The production image installs `postgresql-client-16` from the signed
[official PostgreSQL Apt repository](https://www.postgresql.org/download/linux/debian/),
matching the supported PostgreSQL 16 server. The unversioned Debian client package
previously selected client 17, whose restore prologue failed on PostgreSQL 16 with
`unrecognized configuration parameter "transaction_timeout"`. Keep dump/restore
client major versions aligned with the server during future upgrades; CI asserts
both client versions and performs an actual restore.

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

The production container runs the privilege-separated entrypoint:

```text
python -m app.scripts.start_backend
```

Follow [staging initialization](staging-initialization.md) for owner-only migration,
runtime reprovisioning and independently verified initial authority. Normal starts
use only runtime credentials; migration is not performed by the runtime role.
The current single migration head is `20260930_0021`.

Run the strict gate (including staging):

```text
python -m app.scripts.check_deployment_readiness --strict --check-database
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

The manifest intentionally reports selected legacy operational tables, not every
database table. Its `BACKUP_MODELS` allowlist is not the backup definition. It omits
organization tables (and existing identity/group tables) and does not serialize
`branches.organization_unit_id`. Do not use it as a recovery archive. Full
PostgreSQL dump/restore below discovers all application tables dynamically and
includes `organization_units`, `church_organization_configurations`,
`organization_office_assignments` and the Branch organization link. Restore uses
`--no-owner --no-privileges`; reapply production roles/grants separately.

Run:

```text
python -m app.scripts.verify_backup_restore
```

The command creates a real PostgreSQL dump, restores it to a temporary database,
compares every application table row count, and deletes the temporary database.

Do not import real church data until this restore test passes on the intended hosting
database.

## Feature-branch Linux validation

The existing backend workflow also runs on pushes to
`feature/vinyrd-member-mobile`. `scripts/validate-linux-container.sh` builds the
production Dockerfile at `github.sha`, starts its production CMD against
an empty PostgreSQL 16 database, and verifies migration, bootstrap, health and
readiness. It then serves the same image with the documented separate non-owner
runtime role and exercises both the existing pilot and organization HTTP smoke
journeys, backup/restore, and runtime restart. Owner credentials are used only for
migration/bootstrap, disposable fixture setup and backup, not the HTTP server's
security checks. There is no separate readiness endpoint; CI uses the existing
strict readiness command plus `/health`.

CI enforces changed-file lint and fails new full application/test findings, while
reporting only the two known unchanged SMS findings as baseline debt. It does not
alter Ruff rules globally or repair unrelated legacy findings. Generated local
validation reports, environment files, and dumps are not part of the checkpoint.
Workflow evidence is uploaded with the tested SHA; a checkpoint does not authorize
merge, production deployment, or hierarchical RBAC work.

## Organization access migration

See [Organization-scoped administration](organization-access.md) before applying `20260928_0020`. Provision runtime table privileges separately from migration ownership, retain UTC settings, and verify the 31-table full backup/restore. Higher-level authority requires separately verified bootstrap; branch custody alone cannot create it. The feature-branch Linux container workflow includes hierarchy smoke. No additional production environment variables are required.


Phase 3.5 staging operations: see [staging initialization and privilege separation](staging-initialization.md). Runtime-only production startup, guarded initial authority and exhaustive restore startup validation are required; migration head remains `20260928_0020`.
