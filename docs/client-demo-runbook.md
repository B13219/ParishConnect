# Client Demo Runbook — Phase 6 acceptance

Use this runbook on the isolated staging deployment before showing VINYRD to a
church client. A successful local demo is not evidence of staging readiness.
Follow [staging initialization](staging-initialization.md) for migration, credentials
and authority; [template governance](denomination-template-governance.md) for upgrades.

## Demo Objective

Show that Vinyrd can replace paper registers and scattered spreadsheets with one practical workflow for people, attendance, communication, stewardship, reporting, and administration.

## Demo Story

1. Login as an administrator and show role-based access.
2. Open Overview to show the current parish picture.
3. Register a visitor and convert the visitor to a member.
4. Add or review a household with children/dependents.
5. Create or select a service, then show manual and QR attendance flows.
6. Record a stewardship entry with a simple payment/reference note.
7. Show weekly attendance and stewardship reports.
8. Compose a message, choose recipients, dispatch it, and open recipient delivery status.
9. Switch roles to show that ushers, accountants, pastors, and administrators see different workspaces.
10. Open member portal to show the lower-permission member view.
11. Show branch settings, audit logs, and backup manifest export as administrative controls.
12. Preview/confirm denomination setup using clearly fictional organization names.
    Show TAG and one non-TAG tree in English, Kiswahili and bilingual mode. Proper
    names and OrganizationUnit IDs must stay unchanged when language changes.
13. Assign an office, then demonstrate that it grants no VINYRD permission. Use an
    independently approved organization grant to demonstrate contained access,
    context switching and revocation. Never infer authority from a title.
14. In the member app, discover and follow another church, request membership and
    switch Home Church. Demonstrate that following and Home Church do not create
    ancestor memberships or remove existing memberships.
15. Preview a terminology override, approve as the local administrator and inspect
    history. Shared-ancestor changes require review. Use hypothetical upgrade
    versions only in isolated acceptance fixtures, never as official releases.

## Talking Points

- The system supports QR/manual attendance, household-assisted attendance and
  member self-service. SMS delivery requires separately verified provider configuration.
- Financial data is separated by role; accountants can focus on stewardship and reports without becoming full administrators.
- Demo data is fake. Real church data should only be imported after permissions, backups, and data handling are approved.
- Payment providers such as Selcom are planned after the core stewardship flow is stable.
- The member webapp is live in the pilot build with profile, giving, events, groups, messages, prayers, Bible content, and sermon lessons.
- Discovery, following and membership requests are implemented separately. Native
  Android/iOS code and EAS internal profiles exist; record the actual validated
  preview artifact before offering installation. Store distribution is not approved.

## Pre-Demo Checklist

- Use the confirmed staging HTTPS origin, with `/staff/`, `/member/` and `/api/v1`.
  Local development ports are not staging deployment instructions.
- PostgreSQL is at `20260930_0021`; runtime privileges are reprovisioned, operator
  secrets/flags removed, and initial authority independently verified.
- `python -m app.scripts.check_deployment_readiness --strict --check-database` passes.
- Use only approved fake staging fixtures, including legacy and custom-required churches.
- Record the exact CI/staging/mobile SHA, full test results and skips. Report the
  two existing SMS Ruff findings separately; do not claim a clean full lint run.
- Full PostgreSQL backup/restore, restored organization/governance checks and
  restored grant/history evidence pass. The admin manifest is not a recovery archive.
- Browser cache is refreshed so the latest `app.js` is loaded.
- No real church records are used unless the client has approved data handling.

## Demo Boundaries

Be clear that these items are planned but not yet production-live:

- Real SMS provider delivery and USSD acceptance are not proven by simulated messages.
- Payment gateway integration.
- Email delivery for password reset.
- Production deployment, domain configuration and operational approval remain separate gates.
- Real data migration from a church's existing spreadsheets.
- Native store publication and physical-device acceptance remain separate from
  automated native tests and an internal preview build.
- Verified national news feeds, YouTube/Zoom attendance streams and road seminar pages.
- Custom denomination hierarchy authoring and institution-approved future template
  versions are not supplied by the built-in `custom_required` fallback.

## Follow-Up Questions For Client

- Which roles should approve member changes, transfers, and giving corrections?
- How does the church currently identify households and dependents?
- What weekly reports do leaders already expect?
- Which payment providers are preferred?
- Which members are likely to use smartphone access, SMS, or USSD?
- Would the church value a future verified news/events feed across branches or national church bodies?
- How should online attendance be recognized for YouTube livestreams, Zoom meetings, road seminars, and remote services?
- Who should be responsible for imports, backups, and audit review?
