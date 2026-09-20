# Vinyrd Frontends

The staff console and member webapp are static frontends served by the Vinyrd FastAPI
service in production.

- `frontend/index.html` → `/staff/`
- `frontend/member-app/` → `/member/`

For local development, the clients use `http://127.0.0.1:8003/api/v1`. On a hosted
domain they automatically use same-origin `/api/v1`.

An explicit `window.VINYRD_API_BASE` value can override the API location when needed.
