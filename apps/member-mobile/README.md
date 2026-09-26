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

## Local development and Expo Go

Use an Expo Go version compatible with SDK 57. Current features use Expo-bundled
modules, including SecureStore, without custom native modules. If the Play Store
version differs, use Expo CLI to install a matching Android Expo Go build.
Run `npx expo start --go` and scan the QR code, or `npx expo start --go --android` with an
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
config plugins. Local iOS compilation and the iOS Simulator require macOS/Xcode.
Windows can edit, bundle and request EAS cloud builds for both platforms, but
cannot run Xcode or the iOS Simulator locally.

Locally validated: Android and iOS Metro/Hermes exports and Android native project
generation. Not validated: Gradle/Xcode compilation, installation or device execution.
This host has no Android SDK/ADB or configured Java toolchain; `expo run:android`
fails at SDK discovery. No APK has been produced.

## Application identity and build versions

The established identifiers are preserved: Android package and iOS bundle ID
`app.vinyrd.member`. Name: **VINYRD**; slug: `vinyrd-member`; version: `0.1.0`;
Android `versionCode`: **1**; iOS `buildNumber`: **1**; URL scheme: `vinyrd`.
Orientation remains unlocked (`default`), with tablet support and a light theme.
The existing crest supplies the app/iOS/adaptive Android icons and the splash
screen on VINYRD charcoal. Launcher masks and the real splash must be checked
on installed builds; Expo Go does not reproduce release splash behavior.

EAS retains `appVersionSource: local`. Before subsequent distributed builds,
increment `android.versionCode` and `ios.buildNumber` in app.json and commit the
change. No automatic version mutation is configured. All profiles use the same
application ID, so development/preview/production are not side-by-side installs.

## EAS cloud build setup and environment

The existing eas.json is extended in place:

| Profile | Environment | Android | iOS |
| --- | --- | --- | --- |
| development | development | Internal development-client APK | Signed device development client |
| preview | preview | Standalone internal APK | Signed ad hoc device build |
| preview-simulator | preview | Inherits preview; use for iOS | Standalone Simulator .app archive |
| production | production | Store AAB | Store-signed build for a later TestFlight/store workflow |

Preview builds contain their JavaScript and do not require Metro. Development
builds include expo-dev-client and use Metro. No submission profile or automatic
submission is configured. Production is preparation only; do not run it for this phase.

Cloud Android builds need no local Android SDK/Android Studio; cloud iOS builds
need no local Xcode/macOS. EAS supplies those build workers. An Expo account,
project access and build quota are required. From this directory:

```sh
npx eas-cli@latest login
npx eas-cli@latest init
```

Link the intended existing Expo project if one exists; otherwise the owner creates
it. Review and commit the resulting `extra.eas.projectId`/owner configuration;
project IDs are public, credentials are not. Do not replace eas.json with a generated
template. No owner/project ID has been guessed or cloud project created here.

Set `EXPO_PUBLIC_VINYRD_API_BASE` in each EAS environment used for builds. Use
the **same reachable HTTPS FastAPI URL including /api/v1** for both platforms.
For the first internal builds, run this interactive command and enter the approved
staging URL when prompted:

```sh
npx eas-cli@latest env:create --environment preview --name EXPO_PUBLIC_VINYRD_API_BASE --visibility plaintext
```

Use `env:update` if the variable already exists. Repeat for development/production
only when those environments are needed. EXPO_PUBLIC values are compiled into
the app and are not secrets; do not choose secret visibility. An ignored local
.env is not a substitute for EAS environment configuration. Never use localhost
for a phone or a preview build. The same API client, bearer session and church
context headers serve Android and iOS without separate API implementations.

## Android APK internal testing and physical-device installation

After the shared setup above, the existing `preview` profile explicitly selects
`android.buildType: apk`, not an AAB:

```sh
npx eas-cli@latest build --platform android --profile preview
```

Let EAS manage/generate the Android keystore when prompted. Open the resulting
EAS installation link on a physical Android phone, download the APK, allow that
browser/file manager to install unknown apps if prompted, and install VINYRD.
Disable that installer permission afterward if desired. An APK can also be installed
with `adb install -r path/to/app.apk` when platform-tools are available. An AAB
cannot be installed this way. No Google Play account/submission is required.

Alternatively, install the local toolchain and run `npm run android:build` for
an installable debug build without an EAS account.

## Development-client builds

```sh
npx eas-cli@latest build --platform android --profile development
# iOS requires the Apple/device setup below:
npx eas-cli@latest build --platform ios --profile development
npx expo start --dev-client
```

Install the development build, then open Metro from its launcher. The phone must
reach Metro and the backend; use a trusted LAN or a supported Metro tunnel when
needed. A Metro tunnel does not expose a localhost backend. Current app features
still work in matching SDK 57 Expo Go using `--go`; use preview builds to validate
branding, native configuration and release behavior.

## iOS Simulator build

```sh
npx eas-cli@latest build --platform ios --profile preview-simulator
```

This inherits preview configuration and sets `ios.simulator: true`. It does not
require Apple signing credentials or paid Apple Developer membership. Download
the .app archive and install it on a **Mac** with Xcode/iOS Simulator; on that Mac,
`npx eas-cli@latest build:run --platform ios` can select and install the build.
It cannot run on Windows or install on a physical iPhone.

## Apple Developer requirements and EAS credential management

Physical iPhone ad hoc testing requires an active Apple Developer Program team,
access to register the established bundle ID, signing permissions, a distribution
certificate and a provisioning profile containing tester device UDIDs. The owner
must authenticate with their Apple account/2FA when EAS prompts to create or update
signing assets. Use EAS-managed credentials (`npx eas-cli@latest credentials
--platform ios`) rather than placing files in the repository. No Apple team or
credentials have been invented or configured by this task.

SecureStore uses Keychain on iOS and encrypted native storage on Android. Read,
write and deletion share the same service/key options; no biometrics are enabled.
iOS Keychain entries may survive app uninstall: uninstall is not a substitute for
signing out. Test explicit logout, expiry and account switching on both devices.
The plugin's unused Face ID usage description is disabled. No camera/location/
notification permission strings or entitlements are enabled for future features.
iOS ATS explicitly rejects arbitrary insecure loads while allowing local-network
development. Expo Dev Launcher adds its Metro discovery usage text to Debug builds;
its SDK plugin strips that text and Bonjour service from non-Debug builds.

Never commit Apple/Google credentials, EAS tokens, certificates, private keys,
provisioning profiles, credentials.json or production secrets. Signing/binary files
and local env files are ignored. Keep any Google service-account JSON outside the
repository even when using a filename that is not covered by an ignore pattern.

## iOS internal physical-device testing

After EAS project/environment setup, the owner registers each test iPhone:

```sh
npx eas-cli@latest device:create
npx eas-cli@latest device:list
npx eas-cli@latest build --platform ios --profile preview
```

Open the registration link on each iPhone and follow the UDID registration steps.
Run the build interactively and authenticate with Apple to update the ad hoc
provisioning profile. Install using the EAS build link on a registered device.
New devices require a new build or `npx eas-cli@latest build:resign` with an updated
profile. Device registration alone does not change an already signed binary.
Provisioning/device processing may delay first installation. Follow any iOS trust
or Developer Mode prompts, particularly for development-client builds.

## TestFlight pilot path — later, not submitted

For a broader pilot, the owner will need an App Store Connect app matching
`app.vinyrd.member`, appropriate roles, Apple agreements and export-compliance
answers. Increment the build number, configure the approved API environment,
create a store-signed iOS build using the production profile, and only after
explicit release authorization upload it to App Store Connect/TestFlight.
Internal testers need App Store Connect access; external testing can require
Beta App Review. TestFlight does not use the ad hoc UDID allow-list. No build or
submission to TestFlight/App Store/Google Play was started here.

## First-device QA gate

On both installed preview apps verify branding/splash/icon masks, portrait and
landscape, safe areas, keyboard/input focus, scrolling, touch targets, stack back
navigation (including iOS swipe-back), HTTPS links/images and `vinyrd://` routing.
Check protected deep links while signed out. Exercise registration, zero-member
login, restart/restoration, expired token, offline logout, follow/request states,
Home Church versus viewed context and cross-church private-data separation.
These device checks remain outstanding; JavaScript export is not native compilation.

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
npm run test:android
npm run test:ios
npx expo-doctor
npx expo install --check
npm run export:android
npm run export:ios
npx expo config --type introspect
```

The mobile suite covers 33 cases: native account/request forms, zero-membership
Home, request states, secure persistence, restoration/expiry, network/storage
failures, stale auth responses, discovery filters, following, approval, primary
selection and context isolation. Jest mocks native interfaces; these are not
emulator/device tests.
The platform-specific commands run the same 33 cases under Android and iOS
resolution/transforms. An explicit standard Expo Babel preset supports both
Jest platform presets; there are no custom application transforms.

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
suite, which passed all 142 tests with PostgreSQL and Chromium enabled in the
foundation phase. It was not rerun for build-readiness changes: backend code is unchanged.

## Known limitations and public-launch gates

- No Android emulator/device run, signed APK or iOS build yet.
- Production recovery delivery, email verification and registration abuse controls
  remain backend/public-launch work. Existing recovery prepares but does not send
  email; the mobile login does not claim otherwise.
- No token refresh/revocation API, payments, full Bible reader, camera uploads,
  QR/location attendance, push notifications or biometric unlock in this phase.
- Current compatible dependencies report 14 moderate transitive npm advisory
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

Build references: [EAS profiles](https://docs.expo.dev/build/eas-json/),
[internal distribution](https://docs.expo.dev/build/internal-distribution/),
[iOS Simulator builds](https://docs.expo.dev/build-reference/simulators/),
[EAS environments](https://docs.expo.dev/eas/environment-variables/) and
[later iOS submission](https://docs.expo.dev/submit/ios/).
