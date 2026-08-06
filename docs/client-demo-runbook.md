# Client Demo Runbook

Use this runbook before showing ParishConnect to a church client or stakeholder group.

## Demo Objective

Show that ParishConnect can replace paper registers and scattered spreadsheets with one practical workflow for people, attendance, communication, stewardship, reporting, and administration.

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

## Talking Points

- The system supports gradual transition: QR, manual entry, household-assisted attendance, SMS/USSD later, and member self-service after that.
- Financial data is separated by role; accountants can focus on stewardship and reports without becoming full administrators.
- Demo data is fake. Real church data should only be imported after permissions, backups, and data handling are approved.
- Payment providers such as Selcom are planned after the core stewardship flow is stable.
- A member app/webapp is a planned later phase after SMS/USSD, giving smartphone users a banking-app style self-service experience.
- The long-term member app can become a verified church network for national church news, followed-church feeds, YouTube/Zoom service attendance, road seminars, and event discovery.

## Pre-Demo Checklist

- Backend is running on `http://127.0.0.1:8003`.
- Frontend is running on `http://127.0.0.1:5173`.
- PostgreSQL has migrations applied and demo seed data loaded.
- `python -m app.scripts.check_deployment_readiness` has been run so demo-only settings are understood.
- `powershell -ExecutionPolicy Bypass -File .\scripts\pre-demo-check.ps1` has been run from the project root.
- Backend tests and lint are passing.
- Browser cache is refreshed so the latest `app.js` is loaded.
- No real church records are used unless the client has approved data handling.

## Demo Boundaries

Be clear that these items are planned but not yet production-live:

- SMS and USSD provider integration.
- Payment gateway integration.
- Email delivery for password reset.
- Production hosting, HTTPS, and domain configuration.
- Real data migration from a church's existing spreadsheets.
- Member self-service app/webapp beyond the current lightweight member portal.
- National church news feeds, YouTube/Zoom attendance streams, road seminar pages, and cross-church network features.

## Follow-Up Questions For Client

- Which roles should approve member changes, transfers, and giving corrections?
- How does the church currently identify households and dependents?
- What weekly reports do leaders already expect?
- Which payment providers are preferred?
- Which members are likely to use smartphone access, SMS, or USSD?
- Would the church value a future verified news/events feed across branches or national church bodies?
- How should online attendance be recognized for YouTube livestreams, Zoom meetings, road seminars, and remote services?
- Who should be responsible for imports, backups, and audit review?
