# Denomination template governance (Phase 5)

Baseline: `fe5f7aebb9fb41a2a2af49af9ba3a9d5919aa3d8`. This phase governs presentation snapshots. It does not modify Branch identity, memberships, offices, grants, proper names, ownership or ancestry. It uses the same engine for every denomination. No official institutional version 2 is published by this change.

## Audit and persistence choices

The existing configuration contains `hierarchy_snapshot` and `terminology_snapshot`; public organization labels live separately in `OrganizationUnit.labels_snapshot`. Proper names are in `canonical_name`/`localized_names`. Units may be published, owned by one branch and reused as ancestors by other branches. Existing setup is local-administrator-only; higher OrganizationAccessGrant scope does not confer denomination-wide publication authority. The Phase 4 resolver and public allowlist remain the presentation boundary.

Existing JSON and the append-only runtime audit log are sufficient for approved overrides and before/after history; no new table is introduced. `hierarchy_snapshot.governance` holds the installed base levels, approved overrides keyed by level and optional position, template provenance and release digest. The effective levels and terminology map retain the Phase 4 shape. Audit rows record denomination, actor, timestamp, request ID/digest, complete before/after snapshots, compatibility and publication impact. They contain no credentials or unrelated member data. Preview and override validation write nothing, including no audit rows. Blocked previews are not saved as pending approval records.

## Version registry and institutional publication

`denominations_v1.py` is the unchanged released catalogue data moved out of the current catalogue facade. A pinned content digest detects accidental historical edits. `template_registry.py` stores serialized immutable release entries and returns detached, validated values. Version identity is denomination plus positive integer; position identity is level key plus position key because historical denominations reuse titles/keys across levels. Duplicate level keys or duplicate position keys within one level are rejected. Staff title resolution uses the assignment level as well as the key; the runtime contract adds positions_by_level while retaining its legacy flat positions map. The current onboarding catalogue remains version 1; all nineteen historical version-1 definitions remain retrievable.

There is no HTTP template publication endpoint. A new institution-supplied version requires a separately reviewed code release: preserve the old module and registry entry, add a new immutable version, validate identifiers/labels/permission suggestions, retain evidence of institutional authorization, and independently approve the publication. If intentionally changing the default for new installations, update the current catalogue facade as a separate reviewed choice; never rewrite installed snapshots or historical releases. Institutional provenance requires an institution and authorization reference in the release metadata; the release reviewer must verify the underlying evidence. A reference alone is not proof of authenticity. Existing releases are classified `vinyrd_default`, not denomination-official. Test-only hypothetical releases exercise version 2/3 and are never installed into the production registry.

## API and approval

All endpoints are under `/api/v1/network/admin/organization/governance` and require an authenticated active local church Administrator. The existing selected-branch guard rejects another church context. A grant-only administrator cannot use governance to claim institutional authority or edit another church's configuration.

| Endpoint | Capability |
| --- | --- |
| `GET /` (without trailing slash also supported by router normalization) | Installed/available version, upgrade availability, compatibility, current revision, overrides and bilingual runtime levels |
| `GET /versions/{version}` | Retrieve a released version for this configuration's denomination |
| `POST /preview` | Read-only structured level/office/label/suggestion comparison and publication impact |
| `POST /overrides/validate` | Same read-only validation contract for local overrides |
| `POST /approve` | Explicit transactional application using expected revision, preview token and request UUID |
| `GET /history` | This church's approval history, including historical snapshots |

Strict request models forbid unknown fields, client roles/provenance, arbitrary templates and unsupported locales/versions. Labels are bounded, nonblank and reject control characters. An override is `{level_key, position_key?: null, labels: {en?: value, sw?: value}}`; null resets that locale to the installed base. Empty maps, duplicate targets and unknown keys are rejected. Overrides are classified only as `church_approved`. Existing overrides survive version upgrades; resetting restores the destination version's base. Canonical IDs never change. Missing Swahili continues falling back to English. Proper organization names are never translated or rewritten.

Approval locks the same PostgreSQL setup advisory key and the configuration row. It rechecks authority through server authorization and RLS, exact installed revision, destination release and the reviewed publication impact. The token includes proposed snapshots and publication scope, so a changed preview fails with 409. Matching request UUID and payload retries return the original approval; reusing the UUID with different input is rejected. Stale approvals and incompatible changes perform no partial writes. Configuration, allowed local unit labels and audit commit together. Preview availability never causes an upgrade.

## Compatibility and shared units

Diffs classify added, removed, renamed, unchanged and requires_review, retain canonical keys, and show both languages plus permission-role suggestions. Permission suggestions are informational and never applied to users, offices or grants. Hierarchy key/order/optional changes require a separately authorized structural workflow. All office-key removals are conservatively blocked, including apparently unused keys, so hidden assignments are never silently remapped/deleted. Additive offices and private office-label changes can be reviewed without granting authority.

A local label may be published only on the branch's exclusively owned, linked, active leaf. A boolean, actor-bound PostgreSQL helper checks for children and other branch/configuration references with complete database visibility, including private children hidden from the administrator. It returns no private data. Any changed ancestor/shared label requires independent approval; Phase 5 blocks the entire proposal rather than partially updating private configuration and public ancestry. This includes ancestors held in the same branch's custody: custody alone does not establish institutional approval. No independent shared-unit publication or custody-transfer workflow is introduced.

Existing setup now reuses a matching ancestor only when its installed labels also match. It cannot adopt a public unit with conflicting terminology merely because its name and parent match. A conflicting matching published ancestor causes setup to return 409 for independent review instead of cloning a parallel tree. Existing unit IDs, parent IDs, localized_names, publication flags, ownership and member relationships remain unchanged during upgrades.

## Migration and operating procedure

Additive migration `20260930_0021` follows `20260928_0020`. It introduces no table, column, backfill or server default, and preserves every installed snapshot. It adds:

- Actor-bound `vinyrd_org_labels_local(uuid)` boolean helper with fixed search path; no definer writes.
- RLS UPDATE policy allowing only the authorized local leaf.
- An invoker trigger permitting only labels_snapshot/updated_at changes; identifiers, topology, ownership, proper names and publication flags remain immutable.
- An audit history index on branch_id/action/created_at, also represented in ORM metadata.
- A local_unit_id configuration index for the exclusive-reference check, also represented in ORM metadata.

Use the existing [staging privilege-separation runbook](staging-initialization.md). Run Alembic as the migration owner, then reapply `python -m app.scripts.provision_database_access --runtime-role <runtime-role> --backup-role <backup-role>`. The runtime matrix now includes UPDATE on organization_units, constrained by the new policy and immutable-field trigger. Do not give HTTP ownership/BYPASSRLS. No new environment variable or bootstrap authority flag is needed. Missing updated privileges fail readiness checks; provision before restarting the new runtime.

Back up first, migrate to the single head 20260930_0021, provision, start the exact validated image, check `/health` and strict readiness, and validate representative TAG/Catholic/Lutheran/SDA accounts. Review terminology with institutions in staging. Do not run fixture-writing smoke scripts against production. Rollback application code only after checking compatibility; retain approved snapshots/history and do not downgrade a live schema automatically. No production deployment is performed by this phase.

The existing exhaustive pg_dump/restore covers all 31 application tables. Verification now compares full configuration snapshots, unit rows and template approval audit rows as well as counts/grants/head, then reprovisions and starts the restricted restored runtime. The Linux container workflow includes real HTTP governance preview/approval, idempotency/stale checks, shared-ancestor blocking and public label checks before backup.

## UI, validation and limits

Organization Administration has one Template Governance section: installed/available versions, configuration-driven bilingual level/office selectors, local override/reset, structured comparisons, provenance, publication impact, compatible approval and history. Editing inputs invalidates the reviewed proposal. Context changes discard old UI and never retain another denomination's comparison. Server checks remain authoritative if controls are bypassed.

Member web/native require no new mapping or client code. Unapproved previews leave their public payloads unchanged; approved local publication is delivered through the Phase 4 contract on the next fetch. The governance endpoints and private snapshots are not added to public APIs.

Tests cover all 19 immutable releases; TAG, Catholic, Lutheran and SDA upgrade flows; hypothetical versions; overrides, history and fallback; structural/shared-unit rejection; local and grant-only isolation; non-owner PostgreSQL RLS, hidden references, concurrent retries, and preservation of existing members, branches, offices and grants. Chromium covers comparisons, approval, history, unauthorized requests, incompatibility and context switching. Full suite and exact-SHA Linux results are recorded in the completion report.

Remaining limits: institutional publication is an independently reviewed code release, not an in-app denomination authority registry; shared ancestry/structural changes require a later authorized workflow; custom hierarchy creation remains explicitly `requires_configuration` unless an institution-supplied configuration already exists; history has no separate retention/pagination UI; no official translations or version-2 institutional changes are invented. Staging needs owner migration and runtime privilege reprovisioning before approval testing. Phase 6 is not started.

INSTALLED CONFIGURATIONS CHANGE ONLY AFTER AUTHORIZED APPROVAL.

SHARED ORGANIZATION UNITS CANNOT BE MODIFIED THROUGH AN UNRELATED CHURCH'S TEMPLATE UPGRADE.
