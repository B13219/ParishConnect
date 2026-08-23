# ParishConnect

ParishConnect is an ongoing church management and engagement platform designed to replace paper registers and disconnected spreadsheets with one secure, practical system.

## What it does

- Manages visitor, member, and household records.
- Supports QR-code and usher-assisted attendance check-in.
- Tracks events, ministries, tithes, and offerings.
- Provides announcements and leadership reporting workflows.
- Uses role-based access patterns to protect church information.

## Current status

This repository contains a working MVP foundation:

- FastAPI REST API
- SQLAlchemy models and Alembic migrations
- PostgreSQL-ready configuration with SQLite-backed tests
- Static administrative web interface
- Member and household management
- Attendance events, QR token windows, and check-in
- Stewardship records and summary reporting

The project is still in active development. Authentication hardening, hosted messaging integrations, mobile features, and production deployment are planned next.

## Technology

- Python
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL / SQLite
- HTML, CSS, and JavaScript
- Pytest and Ruff

## Repository structure

The complete cleaned source is available in `ParishConnect-source.zip`.

```text
backend/    API, database models, migrations, scripts, and tests
frontend/   Administrative web interface and QR check-in page
mobile/     Reserved for the member mobile application
docs/       Product requirements, roadmap, architecture, data model, deployment, and API docs
outputs/    Engineering notes and implementation handoffs
```

## Run the demo

From the `backend` directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
.\run-demo.ps1
```

In another terminal, serve the frontend:

```powershell
cd frontend
python -m http.server 5173
```

Then open:

- Admin interface: `http://127.0.0.1:5173`
- QR scan page: `http://127.0.0.1:5173/scan.html`
- API documentation: `http://127.0.0.1:8003/docs`

## Verification

- Backend test suite passing
- Ruff checks passing
- Active development roadmap maintained in `docs/post-demo-roadmap.md`

## Important note

The credentials and QR secret included in local defaults are development-only placeholders. Production deployments must use secure environment variables and must never commit real church or member data.

## Author

Built by [Beka Kawanara](https://github.com/B13219) as an ongoing full-stack portfolio project.


For the current post-demo development direction, see `docs/post-demo-roadmap.md`.

