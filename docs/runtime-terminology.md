# Runtime denomination terminology (Phase 4)

Phase 4 extends validated checkpoint `054fa6d67c22b111a42821d42d755e467647f3f9`. It adds presentation data; no migration, new hierarchy, permission role, membership meaning or RLS policy is introduced.

## Audit and boundary

The audit covered denomination/localization and organization services, configuration snapshots, security/tenancy, network/admin APIs, the staff console, member web and native clients, and existing denomination/organization/browser tests.

| Surface | Finding and treatment |
| --- | --- |
| `organization_access.py` | Office options were read from the newest catalogue. Resolve installed office options from the authorized owner's configuration snapshot, with catalogue fallback for units without an accessible installed configuration. Keep scope checks intact. |
| `organizations.py` | Public paths exposed English canonical names and raw snapshot labels. Add allowlisted bilingual presentation/name variants from each published unit's persisted snapshot. Do not read private configuration for public traffic. |
| Organization setup | Swahili-first bilingual helper regardless of UI preference. Use server presentation and the effective staff locale; persisted setup and offices use installed runtime levels. |
| Organization Administration | Raw canonical names, inconsistent locale fallback, no clear current-context ancestry, generic summary heading. Use resolved names/levels/offices and a scoped current-context header. Discard obsolete detail responses when selection changes. |
| Branch settings/staff listings | Latest catalogue preview and free-text staff titles. Branch API supplies installed runtime levels; staff listings resolve canonical office keys first and retain legacy free text as fallback. |
| Member web/native | Discovery, Following and profiles omitted ancestry. Both consume the same compact `presentation` contract; cards show up to two nearest ancestors, profiles/membership context show the public full path. Home Church/membership views include context without changing selection semantics. |
| Discovery search | Church-name matching only. Match published organization proper names and the stored English/Swahili level labels, retaining literal church-name substring search and existing filters/pagination. |
| Generic UI vocabulary | Product concepts such as Home Church, following, membership, VINYRD access roles, technical field names, Branch tenancy and community-group configuration remain distinct from ecclesiastical terminology. This is not a full translation of every button, validation message, event or content record. |

## Canonical resolver and snapshots

`app/services/terminology.py` is the only denomination runtime policy engine. It contains no denomination-specific branches. A configured church uses `terminology_snapshot` as its installed label layer and `hierarchy_snapshot.levels` for installed levels/offices. Published OrganizationUnit labels are the immutable labels copied during setup; public runtime uses those snapshots even after a catalogue change. Existing `label`, `title`, `labels`, canonical names and keys remain present.

When configuration is absent, current catalogue data provides preview/fallback. Unknown/custom denominations get their supplied configuration labels or generic labels. Missing entries in a configured snapshot do not silently install new catalogue levels; unavailable labels fall back to the stored label or generic display. Snapshot upgrades and complex override editing remain separate workflows. There is no separate override model/UI today; existing `terminology_snapshot` entries are honored. Manually editing private snapshots alone is not a supported publication workflow: public units retain their own installed published labels.

The response adds `presentation.en` and `presentation.sw`, each with `label`, `secondary_label`, `bilingual_label`, optional proper `name`, and presentation source (`snapshot`, `catalogue`, `vinyrd_default`). No official-translation certification is invented. Existing English defaults and supplied Kiswahili are preserved; missing Kiswahili falls back to English. A proper name uses the requested `localized_names` value or `canonical_name`; it is never machine-translated.

Staff setup also returns `runtime_levels`, and authorized branch settings return `runtime_template`. Public `terminology` contains only the local level presentation; it never exposes a configuration snapshot, fingerprint, configuring actor, owner, grant or unpublished path. Discovery cards and native/web clients require no per-card catalogue request.

## Locale and caching

Staff: Profile.ui_language if available, then the selected Branch.default_language, then `en`. The effective value is returned with each authorized branch context and setup/settings response. Global member UI: Profile.ui_language, then `en`; Member.preferred_language remains exclusively a church communication preference. Native profile save updates session presentation immediately. Both locale variants travel with church data, so switching language requires no separate catalogue fetch and existing/offline data has an English/legacy fallback.

No cross-branch terminology cache is added. Staff branch switching retains the existing full page reset, while generation guards prevent slower organization-detail responses from replacing current content. The header is built only from OrganizationScope-visible paths, not from all configured ancestors. Catalogue filtering is a preview; installed church presentation is independent of that catalogue.

## Positions, reports and security

A canonical office key uses the installed localized title; absent keys retain official/custom or legacy position_title, then the existing technical-role fallback. Office selectors retain canonical keys, legacy title selectors retain their original stored English values, and permission roles remain independently selected technical values. Summary headings use the selected unit's bilingual level label; report calculations and query scopes are unchanged.

The existing `save_office` guard now validates its office key against installed office options, matching the presentation. This changes no access-grant/role checks. Label text is never supplied to an authorization decision. Runtime, migration, backup/restore credentials and initial authority/recovery architecture are unchanged.

Search evaluates only complete, active, published paths. It normalizes Unicode/case and common name connectors (la/ya/wa/of/the), then compares proper-name words plus available level labels. It does not generate translated proper names or duplicate records. Candidate profiles are streamed in batches of 100 and scanning stops after enough matches for the requested page. It is intentionally simple; high-volume search indexing and ranking remain future scaling work.

## Validation and remaining gaps

The test matrix covers every catalogue denomination, TAG bilingual order, Catholic/Lutheran/SDA defaults, custom labels, snapshot/catalogue drift, proper-name fallback, locale defaults, canonical/legacy positions, public allowlisting/search and security invariance. Existing global UI/communication preference tests remain. Chromium covers TAG English and Kiswahili, Catholic context, TAG-to-Catholic switching, bilingual setup, offices versus grants and the existing membership/organization journeys. Native tests cover English/Swahili ancestry, old/offline payload fallback and immediate Profile.ui_language presentation changes.

No schema or environment changes are required. Existing migration head is `20260928_0020`; production validation continues to use the Phase 3.5 privilege-separated runbook. No EAS build is required. Verify real institution-supplied terminology during staging; most catalogue entries intentionally retain English until approved Kiswahili is supplied. Custom hierarchy construction, snapshot upgrades, override editing, whole-application text translation and search indexing are outside this phase.

ONE ORGANIZATION TREE IS SHARED ACROSS ALL LANGUAGES

DENOMINATION TERMINOLOGY CHANGES PRESENTATION, NOT AUTHORIZATION
