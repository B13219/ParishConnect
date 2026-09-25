# Global VINYRD identity

Current state: Prompt 2 is implemented on `feature/global-member-identity`.
Prompt 1 remains intact. Prompt 3 has not begun.

## Original audit and baseline (before Prompt 1)

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
| branches (retained) | Private church identity and configuration. No rename or parallel churches table. Public data comes from the explicit publication below. |
| church_memberships (new) | Church, nullable user, nullable unique legacy member, optional membership number, status, descriptive role, primary flag, joined/approved dates and approver. At least a user or legacy member is required. |
| membership_requests (new) | User/church, message, status, review metadata, reason and optional matched member. One pending/more-info request per user/church. Resolved requests are retained. Prompt 2 adds a consent-scoped applicant snapshot for reviewers. |
| church_follows (new) | Unique user/church pair and timestamps. No member ID, primary flag, staff role, or permission side effects. No follow-count limit. |
| church_public_profiles (Prompt 2) | One explicit publication/draft per branch: name, ISO-style two-letter country code, region/city, optional denomination, location, HTTPS logo/site, about, service times, public contact and bounded public events/announcements/ministries. No automatic copying from private settings. |

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
its primary flag. On the next member synchronization, the owner-only initialize-home
endpoint chooses the oldest active membership if none is primary. It never
replaces an existing Home Church. The owner can select another active membership.
Neither this selection nor following modifies users.branch_id (staff scope).

The existing member login now accepts an account without a membership. Home/profile
show an account-only state; membership-only pages send that person home without
clearing a valid login. Prompt 2 adds the account, church-picker and review-form
screens described below. Existing staff/public/member URLs and Railway files are preserved.

## Identity API contract

All paths are under `/api/v1`; authenticated operations use the existing bearer token.

| Method/path | Operation |
| --- | --- |
| POST /auth/register | First/last name, email, password (12+ characters), optional phone; returns existing login response shape. No role, church or member IDs accepted. |
| GET, PUT /identity/me | Read/replace personal profile. Email is read-only here; self-service email change is not implemented. Password reset uses the existing /auth/password-reset/request and /auth/password-reset/confirm endpoints. |
| GET /identity/churches | Compatibility ID/name/location list, now restricted to explicitly published profiles. Use the paginated network API for new discovery. |
| GET /identity/memberships | Own relationships. |
| PUT /identity/memberships/{id}/primary | Owner's active home church. |
| POST /identity/churches/{id}/requests | Submit membership request with optional message and share_contact (default false). |
| GET /identity/requests | Own request history. |
| POST /identity/requests/{id}/cancel | Cancel pending/more-info request. |
| GET /identity/churches/{id}/requests | Church administrator's review queue. |
| POST /identity/requests/{id}/review | Approve/reject/request more info; optional matched_member_id and reason. |
| GET /identity/churches/{id}/memberships | Administrator's church-local memberships. |
| PATCH /identity/memberships/{id} | Church administrator changes local membership status. |
| GET /identity/follows | Own follows. |
| PUT, DELETE /identity/churches/{id}/follow | Idempotent follow/unfollow. |

## Prompt 2: church network and administration

The member application now includes account registration/profile editing, recovery
screens using the existing reset API, Discover, public church profiles, Following
and My Church. Bottom navigation provides Home / My Church / Discover / Following /
Profile. Existing giving, groups, events, messages and prayers remain reachable
through Home and My Church. Empty membership lists remain a valid signed-in state.

Discovery supports name substring and case-insensitive country, region, city and
denomination filters; pages are bounded to 24 by default (maximum 100). Views are
All, Local (requires region or city), New on VINYRD (publication-record creation
order), Tanzania and the separate Followed Churches screen. Country codes are
normalized to uppercase; the schema is not tied to one country/city. Local is a
structured location filter, not GPS/radius ranking. No recommendations are added.

Only explicitly published profiles are anonymously readable. Publication has its
own editor in Members / Registration Requests in the existing staff console.
Events, announcements and ministries are intentionally entered public summaries;
there is no automatic join to private calendars, messages, ministry membership,
contact directories, geofences or SMS configuration. Unpublishing removes discovery
and public detail access; existing follows and memberships remain intact.

Follow and Request to join are separate controls and separate tables. This phase
serves public content to followers; it does not introduce follower-only private
content or a recommendation feed. Unfollow never changes membership.

The staff queue provides pending/approved/rejected/more-information/cancelled
filters, request date, applicant name/message, consented contact/photo and possible
unclaimed church-local matches. Suggestions are not proof of identity. Selecting
an existing member requires explicit reviewer confirmation in the UI; the server
rechecks tenant, ownership and competing claims transactionally. No matching by
email automatically grants access. Approval preserves the selected member ID and
all its history. Rejection and more-information notes remain visible to the owner;
neither deletes the account or follows. More-information replies use contact with
the office or cancellation/reapplication in this version.

Snapshot privacy: names/message are shared when requesting membership. Email,
phone and photo are included only when share_contact is true; no global profile
RLS policy is widened for reviewers. New local member records copy only the
consented snapshot contacts. Linking an existing local member preserves the
church's already-held contacts and history. Prior-phase requests receive name-only
snapshots on upgrade. Snapshots describe the submitted request, so later global
profile edits do not retroactively change them. External HTTPS photos are loaded
by the browser without a referrer; no server-side URL fetching or upload storage
is added.

Viewed church is sessionStorage `vinyrd_viewed_church`, validated against the
owner's active memberships before portal requests. The browser sends X-Church-ID
only to member-portal routes. Changing it reloads the selected private context,
without touching is_primary. My Church has a separate Make Home Church action.
Owner-side synchronization initializes the oldest active membership only when no
Home Church exists, under the same account lock used for primary changes. Church
reviewers never inspect other churches' memberships to choose Home Church.

All routes below are relative to /api/v1:

| Method/path | Contract |
| --- | --- |
| GET /network/churches | Anonymous paginated published directory: q, country, region, city, denomination, view, offset, limit. |
| GET /network/churches/{church_id} | Anonymous published allowlist only; unpublished/absent returns 404. |
| GET /network/me | Own memberships with church names, own request history and followed church IDs. |
| POST /network/me/initialize-home | Owner-only, idempotent initialization when no primary exists. |
| GET, PUT /network/admin/profile | Read/write only the authenticated administrator's church publication. The client cannot supply church_id. |
| GET /network/admin/requests | Own-church queue by status, 50 at a time; scoped unclaimed member suggestions. |

The existing identity follow, request, review and primary routes remain the mutation
APIs. Users cannot assign roles, approve their own requests (even if they are a
church administrator), or access the queue as an ordinary member. Errors and note
content are rendered as text, not executable HTML. Server authorization remains
mandatory regardless of hidden/disabled UI controls.

## Prompt 2 migration and staging procedure

New migration `20260925_0016_church_network.py` follows `20260925_0015`; there is one
Alembic head. It adds membership_requests.applicant_snapshot and
church_public_profiles, a geography index, public-profile RLS and a trigger that
also denies an administrator's self-review. No existing member/auth/attendance/
giving/group rows are removed or rewritten. Existing request messages/statuses are
preserved. No church is automatically published. Downgrade refuses destructive
removal; roll application code back while retaining additive data.

Public-profile RLS permits published reads, and draft reads/inserts/updates only
for an active Administrator whose existing users.branch_id matches. No delete
policy is installed. Request RLS remains owner/own-church-admin, with self-review
blocked both by service authorization and a PostgreSQL trigger. Giving and
attendance retain the existing server-enforced church scope rather than claiming
that RLS has been added to every legacy table.

Recommended staging steps (no production action has been run):

1. Back up and restore into isolated staging. Verify migration 0015 legacy email/
   branch prerequisites if staging is still at 0014. Rehearse the complete chain;
   inspect legacy member counts, IDs, credential hashes and histories afterward.
2. As schema owner, run `alembic upgrade head` from backend/. New runtime table
   grants must be applied explicitly, for example SELECT/INSERT/UPDATE on
   church_public_profiles to the actual backend runtime role. Existing grants
   on membership_requests cover its new column. Do not grant browser/PUBLIC access.
3. Run HTTP traffic with a non-owner NOSUPERUSER NOBYPASSRLS role. Verify ownership,
   grants and transaction-local actor context. Migration/bootstrap must use the
   schema owner. The unchanged Railway startup uses one URL for both; arrange the
   separate migration/runtime launch procedure before relying on RLS in deployment.
4. Preserve PARISHCONNECT_* secret values and existing API/URL configuration;
   changing token/password secrets can invalidate existing access. No new service,
   Supabase credentials, object store or third-party API key is required. The
   member app uses existing bearer auth; publish HTTPS asset/site URLs only.
5. Deploy backend and static frontend together in staging. As two separate church
   administrators, enter and explicitly publish profiles. Confirm draft exclusion,
   tenant separation, consent behavior and safe manual identity verification.
6. Repeat the browser journey and non-owner PostgreSQL tests, migration preservation
   and concurrent Home Church checks. Validate attendance, giving, groups, staff
   provisioning/imports and recovery for legacy and newly registered people.
7. Run production Python 3.12/Docker CI, readiness and backup-restore checks.
   Resolve the independently tracked SMS lint baseline before calling CI green.
   Production rollout is a separate authorized operation.

No new production environment variables are required by this phase. The browser
test has optional VINYRD_TEST_BROWSER=1 and VINYRD_BROWSER_ARTIFACTS; PostgreSQL tests
require VINYRD_TEST_POSTGRES_URL pointing to localhost/127.0.0.1. Test dependencies
are installed with `pip install -e ".[dev,browser]"` and
`python -m playwright install chromium` (CI installs Linux dependencies too).
Browser tests start a disposable loopback service on port 8003, which must be free.
They use an isolated file-backed SQLite copy to support concurrent browser calls.
PostgreSQL tests create/drop only uniquely named local test databases and roles.

## Validation and release readiness

* 142 tests passed: prior regression suite plus network/API privacy tests, real
  PostgreSQL migration/RLS tests and a real Chromium member/admin workflow. The
  browser journey also verifies legacy login/giving and global profile editing.
* PostgreSQL 16.15: 0014 -> 0015 -> 0016 with populated legacy tables and a populated
  0015 request; all legacy columns and request message/status remain preserved.
  Non-owner publication, tenant-denial, self-review denial, owner-home initialization,
  two memberships and concurrent primary updates pass.
* API regression covers Church A/B attendance and giving separation, follower/
  pending private-access denial, rejection preserving the account/follows,
  consent, matching/linking, draft privacy, publication filters and pagination.
* Chromium covers signup, discovery, separate follow/join, more information,
  verified legacy linking, rejection/reapplication, second membership, Home Church,
  viewed church switching, unfollow, legacy authentication and profile editing.
  Mobile discovery and desktop console were visually inspected; mobile has no
  horizontal overflow. Other browser engines and physical devices are not tested.
* Changed Python code passes Ruff. Full Ruff still reports exactly two pre-existing
  SMS findings: messages.py:428 BLE001 and services/sms.py:1 I001, left unchanged.
* All frontend JavaScript passes node --check; Python compileall and package wheel
  build pass. The existing static frontend has no bundle build, and neither a
  standalone typecheck nor TypeScript configuration exists. Syntax checks are not
  represented as typechecking. The existing wheel package list is narrow; production
  uses the unchanged Docker editable install, so wheel success is not a deployment
  validation.
* Docker engine is unavailable locally (dockerDesktopLinuxEngine pipe missing).
  Production container/Python 3.12 validation remains outstanding; local Python is
  3.14. Existing framework deprecation warnings remain. CI now includes the opt-in
  Chromium journey and syntax checks for every frontend JavaScript file.

Public-launch gates remain: verified recovery/email delivery and registration
abuse controls; an operational manual-identity verification procedure; non-owner
runtime deployment; backup/restore rehearsal and successful production container
validation. The existing production password-reset request prepares but does not
send its token. Recovery screens do not claim delivery or verified email; local
mode supports the existing demo token only. Email equality never proves identity.
Profiles and public content require church staff curation. ISO-style country codes
are format-validated, not backed by a country/administrative-area catalog yet.

Prompt 1 implementation remains in b0d1759 with documentation closeout de431cd.
The missing registration/profile screens were committed separately as dde5710.
The church network phase is a separate commit. No production deployment, merge or
push occurred. Prompt 2 is complete for staging review; Prompt 3 has not started.
