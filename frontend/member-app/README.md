# Vinyrd Member Webapp

Mobile-first member experience based on the approved Figma direction.

Current first slice:
- Figma-matched Home screen
- Live member greeting and upcoming event from `GET /api/v1/member-portal/me`
- Exact Figma-exported shortcut and navigation SVG assets
- Installable-webapp manifest foundation
- Existing admin console kept separate

Run the backend on port 8003, then serve `frontend` on port 5173 and open:

`http://127.0.0.1:5173/member-app/`

Next slice: member authentication plus the Profile screen.
