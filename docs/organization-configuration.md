> Phase 3 extension: [Organization-scoped administration](organization-access.md) adds explicit access grants after revision 0019. The setup-phase description below remains the historical organization configuration contract; office assignments themselves still grant no access.

# Persistent church organization configuration

This phase extends localization baseline `bb44938` on
`feature/vinyrd-member-mobile`. Branch remains the operational tenant. The
organization tree describes affiliation; it does not replace global accounts,
memberships, staff roles or their authorization checks.

## Schema and migration

Additive Alembic revision **20260927_0019**, following **20260927_0018**, adds:

| Table/change | Purpose |
| --- | --- |
| `organization_units` | UUID; canonical denomination/level; official and normalized name; nullable parent FK; country/region/city; localized official names; installed level labels; status; managed/published flags; branch custody; deterministic match digest; timestamps |
| `branches.organization_unit_id` | Nullable, unique FK to the unit representing this operational Branch |
| `church_organization_configurations` | Branch PK; denomination/version; selected unit FK; setup status; configured time/user; terminology/hierarchy snapshots; confirmation fingerprint; timestamps |
| `organization_office_assignments` | UUID; unit, user, canonical office key, independent intended permission profile, status, operational Branch and timestamps |

Parent, match, custody and user/status indexes support traversal and lookup.
Owner/match and unit/user/position unique indexes prevent duplicates. A check
rejects self-parenting. Denomination-specific ordering and optional levels are
validated in the service rather than encoded as one universal database hierarchy.

No hierarchy backfill or mandatory setup occurs. No member, giving, attendance,
group, password or role rows are rewritten. Legacy `User.position_title` and
`User.organization_level` remain. Downgrade deliberately refuses to drop installed
organization data; application rollback retains the additive schema.

## APIs

All paths below have the existing `/api/v1` prefix. Organization administration
requires an active Administrator for the actor's own Branch. Payloads cannot
select another tenant.

| Method/path | Behavior |
| --- | --- |
| `GET /network/admin/organization/setup` | Installed configuration/ancestry or an unsaved draft state |
| `POST /network/admin/organization/preview` | Read-only denomination/version, localized levels, expected parents, offices and terminology |
| `POST /network/admin/organization/confirm` | Atomically install validated ancestry and template snapshots |
| `GET /network/admin/organization/assignments` | Own-branch assignments, active users and existing permission-profile keys |
| `PUT /network/admin/organization/assignments` | Upsert by unit/user/office; independently select profile and active/inactive status |
| `GET /network/denominations` | Existing catalogue now includes built-in `template_version: 1` |
| `GET /network/churches` and `GET /network/churches/{id}` | Additive public `organization_path` array |

Example preview: `{"denomination":"TAG","organization_level":"local_church"}`.
Neither preview nor console review writes organization data. Confirmation requires
the previewed version. Stale versions return 409; invalid keys, missing required
parents, repeated levels or out-of-order paths return 422.

## TAG installation

```json
{
  "denomination": "TAG",
  "template_version": 1,
  "organization_level": "local_church",
  "units": [
    {"level_key":"national_church","canonical_name":"Tanzania Assemblies of God","country":"TZ"},
    {"level_key":"zone","canonical_name":"Eastern","country":"TZ"},
    {"level_key":"district","canonical_name":"Dar es Salaam","country":"TZ"},
    {"level_key":"section","canonical_name":"Kinondoni","country":"TZ"},
    {"level_key":"local_church","canonical_name":"TAG Mikocheni","country":"TZ"}
  ]
}
```

This persists `Assemblies of God` and a five-unit parent chain. Branch and its
configuration point to TAG Mikocheni. Newly created ancestors are unmanaged; the
selected Branch unit is managed. Neither flag grants denomination-wide authority.

The console displays `Kanda / Zone`, `Jimbo / District` and `Sehemu / Section`;
stored identifiers remain `zone`, `district` and `section`. An official name such
as `Jimbo la Dar es Salaam` remains unchanged. Optional API metadata such as
`localized_names: {"sw":"Jimbo la Dar es Salaam","en":null}` is accepted.
Missing localized names fall back to the canonical name. The current wizard
collects canonical names; it does not machine-translate names.

## Catholic and custom denominations

```json
{
  "denomination": "Roman Catholic",
  "template_version": 1,
  "organization_level": "parish",
  "units": [
    {"level_key":"diocese","canonical_name":"Arusha Diocese"},
    {"level_key":"parish","canonical_name":"St. Joseph"}
  ]
}
```

This installs `Catholic`, Diocese → Parish. Optional province and deanery are
omitted; an outstation is not required for parish setup. The same generic catalogue
validation handles other denominations. A custom denomination installs only its
name and `custom_required` status with empty hierarchy, null version/unit and no
guessed structure. Custom hierarchy editing remains a future workflow.

## Confirmation, reuse and snapshots

The service validates the full path before inserts. PostgreSQL uses a transaction
advisory lock for this low-volume workflow plus a Branch row lock. This serializes
ancestor reuse and simultaneous confirmations. Unit, link, configuration and audit
writes commit together; failure rolls all of them back.

Reuse requires the same denomination, canonical level, Unicode-normalized/case-
folded/whitespace-normalized name, exact parent, geography, localized-name metadata
and publication choice. Similar names do not match. Same-named sections under
different districts remain distinct. Another tenant's unpublished records are
never inspected/reused. Published ancestors can be reused, including one represented
by its own operational Branch, without granting access to that Branch. A branch
never claims another branch's unit as its own selected local unit.

The exact normalized confirmation payload is fingerprinted. Repeating it returns
the existing configuration without duplicate units/audit events, even after live
catalogue changes. A different payload after completed setup returns 409. Installed
snapshots retain level/office terminology and the selected path. Template edits or
ordinary Branch settings cannot silently replace the installed configuration.

## Console workflow

Open **Members → Registration Requests → Church organization setup**. Select a
denomination and the level being configured. Fill mandatory ancestors; optionally
include eligible optional levels. Geography is optional and structured, with no
Dar es Salaam requirement. Per-unit publication checkboxes default to private.
Review displays denomination/version, names, geography, publication choices,
selected church level, bilingual terminology and offices. Only **Confirm Church
Setup** persists records. Input edits invalidate review. Configured churches show
their installed snapshot and an office assignment editor.

Office assignment selects user, office, intended permission profile and status
separately. Local administrators can assign only their selected unit and active
users in their Branch, never ancestor offices or another tenant's users.
Deactivation uses the same upsert with `status: "inactive"`.

## Members, public data and security

A person joins one **Branch**, yielding one ChurchMembership for that Branch.
Ancestry is derived through `Branch.organization_unit_id` and parent links; no
national, zone, district or section memberships are created. Home Church, multiple
memberships, viewed-church context, follows, legacy-member linking and historical
church data retain their existing behavior.

**Position is not permission.** An assignment with profile `administrator` does
not create UserRole rows, change legacy user fields or grant access. Existing
authentication and Branch authorization remain authoritative. Utilities
`is_unit_descendant_of`, `organization_scope_ids` (inclusive of the starting unit)
and `user_organization_assignments` prepare future scope resolution but are not
wired into access grants. They observe DB visibility and do not bypass RLS.

RLS is enabled on all three new tables. Unpublished units are visible only to their
owning Branch administrator; active published units are readable. Configuration
reads/writes require the owning administrator. Assignment reads allow the assigned
user or owning administrator; writes also require a same-Branch active user and
that Branch's selected unit. Units have no runtime UPDATE/DELETE policy; deleting
configuration/assignments is also unavailable. Server endpoints independently
enforce tenant boundaries and canonical keys, including with an owner connection.

Public traversal is batched by depth. Every hop must be active and explicitly
published, otherwise the entire path is `[]`. Only `level_key`, official `name`
and installed `labels` are serialized; no UUIDs, staff, permissions, custody,
contacts, snapshots or internal flags. A public profile whose declared denomination
contradicts installed ancestry receives an empty path. Existing publication rules
and response fields remain compatible. Mobile/EAS changes are not needed to ignore
or later consume this additive field.

Existing audit logging records `organization.unit_created`,
`organization.branch_linked`, `organization.setup_confirmed`,
`organization.office_created`, and `organization.office_changed`. Metadata is
limited to structural IDs/keys, version and status.

## Validation and staging

Validated locally: **171 backend tests passed**, including 19 organization service/
API cases, two organization PostgreSQL cases, the existing migration preservation,
non-owner RLS and concurrency cases, and the extended Chromium journey. This covers
rollback after a mid-transaction failure, simultaneous confirmation, safe public
ancestor reuse, optional Catholic levels, no ancestor memberships, no privilege
elevation from assignments, cross-tenant denials and public projection privacy.
Changed Python files pass Ruff; console JavaScript syntax validation also passes.
The baseline Starlette/httpx and HTTP 422 deprecation warnings remain.

Staging procedure:

1. Back up and rehearse restore of PostgreSQL. Apply `alembic upgrade head` using
   the schema-owner migration credentials; confirm sole head `20260927_0019`.
2. Use the established non-owner NOSUPERUSER NOBYPASSRLS API role. Grant it
   SELECT/INSERT/UPDATE/DELETE on the three new tables using the existing runtime
   grant procedure; RLS still restricts those grants. Owners/superusers bypass RLS.
   Separate migration/runtime credentials remain an existing deployment prerequisite.
3. Release backend and console assets together. Preserve Railway, auth secrets,
   API URLs, mobile application and `eas.json`. No environment variables or new
   external services are required.
4. Confirm legacy operations without setup, TAG/Catholic setup, independent office
   profile selection, public/private ancestry, and isolation using two church admins.
   Check that members still have only their intended Branch memberships/history.
5. Run production Python/container CI and backup/restore rehearsal before any
   separately authorized production rollout. Local validation used Python 3.14,
   PostgreSQL 16.15 and Chromium; no production deployment occurred.

Review limits: structural reconfiguration, unit renaming/publication changes,
custom hierarchy editing, verified denomination governance, custody transfer and
hierarchical RBAC are future workflows. Units are immutable through current APIs;
private defaults and explicit review matter. A self-described affiliation does
not prove denomination authority. The existing profile editor can unpublish a
church profile, but does not alter shared ancestor records. Full-repository lint
debt is reported separately; mobile source was unchanged so mobile checks were
not repeated. Feature-branch checkpoints are for validation and review only; they
do not authorize merging or deployment. See `deployment-readiness.md` for the
Linux container workflow, explicit UTC sessions, and selected-table backup
manifest scope.
