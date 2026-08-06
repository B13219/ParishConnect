# ParishConnect Admin Console

Static admin dashboard for the first presentation-ready phase.

## Run

Start the backend against PostgreSQL:

```powershell
cd C:\Users\bekas\Documents\Codex\2026-07-10\let\work\parishconnect\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8003
```

Start the admin console:

```powershell
cd C:\Users\bekas\Documents\Codex\2026-07-10\let\work\parishconnect\frontend
python -m http.server 5173
```

Open:

```text
http://127.0.0.1:5173/
```

## Notes

- `index.html` is the administrator console.
- `member.html` is the lower-permission member portal.
- The API base URL is configured in `app.js` for the local backend at `http://127.0.0.1:8003/api/v1`.
- For deployment, serve these files behind HTTPS and align backend `PARISHCONNECT_CORS_ORIGINS` with the deployed frontend domain.
