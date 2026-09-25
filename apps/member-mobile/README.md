# VINYRD Member Mobile

A genuine React Native application using Expo, TypeScript and Expo Router. It
coexists with `frontend/member-app/` and uses the same FastAPI/PostgreSQL backend.
There is no WebView shell or alternate identity provider.

## Installation and configuration

Requirements: Node 22.13+ and npm. Validated with Node 24, Expo SDK 57.0.25,
React Native 0.86.3, React 19.2.3 and Expo Router 57.0.23.

From this directory:

```sh
npm ci
cp .env.example .env
# Set EXPO_PUBLIC_VINYRD_API_BASE before starting Metro.
npm start
```

On PowerShell use `Copy-Item .env.example .env`. Do not commit `.env`.
The backend needs migration `20260925_0016`; churches must explicitly publish
their profiles before they appear in Discover.

`EXPO_PUBLIC_VINYRD_API_BASE` is the sole API base, including `/api/v1`. It is
public bundle-time configuration, never a place for secrets. Components contain
no server hosts. A missing URL produces an actionable error.

- Production/internal release: use the approved HTTPS staging/production API URL.
  Release code rejects HTTP. A URL change requires a new bundle/build; changing
  a Railway variable cannot reconfigure an installed mobile app.
- Android emulator development: the host loopback alias can be used, for example
  `http://10.0.2.2:8003/api/v1` for a local backend on port 8003.
- Physical device: use HTTPS staging or a reachable development LAN address.
  A phone's localhost is the phone. For LAN development, bind Uvicorn to
  `0.0.0.0`, use a trusted network and allow the development port in the firewall.
- HTTP is accepted only in development (`__DEV__`). Prefer HTTPS on physical
  devices, including iOS ATS compatibility. No global release cleartext exception
  is added. Restart Metro after editing `.env`; use `npx expo start --clear` if needed.

Native clients need no browser CORS changes. Existing FastAPI authorization and
PostgreSQL RLS remain authoritative.

## Expo Go and Android workflow

Use an Expo Go version compatible with SDK 57. Current features use Expo-bundled
modules, including SecureStore, without custom native modules. If the Play Store
version differs, use Expo CLI to install a matching Android Expo Go build.
Run `npx expo start` and scan the QR code, or `npx expo start --android` with an
emulator running. SecureStore is native: there is intentionally no browser storage
fallback. Use the existing VINYRD Member Webapp for web access.

For local native development:

1. Install Android Studio, SDK platform/build tools for API 36, platform-tools,
   an emulator image and a compatible JDK (Java 17+ for the generated Gradle setup).
   Configure `ANDROID_HOME`, `JAVA_HOME` and verify `adb devices` sees your target.
2. Set the device-reachable development API URL and start the backend separately.
3. Run `npm run android:build` (`npx expo run:android`). Expo generates the ignored
   Android project, compiles the debug app and starts Metro.
4. Test registration/login/restoration/logout, both churches, Home Church and
   viewed-context separation on the emulator or physical device.

Do not hand-edit generated `android/` or `ios/` folders. Use app configuration and
config plugins. Android is the initial priority; iOS support remains architectural
and has not been built/tested here. Local iOS builds require macOS/Xcode.

Locally validated: Android Metro/Hermes export and native Android project
generation. Not validated: Gradle compilation, APK installation or device execution.
This host has no Android SDK/ADB or configured Java toolchain; `expo run:android`
fails at SDK discovery. No APK has been produced.

## Exact next step toward an installable Android test APK

The included EAS `preview` profile builds an internally distributed APK. After
an Expo account/project and an HTTPS staging backend are available:

```sh
npx eas-cli@latest login
npx eas-cli@latest init
# Set EXPO_PUBLIC_VINYRD_API_BASE in the EAS environment used by preview.
npx eas-cli@latest build --platform android --profile preview
```

Confirm `app.vinyrd.member` as the application ID during project setup. An ignored
local `.env` alone is not reliable cloud build configuration. EAS init provides
the project ID; none is fabricated here. Review account/signing/build-cost prompts
when running these commands. Download the resulting APK for internal testers;
do not submit to a store for this foundation phase. No EAS project, credentials,
cloud build or store submission was created by this task.

Alternatively, install the local toolchain and run `npm run android:build` for
an installable debug build without an EAS account.

## Screens and coverage

| Area | Native implementation |
| --- | --- |
| Welcome, Create Account, Login | Real account endpoints, readable validation errors, zero-membership login |
| Onboarding, Account/Profile | Optional onboarding, global profile editing, read-only email, HTTPS avatar URL |
| Home | Account greeting, membership/follow summary, private feature navigation |
| My Church | Membership states, request history, viewed context and separate Home Church selection |
| Discover | Name, country, region, city, denomination; All/Local/New/Tanzania views; pagination |
| Church Profile | Public logo/about/services/events/announcements/ministries/contacts, distinct Follow and Request to join |
| Following | Follow/unfollow; withdrawn public profiles handled without losing the follow relationship |
| Membership | Explicit contact consent, pending/more-info/rejected/approved states, cancellation/reapplication |
| Events | API-backed events and checked-in status; no QR/location submission yet |
| Giving | Church-scoped total and recent records; no payment collection or new giving entry |
| Groups | Existing community/ministry memberships |
| Messages | Existing member-visible messages |
| Prayer | Own history and submission, explicit contact/sharing preferences |
| Sermons/Bible | Published sermons, scripture references and existing personal lessons; no full Bible corpus/reader |

Main tabs: **Home / My Church / Discover / Following / Profile**. Secondary screens
use the member stack. Native controls, Safe Area, keyboard handling, responsive
content widths, green/charcoal/gold/off-white colors and the existing circular
VINYRD crest preserve the webapp's visual language without loading its website.

## Structure

```text
app/                    Protected auth/member stacks, five tabs and secondary routes
components/             Native controls/cards, layout and church-context display
features/auth/          Login, registration and profile forms
features/network/       Discovery, profiles, following and membership screens
features/portal/        Private church feature screens
services/api.ts         Central transport/config/headers/errors/timeouts
services/endpoints.ts   Typed bindings to inspected FastAPI routes
services/session.ts     Testable restoration/login/logout/expiry state machine
services/secureStorage.ts SecureStore adapter; only persisted token
services/networkState.ts Viewed context separate from server primary membership
hooks/                  Focus-aware loading and stale-response protection
providers/              Account/session lifetime and network state
types/                  API data contracts, not duplicated authorization rules
constants/              VINYRD palette
assets/                 Existing crest and attribution
scripts/                Disposable live API contract verification
tests/                  Session, transport, network, storage and native screen tests
```

Later native capabilities should be independent permission-gated adapters.
Notifications subscribe to authenticated session lifetime; QR/camera/location
submit through backend attendance APIs with explicit church context; biometrics
wrap SecureStore unlock without replacing server authentication. Router and the
`vinyrd` scheme establish the deep-link boundary. Verified app links and deferred
navigation are not configured yet. No push/camera/location/biometric permission is
requested. Sensitive audio/camera/location/storage permissions are blocked in
Android configuration.

## Authentication and tenant boundaries

- Existing FastAPI bearer identity only; no Supabase/Firebase/Clerk integration.
- Tokens use Expo SecureStore with a namespaced key, dedicated keychain service
  and `WHEN_UNLOCKED_THIS_DEVICE_ONLY`. The plugin configures Android backup
  exclusions. No token is stored in AsyncStorage, sessionStorage, source or logs.
- Startup validates the stored token through `/auth/me` before exposing protected
  routes. A 401 clears the token/session. Network failure preserves the secure
  token and offers retry/sign-out. Membership 403 does not erase a valid login.
- Local sign-out works when the server is unreachable. Serialized storage and
  session revisions prevent late login/401 responses from affecting a newer
  session. Secure storage failures are surfaced rather than reported as success.
- The backend has no refresh-token API or server-side logout revocation. Expiry
  requires sign-in; an issued bearer token otherwise remains valid until expiry.
- A global account remains usable with no memberships. Follows grant no private
  member permissions. UI guards aid navigation; the server enforces authorization.
- Viewed church is session-memory state. Only private portal requests receive
  `X-Church-ID`. Profile/network/primary mutations do not. Changing viewed church
  does not change Home Church or leave memberships. Owner APIs initialize/select
  primary membership. Context changes hide prior private data immediately and
  discard late responses. Private records are not cached to disk.
- Account-specific network state is discarded when its authenticated provider
  unmounts. Contact sharing on a membership request defaults to off.

## APIs integrated

All paths are relative to the configured `/api/v1` base:

- POST `/auth/register`, `/auth/login`, `/auth/logout`; GET `/auth/me`.
- GET/PUT `/identity/me`.
- GET `/network/churches`, `/network/churches/{id}`, `/network/me`;
  POST `/network/me/initialize-home`.
- PUT/DELETE `/identity/churches/{id}/follow`; POST
  `/identity/churches/{id}/requests`, `/identity/requests/{id}/cancel`;
  PUT `/identity/memberships/{id}/primary`.
- GET `/member-portal/me`, `/member-portal/events`, `/member-portal/groups`,
  `/member-portal/messages`, `/member-portal/prayers`, `/member-portal/sermons`,
  `/member-portal/sermon-lessons`; POST `/member-portal/prayers`.

No approval or staff-role assignment API is exposed by mobile screens. No new
backend endpoint or database migration was required.

## Tests and checks

```sh
npm run typecheck
npm run lint
npm test
npx expo-doctor
npx expo install --check
npm run export:android
```

The mobile suite covers 33 cases: native account/request forms, zero-membership
Home, request states, secure persistence, restoration/expiry, network/storage
failures, stale auth responses, discovery filters, following, approval, primary
selection and context isolation. Jest mocks native interfaces; these are not
emulator/device tests.

For actual mobile-service HTTP integration, install backend dev dependencies and
run from the repository root:

```sh
python apps/member-mobile/scripts/verify_api_contract.py
```

This compiles the actual TypeScript services and uses Node fetch against a
temporary loopback FastAPI server and SQLite copy. It covers registration,
restoration, profile, discovery/follows, more-info, legacy linking, second church,
Home Church/context, private reads, prayer, unfollow/logout and cross-tenant denial.
It never targets production. PostgreSQL RLS is tested by the unchanged backend
suite, which passed all 142 tests with PostgreSQL and Chromium enabled.

## Known limitations and public-launch gates

- No Android emulator/device run, signed APK or iOS build yet.
- Production recovery delivery, email verification and registration abuse controls
  remain backend/public-launch work. Existing recovery prepares but does not send
  email; the mobile login does not claim otherwise.
- No token refresh/revocation API, payments, full Bible reader, camera uploads,
  QR/location attendance, push notifications or biometric unlock in this phase.
- Current compatible dependencies report 13 moderate transitive npm advisory
  entries rooted in `decode-uri-component` (Router/query-string) and `uuid`
  (Expo/xcode tooling). Reassess upstream patches before public release; forced
  audit fixes propose incompatible SDK downgrades and were not applied.
- Production still requires the existing documented non-owner RLS runtime setup,
  recovery delivery, backup rehearsal and deployment validation. Railway/backend/
  webapp behavior is unchanged; the two unrelated SMS Ruff findings remain.

References: [Expo SDK 57](https://expo.dev/changelog/sdk-57),
[SecureStore](https://docs.expo.dev/versions/latest/sdk/securestore/),
[protected routes](https://docs.expo.dev/router/advanced/protected/) and
[Android setup](https://docs.expo.dev/workflow/android-studio-emulator/).
