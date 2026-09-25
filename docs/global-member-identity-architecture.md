# Global VINYRD identity

## Audit and baseline

Repository: B13219/ParishConnect, product VINYRD. Baseline: origin/main,
`8d72e24b9c0d0f881cd1ea1248177af294d69942`. Feature branch:
`feature/global-member-identity`. Default branch was verified as main and the
fresh checkout was clean before creating this branch.
FastAPI, SQLAlchemy 2, Alembic and PostgreSQL; SQLite is used in unit tests.
There is no Supabase integration and no existing PostgreSQL row-level policy.

`users` stores credentials and optional `branch_id` and unique `member_id`.
Login itself does not require a member, but the member portal and its browser
login require that single linked member. `roles` / `user_roles` are global role
names; previously most staff queries operated across the entire database and
creation selected the oldest branch. `branches` is the existing church entity.

`members` contains church-local people, including people without an account.
Attendance and contributions carry branch and member references. Household,
community-group and ministry participation reference members. Messages have a
branch and member/visitor recipients. Prayers and sermon lessons reference a
branch and member. Staff provisioning creates a user for one member. CSV import
and visitor conversion also create offline members. Existing Alembic history
ends at 20260921_0014. Railway runs migrations and administrator bootstrap before
Uvicorn; the static staff and member applications have no package build step.

## Implementation strategy

Retain users as the permanent identity and sole credential store. Retain branches
as churches and every legacy member ID. Add profiles, church memberships,
membership requests and independent follows. Membership links bridge to legacy
members so historical giving, attendance, private groups and messages continue
to resolve through the church-local member, never through an unrestricted user ID.
Registration must not create or automatically claim a member based on email.
Church review explicitly links an existing record or creates a new local record
after duplicate checks. A person's primary membership does not change staff
authorization or delete any other membership.

Staff authorization must be limited to the staff user's existing branch; a
membership role is descriptive and cannot grant staff permissions. New PostgreSQL
policies supplement explicit API checks. Existing tables are preserved; legacy
staff queries receive a centrally applied church scope. No production migration,
deployment, push or merge is part of this task.

## Schema and relationships

| Table | Purpose and boundaries |
| --- | --- |
| users (retained) | Permanent account and existing password hash/token implementation. Nullable legacy branch/member pointers stay intact. New `identity_self_managed` flag protects global accounts from church password resets/deactivation. Case-insensitive email uniqueness prevents duplicate credentials. |
| profiles (new) | One row keyed by users.id; first/last name, phone, avatar URL, country, region, city and timestamps. Email comes from users, not a second credential/contact source. |
| branches (retained) | Church identity. No rename or parallel churches table. Discovery exposes only ID, name and location. |
| church_memberships (new) | Church, nullable user, nullable unique legacy member, optional membership number, status, descriptive role, primary flag, joined/approved dates and approver. At least a user or legacy member is required. |
| membership_requests (new) | User/church, message, status, review metadata, reason and optional matched member. One pending/more-info request per user/church. Resolved requests are retained. |
| church_follows (new) | Unique user/church pair and timestamps. No member ID, primary flag, staff role, or permission side effects. No follow-count limit. |

Membership statuses: pending, active, inactive, former, suspended. Request statuses:
pending, approved, rejected, more_info_required, cancelled. Membership indexes
cover user lookups and church/status queues. Partial unique indexes protect one
primary per user and one open request per user/church. Unique church/user allows
many active memberships in *different* churches. Unique church/membership-number
allows multiple null numbers. Composite foreign keys require legacy and matched
members to belong to the relationship's church. Foreign keys do not cascade-delete
historical data.

## Migration and legacy-member strategy

Migration: `20260925_0015_global_member_identity.py`, following `20260921_0014`.
All original tables, rows, columns, IDs and authentication hashes remain intact.
The upgrade adds tables, a users flag, indexes and constraints. It backfills one
profile per user and one membership per legacy member, including offline people.
Only an existing `users.member_id` with a consistent branch is linked to a user;
matching an email is never sufficient to claim private history. A linked active
legacy membership becomes primary. Other memberships remain unclaimed.

Known legacy states transferred/deceased/discontinued map to former in the new
relationship; other unrecognized states map to inactive. Original member status
values remain unchanged. ORM mapper hooks create profiles/memberships for future
staff provisioning, imports, visitor conversions and seed operations in the same
transaction. Member status edits synchronize the new relationship and clear a
primary flag when it becomes non-active. These hooks require the application
runtime; external SQL writers must reconcile their inserted rows before using
the new identity APIs. The migration is the initial reconciliation, not an
ongoing database trigger for arbitrary external writers.

Registration creates a user/profile only. A church administrator approves a
request and explicitly selects an offline member when one exists. New member
creation is blocked when matching email, phone or name suggests a duplicate.
The administrator can review the existing records or create a distinct offline
record and explicitly match it. An already-claimed member cannot be claimed by
another account. Reactivating an existing membership reuses its member ID.
Approval, review metadata and member linking commit together; account-row locks
serialize approvals, request creation/cancellation and primary changes. Database
uniqueness remains the final concurrency protection.

Existing staff-provisioned accounts retain their legacy reset/status workflow
until the person edits their global profile or completes a self-service membership
approval. Registration starts self-managed immediately. Once self-managed, church
staff cannot reset the global password, disable the account or edit it through
the legacy admin-user endpoint. They manage church membership status instead.
Account merges and automatic email/phone claiming are deliberately not provided.

Before production rollout, inspect case-insensitive duplicate `users.email`
values and inconsistent users.branch_id/member.branch_id links. The unique email
index fails the migration transaction safely if duplicate credentials exist;
resolve them explicitly rather than silently merging accounts. Rehearse the
upgrade on a restored production backup and allow for index-creation locks.
The downgrade refuses to drop identity data: roll application code back while
retaining these additive tables; review any data rollback separately.

## Authorization and PostgreSQL RLS

There is no Supabase, auth.uid(), or browser database client. The backend is the
trusted database client. Token subjects are loaded from users; current database
roles determine authorization, not role claims supplied by the browser. Reset
tokens are now rejected by the access-token dependency.

New tables enable PostgreSQL RLS and revoke PUBLIC table privileges. The API sets
`vinyrd.user_id` with transaction-local `set_config`, restoring it after a commit
opens another transaction. Connection-pool reuse does not retain actor context.

* Profiles and follows: owner-only reads/updates. Staff can insert a profile when
  provisioning an account in their branch, without being allowed to read it.
* Memberships: owner reads their memberships; authorized legacy staff read only
  their branch's relationships. Staff creation/status synchronization is limited
  to that branch. Owners can change only their primary flag, not identity, role,
  church, status or approval metadata. A database trigger enforces that column
  boundary in addition to the API's narrower operations.
* Requests: owners read/create their own pending requests and cancel an open
  request. Only church administrators review requests in their own branch. RLS
  and the update trigger reject self-approval and reassignment.
* No membership/request delete API or delete policy is provided.

Existing legacy tables still use server authorization rather than new blanket
RLS policies. `require_roles` installs a request-session church scope on staff
ORM queries, including aggregates, CSV exports, branch settings, user management
and child relationships. Flush validation checks church ownership and referenced
members/events/households/staff. New identity services use explicit owner/church
predicates and administrator checks. The public legacy attendance paths retain
their URLs and event/geofence/QR validation, with an added same-church person/event
check. They do not gain any authority from follows.

PostgreSQL table owners and BYPASSRLS/superusers bypass RLS; this is not hidden by
the application checks. For defense in depth, run the HTTP application using a
non-owner, NOSUPERUSER, NOBYPASSRLS role with required table privileges, and run
migrations/bootstrap as the schema owner. Railway's existing command/configuration
is unchanged and currently uses one database URL; separating runtime/migration
credentials is an operational rollout prerequisite for relying on RLS itself.
Do not distribute the backend database role to clients: custom session settings
are trusted-server context, not proof of identity from an arbitrary SQL client.
Integration tests explicitly use a non-owner role and test deny rules directly.

The design follows PostgreSQL's [row security documentation](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
and SQLAlchemy's [session query filtering documentation](https://docs.sqlalchemy.org/en/20/orm/session_events.html#adding-global-where-on-criteria).

## Member context, follows and home church

The portal resolves an active membership to its legacy member. Without an explicit
selection it uses the primary membership; `X-Church-ID` selects another active
membership for that request. A revoked/inactive/suspended relationship cannot
fall back to the legacy user pointer. Historical giving/attendance/private groups
continue to reference the church-local member, preserving all IDs and history.
Giving reads check both member and church. No global-user-wide join reveals another
church's giving, groups, attendance, prayers or messages.

The owner chooses a home church using the primary endpoint. Only active
memberships can be primary; the old primary is cleared before the new one is set
in a single transaction. Other memberships remain active. Approval does not
implicitly change home church or inspect the person's other churches. Existing
home associations are preserved by backfill. Suspending a home membership clears
its primary flag, leaving the person free to select another active membership.
Neither this selection nor following modifies users.branch_id (staff scope).

The existing member login now accepts an account without a membership. Home/profile
show an account-only state; membership-only pages send that person home without
clearing a valid login. No self-registration, church-picker or review-form UI is
introduced here. Existing staff/public/member URLs and Railway files are preserved.

## API contract for the next member-app flow

All paths are under `/api/v1`; authenticated operations use the existing bearer token.

| Method/path | Operation |
| --- | --- |
| POST /auth/register | First/last name, email, password (12+ characters), optional phone; returns existing login response shape. No role, church or member IDs accepted. |
| GET, PUT /identity/me | Read/replace personal profile. Email/password changes use the existing auth/account flows, not this profile payload. |
| GET /identity/churches | Limited church discovery. |
| GET /identity/memberships | Own relationships. |
| PUT /identity/memberships/{id}/primary | Owner's active home church. |
| POST /identity/churches/{id}/requests | Submit membership request with optional message. |
| GET /identity/requests | Own request history. |
| POST /identity/requests/{id}/cancel | Cancel pending/more-info request. |
| GET /identity/churches/{id}/requests | Church administrator's review queue. |
| POST /identity/requests/{id}/review | Approve/reject/request more info; optional matched_member_id and reason. |
| GET /identity/churches/{id}/memberships | Administrator's church-local memberships. |
| PATCH /identity/memberships/{id} | Church administrator changes local membership status. |
| GET /identity/follows | Own follows. |
| PUT, DELETE /identity/churches/{id}/follow | Idempotent follow/unfollow. |

Before a public registration UI rollout: rehearse migration/backfill and role setup;
implement registration, church discovery, request status/review, verified manual
claiming and home selection screens; wire X-Church-ID for context switching. The
current password-reset implementation prepares a token but does not deliver email
in production. Implement verified email/recovery delivery and registration abuse
controls before public launch. No unverified email should authorize claiming.
For more-info requests, this first API supports review plus cancellation/reapply;
a dedicated reply/resubmission UI/API remains future work. Staff roles remain
bound to the existing staff branch; multi-church staff delegation is separate
from multi-church membership.

## Validation

* 132 tests passed, including all 118 existing tests and 14 new tests.
* PostgreSQL 16: full migration chain applied; upgrade from populated prior head
  preserved every seeded legacy column value across all legacy tables.
* Non-owner RLS: own-only reads, no-context denial, cancellation versus self-approval,
  membership-column protection and pooled-context reset passed. API registration,
  two-church approval and concurrent primary switching passed with RLS active.
* All frontend JavaScript files passed node --check; Python compileall passed.
* New/changed identity code passes Ruff. Full Ruff reports two existing findings:
  app/api/routes/messages.py:428 (BLE001), app/services/sms.py:1 (I001).
* Python wheel build succeeded. Production Docker build could not run because
  this machine's Docker engine is unavailable; rerun the CI Docker build before
  deployment. There is no configured standalone typecheck or frontend build task.
* No production database was contacted or migrated. No deployment, push or merge.

Run the PostgreSQL tests against an explicitly local disposable cluster:
`VINYRD_TEST_POSTGRES_URL=postgresql+psycopg://...@127.0.0.1:PORT/postgres pytest -q`.
Those tests create a uniquely named temporary database/runtime role and remove
only those resources. Without that variable the two PostgreSQL tests are skipped.
The existing backend CI workflow supplies this variable from its disposable
PostgreSQL service, so those tests run in CI too.
