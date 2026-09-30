"""Reviewed code releases only; no tenant API can publish institutional templates.

Never edit denominations_v1 after release. Add a version module and a release
entry instead. Serialized release bytes and detached return values prevent
caller mutation; historical versions remain addressable after newer releases.
"""

import json
from types import MappingProxyType
from typing import Annotated, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.services.denominations import normalize_denomination
from app.services.denominations_v1 import DENOMINATION_CATALOG

RELEASES = MappingProxyType(
    {
        (t["value"], 1): json.dumps({**t, "template_version": 1, "provenance": "vinyrd_default"})
        for t in DENOMINATION_CATALOG
    }
)

Key = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,119}$")]
Label = Annotated[str, Field(min_length=1, max_length=200)]


class Position(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    key: Key
    title: Label
    labels: dict[Literal["en", "sw"], Label]
    permission_role: Literal[
        "administrator", "pastor_leader", "accountant", "receptionist", "usher"
    ]

    @field_validator("labels")
    @classmethod
    def english_fallback(cls, labels):
        if not labels.get("en"):
            raise ValueError("A verified English fallback is required.")
        return labels


class Level(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    key: Key
    label: Label
    labels: dict[Literal["en", "sw"], Label]
    optional: bool = False
    positions: list[Position]


class ReleasedTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    value: Label
    label: Label
    governance_model: Label
    template_version: int = Field(ge=1)
    levels: list[Level] = Field(min_length=1, max_length=32)
    provenance: Literal[
        "vinyrd_default", "church_approved", "denomination_approved", "denomination_official"
    ]
    institution: Label | None = None
    authorization_reference: Label | None = None

    @model_validator(mode="after")
    def institutional_provenance(self):
        if self.provenance in ("denomination_approved", "denomination_official") and not (
            self.institution and self.authorization_reference
        ):
            raise ValueError("Institutional publication requires reviewed authorization evidence.")
        return self


def versions(denomination):
    name = normalize_denomination(denomination)
    return sorted(version for name_, version in RELEASES if name_ == name)


def template(denomination, version):
    raw = RELEASES.get((normalize_denomination(denomination), version))
    if raw is None:
        raise HTTPException(422, "Unsupported released template version.")
    try:
        result = ReleasedTemplate.model_validate_json(raw).model_dump()
    except ValidationError as exc:
        raise HTTPException(
            422, "Malformed released template; publication review required."
        ) from exc
    if (
        result["value"] != normalize_denomination(denomination)
        or result["template_version"] != version
    ):
        raise HTTPException(422, "Released template identity mismatch.")
    levels = result.get("levels", [])
    keys = [level.get("key") for level in levels]
    if not keys or None in keys or len(set(keys)) != len(keys):
        raise HTTPException(422, "Invalid released hierarchy keys.")
    for level in levels:
        if not level["labels"].get("en"):
            raise HTTPException(422, "Released hierarchy lacks an English fallback.")
        positions = [p.get("key") for p in level.get("positions", [])]
        # Position identity is (level_key, position_key); historic templates reuse
        # keys such as treasurer across levels. Duplicates within a level are invalid.
        if None in positions or len(positions) != len(set(positions)):
            raise HTTPException(422, "Duplicate or invalid released position keys.")
    return result
