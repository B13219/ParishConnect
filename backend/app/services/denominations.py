"""Current catalogue facade. Released version data lives in denominations_v1."""

from copy import deepcopy

from app.services.denominations_v1 import DENOMINATION_ALIASES
from app.services.denominations_v1 import DENOMINATION_CATALOG as RELEASED_V1

DENOMINATION_CATALOG = deepcopy(RELEASED_V1)


def normalize_denomination(value):
    if not value:
        return value
    normalized = value.strip()
    lowered = normalized.casefold()
    for item in DENOMINATION_CATALOG:
        if item["value"].casefold() == lowered:
            return item["value"]
        if any(
            alias.casefold() == lowered for alias in DENOMINATION_ALIASES.get(item["value"], [])
        ):
            return item["value"]
    return normalized


def denomination_catalog():
    # Include nested labels in the copy: API callers must not mutate defaults.
    return deepcopy(
        [
            {"template_version": 1, **item, "aliases": DENOMINATION_ALIASES.get(item["value"], [])}
            for item in DENOMINATION_CATALOG
        ]
    )
