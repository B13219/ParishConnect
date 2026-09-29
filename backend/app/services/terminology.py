"""Snapshot-first presentation only. Never used by authorization or stored identifiers."""

import re
import unicodedata
from copy import deepcopy

from sqlalchemy import select

from app.models import ChurchOrganizationConfiguration, OrganizationOfficeAssignment, Profile
from app.services.denominations import DENOMINATION_CATALOG, normalize_denomination
from app.services.localization import normalize_locale


def effective_locale(ui_language=None, branch_language=None):
    return normalize_locale(ui_language, normalize_locale(branch_language))


def user_locale(db, user, branch=None):
    profile = db.get(Profile, user.id)
    return effective_locale(
        profile.ui_language if profile else None, getattr(branch, "default_language", None)
    )


def presentation(labels, fallback="Organization", source="vinyrd_default"):
    clean = {
        k: v.strip()
        for k, v in (labels or {}).items()
        if k in ("en", "sw") and isinstance(v, str) and v.strip()
    }
    english = clean.get("en") or fallback
    result = {}
    for locale in ("en", "sw"):
        first = clean.get(locale) or english
        second = clean.get("sw" if locale == "en" else "en") or english
        result[locale] = {
            "label": first,
            "secondary_label": second if second != first else None,
            "bilingual_label": first + " / " + second if second != first else first,
            "source": source,
        }
    return result


def value(configuration, key, default=None):
    return (
        configuration.get(key, default)
        if isinstance(configuration, dict)
        else getattr(configuration, key, default)
    )


class Terminology:
    def __init__(self, configuration=None, denomination=None):
        self.configuration = configuration
        self.denomination = value(configuration, "denomination") or denomination or ""
        template = next(
            (
                t
                for t in DENOMINATION_CATALOG
                if t["value"] == normalize_denomination(self.denomination)
            ),
            {},
        )
        self.installed = bool(
            configuration
            and value(configuration, "setup_status") in ("configured", "custom_required")
        )
        self.levels = deepcopy(
            (value(configuration, "hierarchy_snapshot", {}) or {}).get("levels", [])
            if self.installed
            else template.get("levels", [])
        )
        self.terms = value(configuration, "terminology_snapshot", {}) or {}
        self.source = (
            "snapshot" if self.installed else "catalogue" if template else "vinyrd_default"
        )
        self.version = (
            value(configuration, "template_version")
            if self.installed
            else template.get("template_version", 1)
            if template
            else None
        )

    def level(self, key, labels=None):
        entry = next((item for item in self.levels if item["key"] == key), {})
        # The persisted terminology map is the installed configuration's label layer.
        installed = (self.terms.get(key) or entry.get("labels")) if self.installed else None
        resolved = installed or labels or entry.get("labels") or {}
        fallback = entry.get("label") or (key.replace("_", " ").title() if key else "Local Church")
        return presentation(
            resolved, fallback, self.source if installed else "snapshot" if labels else self.source
        )

    def positions(self, level_key):
        level = next((item for item in self.levels if item["key"] == level_key), {})
        return [
            {
                **p,
                "presentation": presentation(
                    p.get("labels"), p.get("title") or "Office", self.source
                ),
            }
            for p in level.get("positions", [])
        ]

    def position(self, key, locale="en", official_title=None, position_title=None, role=None):
        for level in self.levels:
            for p in self.positions(level["key"]):
                if p["key"] == key:
                    return p["presentation"][normalize_locale(locale)]["label"]
        return official_title or position_title or role or "Staff"

    def payload(self, local_key=None):
        return {
            "version": 1,
            "source": self.source,
            "template_version": self.version,
            "local_church": self.level(local_key),
            "levels": {p["key"]: self.level(p["key"]) for p in self.levels},
            "positions": {
                p["key"]: p["presentation"]
                for level in self.levels
                for p in self.positions(level["key"])
            },
        }


def resolve_level_label(configuration, level_key, locale):
    return Terminology(configuration).level(level_key)[normalize_locale(locale)]["label"]


def resolve_bilingual_level_label(configuration, level_key, locale):
    return Terminology(configuration).level(level_key)[normalize_locale(locale)]["bilingual_label"]


def resolve_position_label(configuration, position_key, locale, **fallbacks):
    return Terminology(configuration).position(position_key, locale, **fallbacks)


def resolve_organization_name(unit, locale):
    return (
        (value(unit, "localized_names", {}) or {}).get(normalize_locale(locale))
        or value(unit, "canonical_name")
        or value(unit, "name")
    )


def unit_presentation(unit, resolver=None):
    resolver = resolver or Terminology(denomination=unit.denomination)
    return {
        locale: {
            **resolver.level(unit.level_key, unit.labels_snapshot)[locale],
            "name": resolve_organization_name(unit, locale),
        }
        for locale in ("en", "sw")
    }


def configurations(db, branch_ids):
    # Existing RLS remains authoritative; never elevate to read hidden configurations.
    return (
        {
            c.branch_id: c
            for c in db.scalars(
                select(ChurchOrganizationConfiguration).where(
                    ChurchOrganizationConfiguration.branch_id.in_(branch_ids)
                )
            )
        }
        if branch_ids
        else {}
    )


def staff_context(db, user, scope):
    accessible = scope.branch_ids()
    branches = [b for b in scope.branches if b.id in accessible]
    profile = db.get(Profile, user.id)
    configs = configurations(db, [b.id for b in branches])
    own_offices = list(
        db.scalars(
            select(OrganizationOfficeAssignment)
            .where(
                OrganizationOfficeAssignment.user_id == user.id,
                OrganizationOfficeAssignment.status == "active",
            )
            .order_by(OrganizationOfficeAssignment.created_at)
        )
    )
    result = {}
    for b in branches:
        resolver = Terminology(configs.get(b.id), b.denomination)
        unit = scope.units.get(b.organization_unit_id)
        locale = effective_locale(profile.ui_language if profile else None, b.default_language)
        visible_path = scope.visible_path(b.organization_unit_id) if unit else []
        office = next(
            (
                o
                for u in reversed(visible_path)
                for o in own_offices
                if o.organization_unit_id == u.id
            ),
            None,
        )
        result[b.id] = {
            "display_position_title": resolver.position(
                office.position_key if office else None,
                locale,
                position_title=user.position_title if b.id == user.branch_id else None,
                role=" / ".join(sorted(scope.roles_for_branch(b.id))).replace("_", " "),
            ),
            "locale": effective_locale(
                profile.ui_language if profile else None, b.default_language
            ),
            "terminology": resolver.payload(unit.level_key if unit else None),
            "organization_path": [
                {
                    "id": u.id,
                    "level_key": u.level_key,
                    "presentation": unit_presentation(u, resolver),
                }
                for u in visible_path
            ]
            if unit
            else [],
        }
    return result


def search_tokens(text):
    return set(re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", text or "").casefold())) - {
        "la",
        "ya",
        "wa",
        "of",
        "the",
    }


def matches_context(query, name, path):
    # Only already-public complete paths enter this matcher. Match proper-name words
    # and any supplied localized level label, without changing a stored level key.
    wanted = search_tokens(query)
    if (query or "").strip().casefold() in name.casefold() or (
        wanted and wanted <= search_tokens(name)
    ):
        return True
    for unit in path:
        names = search_tokens(unit["name"])
        for view in unit.get("presentation", {}).values():
            names |= search_tokens(view.get("name"))
        labels = set()
        for label in unit.get("labels", {}).values():
            labels |= search_tokens(label)
        if wanted and wanted <= names | labels:
            return True
    return False


def runtime_levels(resolver):
    return [
        {
            **level,
            "presentation": resolver.level(level["key"]),
            "positions": resolver.positions(level["key"]),
        }
        for level in resolver.levels
    ]
