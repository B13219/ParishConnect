"""Small terminology helpers; locale selection never changes canonical identity."""

from collections.abc import Mapping

SUPPORTED_UI_LANGUAGES = ("en", "sw")


def normalize_locale(value: str | None, fallback: str = "en") -> str:
    """Resolve display locales (including regional tags); not a storage validator."""
    language = (value or "").strip().lower().replace("_", "-").split("-")[0]
    if language in SUPPORTED_UI_LANGUAGES:
        return language
    return fallback if fallback in SUPPORTED_UI_LANGUAGES else "en"


def localized_label(
    labels: Mapping[str, str], locale: str | None, fallback_locale: str = "en"
) -> str:
    for language in (normalize_locale(locale), normalize_locale(fallback_locale), "en"):
        label = labels.get(language)
        if label and label.strip():
            return label.strip()
    return ""


def bilingual_label(labels: Mapping[str, str], primary: str = "sw", secondary: str = "en") -> str:
    first = localized_label(labels, primary)
    second = localized_label(labels, secondary)
    return f"{first} ({second})" if first and second and first != second else first or second
