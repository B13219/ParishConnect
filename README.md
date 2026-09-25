# Vinyrd

Vinyrd is a church management and member-engagement platform for people, attendance,
households, communities, ministries, stewardship, communication, pastoral care, sermons,
and member self-service.

## Pilot v1.0

The FastAPI deployment serves the web applications and API. The native mobile
application is built separately and shares the same backend:

- **VINYRD Staff Console:** `/staff/`
- **VINYRD Member Webapp:** `/member/`
- **VINYRD Member Mobile App:** native React Native/Expo application in
  [`apps/member-mobile/`](apps/member-mobile/README.md), built separately for Android/iOS
- **API:** `/api/v1`
- **Health check:** `/health`
- **API docs:** `/docs`

Production uses PostgreSQL. The FastAPI service serves both frontends on the same HTTPS
origin, so hosted deployments do not require cross-origin frontend/API wiring.

## Core capabilities

- Member, visitor, household, community, and ministry management
- Member account provisioning and authenticated member self-service
- Manual, QR, and geofence-assisted attendance
- Giving/stewardship records
- Messaging and announcements
- Prayer requests with pastoral follow-up workflow
- Sermon management and member-facing published sermons
- Private member sermon lessons
- Role-based access and audit logs
- Backup manifest plus PostgreSQL dump/restore verification

## Local development

See `backend/README.md` and `frontend/README.md`.

## Production gate

A merge to the pilot branch is validated with:

1. PostgreSQL migrations
2. full Pytest suite
3. Ruff
4. JavaScript syntax checks
5. strict production readiness check
6. real HTTP pilot journey
7. PostgreSQL dump + restore verification

The legacy `PARISHCONNECT_` environment-variable prefix is intentionally retained for
backward compatibility while the product-facing brand is Vinyrd.
