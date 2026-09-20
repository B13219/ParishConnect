# Vinyrd Member Webapp

Mobile-first member experience based on the approved Vinyrd Figma direction.

Implemented:
- Figma-matched Home screen
- Member sign-in using the existing ParishConnect auth API
- Explicit authenticated user to member profile linking
- Protected /api/v1/member-portal/me and member giving
- Figma-directed Profile screen with live member and branch data
- Exact shortcut/navigation SVGs exported from the Figma file
- Session-scoped bearer-token handling for the webapp
- Installable-webapp manifest foundation
- Existing staff/admin console kept separate

Local run:
1. Apply migrations and seed the demo data/auth records.
2. Start the backend on port 8003.
3. From frontend run: python -m http.server 5173
4. Open http://127.0.0.1:5173/member-app/login.html

The demo auth seeder links the first active member to a Member-role account. If that member has no email, it uses member@graceparish.test. The demo password remains parishconnect.

Next: Giving, Events, Groups and Messages can build on the authenticated member session.
