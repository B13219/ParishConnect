# Organization-scoped administration (Phase 3)

This phase extends validated checkpoint `c0f21cc8ac22369a4b565c823114d0ec3c2685ab` without rewriting its commits. FastAPI and PostgreSQL remain authoritative; no mobile code, Supabase, production deployment or main merge is involved.

**OFFICE ASSIGNMENT ALONE GRANTS NO VINYRD ACCESS**

**ORGANIZATION SCOPE DEFINES WHERE; PERMISSION ROLE DEFINES WHAT**

## Storage and migration

`20260928_0020` follows `20260927_0019`. It adds `organization_access_grants`: UUID primary key, user and organization-unit FKs, canonical permission role, scope mode, status, nullable granting actor FK, and timestamps. Scope is `unit_only` or `descendants`; status is `active`, `inactive` or `revoked`. Supported technical roles are administrator, pastor_leader, accountant, receptionist and usher. Office names and translations are never permission identifiers.

A unique (user, unit, role, scope) index prevents equivalent grants, including inactive/revoked duplicates; reactivate the existing row. User/status and unit/status indexes support authorization. Existing parent and branch-unit indexes are retained. New member, attendance and contribution branch indexes support constrained reporting. There is no identity/membership backfill, no new ancestor membership and no destructive downgrade. Index creation is transactional and should be scheduled appropriately for large production tables.

## Scope and delegation

`app/services/organization_access.py` is the canonical application resolver. It batches graph, branch, role and grant reads, traverses iteratively, and retains a separate coverage set per grant. PostgreSQL uses matching fixed-search-path security-definer helpers to traverse private topology without recursive RLS policies. The unrestricted topology helper has PUBLIC execute revoked. Exposed helpers use the transaction-local authenticated actor; they return booleans or that actor's authorized identifiers, not a global tree.

Traversal fails closed on cycles, missing/inactive ancestors and denomination inconsistency. Permission follows actual connected parent relationships, never a denomination name match. Independently rooted trees with identical names confer no shared authority. `unit_only` includes no children. `descendants` includes the selected unit and its nested children. No upward inheritance or wildcard exists.

Legacy User.branch_id plus UserRole remains effective only at that local Branch, including unconfigured churches. Local admins can delegate `unit_only` at their linked unit. A descendant-scope Administrator may delegate only contained scopes; a unit-only Administrator cannot delegate descendants, even when there happen to be no children today. Updates require authority over both old and proposed scopes. Self-management of grants is denied entirely; another authorized administrator must approve changes. Role/status changes are read on each request, not cached in JWT claims.

First higher-level authority cannot be self-created from branch custody. After independent governance verification, a migration-owner operator may run:

Initial authority now uses the guarded, one-shot operator command in [the staging runbook](staging-initialization.md). Both actor and recipient must be verified existing local Administrators in the configured tree. Deployment-owner credentials and a temporary bootstrap flag are required. Existing authority history blocks fresh initialization, including revoked grants; controlled recovery has a separate guard. Exact active retries are idempotent. Offices and memberships remain unchanged.

## APIs and context

Authenticated routes are under `/api/v1/organization-access`:

| Route | Behavior |
| --- | --- |
| GET /tree | Authorized units, scoped parent IDs, installed localized labels, verified offices and accessible Branch choices |
| POST /context | Validates a Branch selection and audits it; returns effective roles |
| GET /grants | Own grants and grants fully manageable by the actor; account ID/name only |
| POST /grants | Explicit contained grant to an active existing account |
| PUT /grants/{id} | Change profile, mode or status; revoke through status=revoked |
| GET /offices | Office holders in administrable units, independent of permission grants |
| PUT /offices | Assign/deactivate a verified denomination office without changing permissions |
| GET /summary?unit_id=... | Capability-filtered church/member/attendance counts and finance totals by currency |

Each subsequent local module request carries `X-Vinyrd-Branch-ID`; central server authorization verifies it against local access or the relevant grant before setting the ORM/RLS tenant context. The header cannot alter User.branch_id, membership, or Home Church. The selection is not a bearer permission and revocation is effective on the next request. Transaction-local RLS settings are restored after transaction boundaries by trusted server hooks.

Existing branch modules remain branch-based. Network membership review and public profile management also use verified selected context. Initial organization setup remains a local-administrator workflow, separate from hierarchy administration. Organization tree roots are clipped to the actor's visibility; private parent names and sibling units are omitted.

## Privacy and security decisions

- New hierarchical pastoral roles do not inherit the legacy local pastor's finance access. Finance requires Administrator or Accountant in each included branch.
- Mixed grants retain independent scopes: section administration plus district accounting does not grant district administration or member profiles.
- Sensitive `/staff/` prayer, pastoral-note, private lesson and credential-management routes remain available only through existing local role authority. New hierarchy grants do not unlock those routes. Composite legacy weekly reports require Administrator for new hierarchical access; other roles use the filtered organization summary. Legacy local behavior is unchanged.
- Member/contact modules continue their existing module role requirements. Accountant grants do not expose full member profiles. No personal records or pastoral content appear in hierarchy summaries.
- The legacy admin backup manifest includes sensitive-module counts and remains local-authority-only for new hierarchy users. Full infrastructure backups cover all tables.
- Local user administration and member-access reset/status routes cannot take over an account holding any organization grant, even when RLS hides its higher grant from the local admin. Account owners retain their normal reset flow.
- Grant create/update/revoke, office edits and context selection are audited without credentials. Existing denial paths do not persist audit rows across rejected/rolled-back requests; this phase does not claim durable denied-attempt auditing.
- Existing RLS is retained. New grant policies enforce old/new containment, prevent self-grants, freeze grant identity, and provide no DELETE policy. Identity policy additions require both a verified selected branch and a qualifying explicit grant. Identity column guards and self-review prohibition remain. There are no USING(true) policies.
- Existing operational tables continue the established trusted-server ORM tenancy pattern. This phase does not claim that all legacy operational tables have database RLS. Never expose runtime database credentials to clients.

## Console and examples

Organization Administration shows a scoped tree, separate organization/Branch selectors, localized level labels, offices, grants and scoped summary. Grant recipients use an existing VINYRD account UUID to avoid introducing a global personal-directory search. Office and access controls remain separately editable. Custom hierarchy authorization works without catalogue hard-coding; custom office editing still requires a verified catalogue, and custom hierarchy construction remains a separate workflow.

Changing church context reloads the console to discard cached local data. Refresh revalidates grants, removes revoked contexts and updates role controls. UI hiding is supplementary to server checks.

TAG example: an explicit Jimbo/District Administrator descendant grant covers its Sehemu/Sections and linked local churches, excluding sibling Jimbo and parent units. A section Administrator plus district Accountant can administer only the section while viewing finance across the district.

Catholic example: a Diocese descendant grant covers linked descendant parishes, with verified/default catalogue labels. A parish-only grant does not include the Diocese. A custom network uses exactly the same relationship engine.

## Deployment and validation

Follow [staging initialization](staging-initialization.md) for separate runtime, migration, backup and restore credentials. Production/staging startup validates the runtime privilege matrix and migration head. The restore verifier automatically reapplies the restricted helper ACL and runtime grants, then starts the restored application and checks health. No schema migration was added in Phase 3.5; the single head remains `20260928_0020`.

The existing feature-branch Linux workflow is reused. It tests the exact pushed commit, builds the existing production Dockerfile, migrates an empty PostgreSQL database, starts production commands, serves HTTP as non-owner/NOBYPASSRLS, runs legacy/organization/hierarchy smoke, verifies a real backup/restore including grant rows, and restarts the container. The dynamic full-database backup now covers 31 application tables. Restore retains functions/policies, but role ownership/privileges still require separate provisioning with the established --no-owner/--no-privileges restore process.

Test coverage includes local legacy admins, nested and unit-only access, siblings/parents, TAG/Catholic/custom trees, mixed capabilities, offices without grants, grants without offices, lifecycle/revocation, self-escalation, arbitrary branch headers, private module denials, unchanged memberships, cyclic graphs, credential takeover prevention, real non-owner PostgreSQL and Chromium. The scope loader uses a fixed number of entity queries, not one query per node; no cross-request permission cache is introduced. Large-network load benchmarking remains a staging task.

This document describes implementation and validation procedures; the completion report records actual final results and the exact tested SHA. Production deployment and main merge require a separate decision.
