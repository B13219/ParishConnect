@'

\# ParishConnect Post-Demo Roadmap



\_Last reconstructed: 23 August 2026\_



\## Purpose



This document is the working development direction agreed after the ParishConnect demo. It supplements `product-requirements.md` and is the source of truth for sequencing post-demo work.



The goal is to move ParishConnect from a presentation-ready MVP into a pilot-ready V1, then into a secure hosted product with inclusive communications, member self-service, payments, and commercial scale.



\## Phase 1 — Finish and Freeze the Core Admin V1



\### People and registration



\- \[x] Member and visitor registration.

\- \[x] Search-first People interface; records remain hidden until searched/requested.

\- \[x] Separate Add Member and Add Visitor forms with show/hide controls.

\- \[x] Expanded member profile view.

\- \[x] Household creation and membership.

\- \[x] Household summary in member profiles.

\- \[x] Member profile → household navigation.

\- \[x] Household → linked member profile navigation.

\- \[x] CSV import foundation for spreadsheet migration.

\- \[ ] Final visitor profile/follow-up UX review.

\- \[ ] Validate visitor-to-member conversion and duplicate handling.



\### Community / cell groups



Support small-community structures used by churches, including Catholic and Lutheran contexts, without hard-coding one denomination's terminology.



\- \[x] Community group data model and migration.

\- \[x] Community memberships.

\- \[x] Create/view communities or cells.

\- \[x] Add/remove members and manage membership.

\- \[x] Community information in member profiles.

\- \[ ] Final permissions and leadership UX review.



\### Denomination and church configuration



\- \[ ] Add/verify denomination-aware church configuration.

\- \[ ] Keep terminology configurable for communities, ministries, services, and leadership structures.

\- \[ ] Keep interface language independent from denomination.



\### Language and localisation



\- \[ ] Add English and Swahili administrative interface support.

\- \[ ] Allow church/admin language selection.

\- \[ ] Preserve individual member language preferences for communications/member-facing experiences.

\- \[ ] Review forms, validation, attendance screens, and reports for translation readiness.



\### Ministries



\- \[ ] Review the existing Ministry model/API before adding anything new.

\- \[ ] Create/manage ministries and ministry meetings where missing.

\- \[ ] Assign/remove members from ministries.

\- \[ ] Show ministry membership in member profiles where appropriate.

\- \[ ] Track ministry-meeting attendance through the shared attendance system.

\- \[ ] Keep ministries distinct from geographic/pastoral community cells.



\### Attendance hardening



\- \[x] Manual attendance foundation.

\- \[x] QR attendance foundation.

\- \[x] Event/service attendance tracking.

\- \[x] Household/dependent attendance support.

\- \[x] Geofence/location attendance foundation.

\- \[ ] Final service-day workflow QA for ushers/receptionists.

\- \[ ] Verify authorized post-service corrections and auditability.

\- \[ ] Verify unreliable-network/offline-friendly recovery.

\- \[ ] Stress-test with realistic congregation sizes.



\### Stewardship correctness



\- \[x] Individual contribution foundation.

\- \[x] Household contribution foundation.

\- \[x] Contribution history/reporting foundation.

\- \[ ] Ensure individual offerings remain individually traceable even when a person belongs to a household.

\- \[ ] Treat giving as household giving only when explicitly recorded that way.

\- \[ ] Keep spouses and eligible children independently traceable for stewardship follow-up.

\- \[ ] Final permissions review for sensitive financial information.



\### Phase 1 integration and QA



\- \[ ] Full workflow test: login → registration → household/community/ministry → attendance → stewardship → reporting.

\- \[ ] Responsive layout and dialog/navigation review.

\- \[ ] Remove obsolete/duplicate controls and scripts.

\- \[ ] Review empty/loading/error/validation states.

\- \[ ] Extend automated tests for new Phase 1 behavior.

\- \[ ] Run full Pytest and Ruff checks.

\- \[ ] Update documentation and pilot runbook.

\- \[ ] Freeze Phase 1 before major visual/security restructuring.



\### Phase 1 exit criteria



The core administration product is coherent, tested, documented, and stable enough that subsequent work focuses on production quality rather than missing core church structures.



\## Phase 2 — VYNARD Product Polish and Identity



Goal: turn the functional admin V1 into a consistent professional product experience.



\- Establish the VYNARD/ParishConnect product identity and visual system.

\- Polish/redesign the administrative UI without destabilising completed workflows.

\- Improve hierarchy, forms, dialogs, navigation, dashboards, lists, responsiveness, and accessibility.

\- Standardise reusable frontend interaction patterns.

\- Keep the interface approachable for non-technical church staff.



\## Phase 3 — Authentication, Permissions and Production Hardening



Goal: make ParishConnect safe enough for a controlled real-church pilot.



\- Replace demo/shared credentials with named administrator/staff accounts.

\- Harden authentication and session/token handling.

\- Complete role-based permissions and least-privilege review.

\- Verify audit logs for sensitive actions.

\- Secure production secrets and environment configuration.

\- Enforce HTTPS in hosted environments.

\- Formalise backup/restore and administrator-only backup/export access.

\- Review privacy and retention before importing real church data.

\- Complete production database/migration procedures.



\## Phase 4 — Messaging, SMS and USSD



Goal: support inclusive communication before relying on a smartphone app.



1\. Stabilise service-day attendance.

2\. Finish messaging queue, recipient targeting, preferences, and delivery-status abstraction.

3\. Integrate a real SMS provider.

4\. Add/validate USSD workflows for feature-phone users where appropriate.

5\. Keep delivery callbacks/status provider-aware.

6\. Add push notifications later when the member app has device tokens.



Messaging should support church-wide, branch, ministry/group, community/cell, and targeted member/visitor communication while respecting language preferences and permissions.



\## Phase 5 — Hosted Deployment and Pilot Church



\- Deploy backend and PostgreSQL to a protected hosted environment.

\- Deploy admin frontend with production CORS and HTTPS configuration.

\- Configure backups, monitoring, logs, and recovery.

\- Use controlled migration/import for approved church data.

\- Train staff according to roles.

\- Pilot with the first church before broad sales.

\- Collect operational feedback and fix pilot blockers.



Planning range: roughly 2–4 weeks for MVP polish and 1–2 months for a meaningful pilot cycle; broader V1 timing depends on integrations and pilot feedback.



\## Phase 6 — Member App / Webapp



The member experience should operate on a self-service-with-approval principle: members see their own information and initiate requests, while staff retain approval authority for sensitive record changes.



\- Secure member authentication.

\- View profile, household, community/cell, ministry, and branch information.

\- View contribution history, receipts, and summaries.

\- Receive announcements, reminders, and event notices.

\- QR/location attendance where appropriate.

\- Submit profile update, prayer, and pastoral follow-up requests.

\- Request branch/church transfers subject to approval.

\- Join verified church livestreams/online meetings.

\- Push notifications after device registration exists.



Android is the initial mobile priority; a webapp can complement it where useful.



\## Phase 7 — Payments and Digital Giving



\- Integrate an approved payment provider/gateway.

\- Match transactions to members/households without losing individual stewardship traceability.

\- Generate references/receipts and reconciliation records.

\- Keep payment workflows separate from full accounting.

\- Add member-initiated digital giving after the payment layer is stable.



\## Phase 8 — Commercial Launch and Multi-Church Growth



\- Finalise packages, implementation/training, support, and subscription billing.

\- Standardise onboarding and spreadsheet/paper migration.

\- Prepare remote deployment for churches in other regions.

\- Support branch and multi-parish/church structures safely.

\- Build partner/referral acquisition channels.

\- Use pilot evidence/testimonials to support sales.

\- Scale monitoring, reporting, support, and operations as the church count grows.



Earlier planning targeted the first 5 churches during the initial post-demo build, growth toward 20+ churches during the mobile/finance expansion, and wider Tanzanian scaling after the product and pilot model are proven.



\## Later Platform Direction — Church Network Layer



Outside the initial product promise, ParishConnect can later expand into a verified church network with church/diocese/ministry feeds, followed-church updates, livestream/online attendance, event discovery, conferences and road seminars, sermon/media libraries, prayer/testimony features, and cross-branch transfers.



\## Development Rule



\*\*Core admin correctness → product polish → security → SMS/USSD → hosted pilot → member app → payments → commercial scale → network platform.\*\*



New ideas should be recorded without derailing the active phase unless they solve a current blocker.

'@ | Set-Content -Encoding UTF8 docs\\post-demo-roadmap.md

