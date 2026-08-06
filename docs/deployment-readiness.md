# Deployment Readiness

This checklist separates the current demo setup from a safe client pilot or production launch.

## Environment

Copy `backend/.env.example` to `backend/.env` and replace every demo value before deploying:

- `PARISHCONNECT_ENVIRONMENT=production`
- `PARISHCONNECT_DATABASE_URL` pointing to a managed or protected PostgreSQL database
- `PARISHCONNECT_CORS_ORIGINS` containing only the deployed frontend domain names
- `PARISHCONNECT_AUTH_TOKEN_SECRET`, `PARISHCONNECT_QR_TOKEN_SECRET`, and `PARISHCONNECT_PASSWORD_SALT` set to long unique secrets
- `PARISHCONNECT_DEMO_PASSWORD` replaced or removed after real administrator accounts are created
- `PARISHCONNECT_ACCESS_TOKEN_MINUTES` set to a reasonable session lifetime

Run the readiness check:

```powershell
cd backend
python -m app.scripts.check_deployment_readiness
python -m app.scripts.check_deployment_readiness --strict
```

## Database

PostgreSQL is the target database for development and production. SQLite is only for local presentation fallback.

```powershell
cd backend
docker compose up -d postgres
alembic upgrade head
python -m app.scripts.seed_demo
```

For production, run migrations against the production `PARISHCONNECT_DATABASE_URL` and do not run demo seed scripts.

## Security Gates

- Create named administrator accounts instead of shared demo credentials.
- Confirm accountant users can view stewardship and reports, but cannot manage unrelated admin settings.
- Confirm ushers only see overview and attendance workflows.
- Confirm audit logs are created for user, branch setting, import, message dispatch, and stewardship actions.
- Keep backup/export access administrator-only until a formal data policy is agreed.

## External Services

These are intentionally not live yet and should be integrated behind provider-specific configuration later:

- SMS and USSD provider credentials
- Push notification provider credentials
- Payment gateway credentials such as Selcom
- Email provider credentials for password reset delivery

Until those are configured, the app should use demo delivery states and manual payment/reference capture.

## Pre-Demo Check

1. Start the API on `http://127.0.0.1:8003`.
2. Start the admin console on `http://127.0.0.1:5173`.
3. Confirm login, role-specific navigation, people flow, attendance, stewardship, communications, reports, imports, branch settings, and backup manifest export.
4. Run backend tests and frontend syntax checks.
5. Use only fake sample data unless the church has approved import, privacy, and backup procedures.
6. Review `docs/client-demo-runbook.md` and rehearse the demo story once end to end.
7. Run `powershell -ExecutionPolicy Bypass -File .\scripts\pre-demo-check.ps1` from the project root before the meeting.
