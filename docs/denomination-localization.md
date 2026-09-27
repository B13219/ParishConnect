# Denomination terminology and global UI language

Canonical denomination values and hierarchy keys are unchanged. The existing
`DENOMINATION_CATALOG`, aliases and `/api/v1/network/denominations` endpoint are
the only catalogue. Levels now expose `labels`, and positions expose a fixed
`key` and `labels`. Existing `label`/`title` fields remain English display defaults.
Keep keys fixed when editing or adding translations; never derive stored identity
or authorization from translated text.

TAG is the first complete bilingual template: national_church → zone → district
→ section → local_church. Its zone still has exactly two offices: fellowship
chairperson and the combined secretary/treasurer office. Existing Kiswahili zone
titles and permission-role suggestions are preserved. Other denominations retain
their existing labels under `en`; no missing Kiswahili translations are invented.
Some legacy English display labels contain parenthetical terminology; those are
retained unchanged until separately reviewed.

The localization helpers resolve en/sw (including regional tags for display),
fall back to English and produce deterministic `Kiswahili (English)` labels without
duplicating identical fallback text. They do not translate strings. Nested API
copies include label dictionaries so callers cannot mutate the shared catalogue.

`profiles.ui_language` is an account-wide interface preference. It is independent
of Branch.default_language and Member/Visitor/HouseholdPerson.preferred_language.
Profile update accepts en or sw only; unsupported/null values return 422. Old
clients that omit the field preserve its current value. Registration/import ORM
hooks use the model's en default. Login, registration and session restoration
include ui_language in the authenticated user object. The profile lookup is by
primary key for one authenticated user, not inside a user-list loop.

The mobile profile form saves English/Kiswahili through the existing profile API.
It explicitly states that full screen translations are not yet available. The
denomination views continue using backward-compatible label/title fields. No
i18n dependency or separate catalogue is introduced. An existing session's user
snapshot receives the preference again on login/session restoration; the profile
API remains authoritative immediately after editing.

## Migration and rollout

`20260927_0018` follows the sole previous head `20260926_0017`. It adds a non-null
VARCHAR(10) column to profiles with a temporary en server default to populate
existing rows, then drops the server default. No memberships, staff titles,
communication preferences, roles or RLS policies are rewritten. SQLAlchemy's
model default supplies en for new ORM/hook inserts. External SQL writers must
explicitly provide ui_language after this migration.

Apply the migration before running the new backend; release the updated mobile
form after the backend. Existing console/web/mobile clients continue working with
the additive responses. The new mobile field is not accepted by an older backend
whose ProfileUpdate forbids extra fields. Downgrade drops the UI preference column
and loses those preferences; it is not a production rollback performed by this task.

Stored historical TAG office titles remain untouched. The console preserves an
unmatched historical title as a custom title; new selections use the English
default. Office title does not grant a permission role. Catalogue position keys
are now explicit constants (scoped to their denomination/level); future translation
edits must not rename them. These fields do not introduce new persisted offices.
